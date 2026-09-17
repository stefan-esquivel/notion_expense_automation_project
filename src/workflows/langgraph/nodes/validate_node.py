"""Validate node for LangGraph workflow."""

from datetime import datetime
from typing import List, Optional, Tuple

from workflows.langgraph.state import ReceiptWorkflowState
from domain.enums import WorkflowStatus, ValidationSeverity
from domain.models.workflow import ValidationResult, ValidationIssue
from domain.models.recipts import Receipt, ReceiptItem, get_missing_required_fields
from domain.models.enrichment import EnrichedReceipt
from llm.receipt_extractor import llm_suspicious_confidence_check
from logger import get_logger

logger = get_logger(__name__)

# Validation thresholds
HIGH_AMOUNT_THRESHOLD = 10000
MIN_REASONABLE_YEAR = 2000
LOW_CONFIDENCE_THRESHOLD = 0.7
TOTAL_MISMATCH_TOLERANCE = 0.15
MIN_TOLERANCE_AMOUNT = 0.10  # Minimum $0.10 tolerance for rounding

# Confidence score below which the LLM catch-all check fires
SUSPICIOUS_CONFIDENCE_THRESHOLD = 0.60

# Confidence multipliers
CONFIDENCE_HIGH_AMOUNT = 0.9
CONFIDENCE_OLD_DATE = 0.8
CONFIDENCE_TOTAL_MISMATCH = 0.85

# Human-readable labels for required fields
_REQUIRED_FIELD_MESSAGES = {
    "vendor": "Missing merchant name",
    "date": "Missing transaction date",
    "total": "Missing total amount",
}

UNKNOWN_MERCHANT_NAME = "Unknown Merchant"


def _check_required_fields(receipt: Receipt) -> Tuple[List[ValidationIssue], float]:
    """RED: required fields must be present."""
    missing = get_missing_required_fields(receipt)
    issues = [
        ValidationIssue(
            message=_REQUIRED_FIELD_MESSAGES[field],
            severity=ValidationSeverity.RED,
            field=field,
            key=f"missing_{field}",
        )
        for field in missing
    ]
    return issues, 1.0


def _check_amount(amount: Optional[float]) -> Tuple[List[ValidationIssue], float]:
    """RED for non-positive amounts; YELLOW for unusually high amounts."""
    issues: List[ValidationIssue] = []
    confidence = 1.0

    if amount is not None:
        if amount <= 0:
            issues.append(ValidationIssue(
                message=f"Invalid amount: ${amount:.2f} (must be positive)",
                severity=ValidationSeverity.RED,
                field="total",
                key="invalid_amount",
            ))
        elif amount > HIGH_AMOUNT_THRESHOLD:
            issues.append(ValidationIssue(
                message=f"Unusually high amount: ${amount:.2f}",
                severity=ValidationSeverity.YELLOW,
                field="total",
                key="high_amount",
            ))
            confidence *= CONFIDENCE_HIGH_AMOUNT

    return issues, confidence


def _check_date(date_str: Optional[str]) -> Tuple[List[ValidationIssue], float]:
    """RED for invalid format or future date; YELLOW for very old date."""
    issues: List[ValidationIssue] = []
    confidence = 1.0

    if not date_str:
        return issues, confidence

    try:
        parsed_date = datetime.fromisoformat(date_str)
        current_date = datetime.now().date()

        if parsed_date.year < MIN_REASONABLE_YEAR:
            issues.append(ValidationIssue(
                message=f"Date is very old: {date_str}",
                severity=ValidationSeverity.YELLOW,
                field="date",
                key="old_date",
            ))
            confidence *= CONFIDENCE_OLD_DATE
        elif parsed_date.date() > current_date:
            issues.append(ValidationIssue(
                message=f"Date is in the future: {date_str}",
                severity=ValidationSeverity.RED,
                field="date",
                key="future_date",
            ))
    except (ValueError, TypeError):
        issues.append(ValidationIssue(
            message=f"Invalid date format: {date_str} (expected ISO format YYYY-MM-DD)",
            severity=ValidationSeverity.RED,
            field="date",
            key="invalid_date_format",
        ))

    return issues, confidence


def _check_unknown_merchant(receipt: Receipt) -> Tuple[List[ValidationIssue], float]:
    """YELLOW when vendor is still the default 'Unknown Merchant' placeholder."""
    issues: List[ValidationIssue] = []
    if receipt.vendor == UNKNOWN_MERCHANT_NAME:
        issues.append(ValidationIssue(
            message=(
                "Merchant name is 'Unknown Merchant' — could not be identified automatically. "
                "Please verify or update the merchant name during review."
            ),
            severity=ValidationSeverity.YELLOW,
            field="vendor",
            key="unknown_merchant",
        ))
    return issues, 1.0


def _check_total_calculation(
    items: Optional[List[ReceiptItem]],
    total: Optional[float],
) -> Tuple[List[ValidationIssue], float]:
    """YELLOW when sum of line items diverges from the receipt total."""
    issues: List[ValidationIssue] = []
    confidence = 1.0

    if not items or not total:
        return issues, confidence

    calculated_total = sum(item.price for item in items)
    difference = abs(total - calculated_total)
    tolerance = max(total * TOTAL_MISMATCH_TOLERANCE, MIN_TOLERANCE_AMOUNT)

    if difference > tolerance:
        issues.append(ValidationIssue(
            message=(
                f"Total mismatch: receipt shows ${total:.2f}, "
                f"items sum to ${calculated_total:.2f} (difference: ${difference:.2f})"
            ),
            severity=ValidationSeverity.YELLOW,
            field="total",
            key="total_mismatch",
        ))
        confidence *= CONFIDENCE_TOTAL_MISMATCH

    return issues, confidence


def _check_enrichment_confidence(
    enriched: Optional[EnrichedReceipt],
) -> Tuple[List[ValidationIssue], float]:
    """YELLOW when enrichment confidence is below the threshold."""
    issues: List[ValidationIssue] = []
    confidence = 1.0

    if enriched and enriched.confidence_score < LOW_CONFIDENCE_THRESHOLD:
        issues.append(ValidationIssue(
            message=f"Low enrichment confidence: {enriched.confidence_score:.2f}",
            severity=ValidationSeverity.YELLOW,
            field=None,
            key="low_enrichment_confidence",
        ))
        confidence *= enriched.confidence_score

    return issues, confidence


def _log_validation_results(result: ValidationResult) -> None:
    red = [i for i in result.issues if i.severity == ValidationSeverity.RED]
    yellow = [i for i in result.issues if i.severity == ValidationSeverity.YELLOW]

    if not red and not yellow:
        logger.info(f"✓ Validation passed — all GREEN (confidence: {result.confidence_score:.2f})")
        return

    if red:
        logger.warning(f"🔴 {len(red)} blocking issue(s):")
        for issue in red:
            logger.warning(f"    🔴 {issue.message}")

    if yellow:
        logger.info(f"🟡 {len(yellow)} advisory issue(s):")
        for issue in yellow:
            logger.info(f"    🟡 {issue.message}")


def validate_node(state: ReceiptWorkflowState) -> ReceiptWorkflowState:
    """Validate extracted and enriched receipt data with tiered severity.

    Each check produces either a RED (blocking) or YELLOW (advisory) issue.
    The graph routes back to review until is_green() returns True.

    When the composite confidence score falls below SUSPICIOUS_CONFIDENCE_THRESHOLD
    and none of the named checks explain it, the LLM is called to produce a
    catch-all YELLOW advisory so the user knows something looks off.

    Args:
        state: Current workflow state with receipt and enriched_receipt

    Returns:
        Updated state with validation_result
    """
    state["status"] = WorkflowStatus.VALIDATING

    try:
        receipt = state.get("receipt")
        if not receipt:
            raise ValueError("No receipt data found in state")

        logger.info(f"🔍 Validating receipt: {receipt.vendor}")

        all_issues: List[ValidationIssue] = []
        confidence_score = 1.0

        for checker, args in [
            (_check_required_fields,       (receipt,)),
            (_check_unknown_merchant,      (receipt,)),
            (_check_amount,                (receipt.total,)),
            (_check_date,                  (receipt.date,)),
            (_check_total_calculation,     (receipt.items, receipt.total)),
            (_check_enrichment_confidence, (state.get("enriched_receipt"),)),
        ]:
            issues, conf = checker(*args)  # type: ignore[call-arg]
            all_issues.extend(issues)
            confidence_score *= conf

        # ── LLM catch-all: low confidence with no specific explanation ────
        if confidence_score < SUSPICIOUS_CONFIDENCE_THRESHOLD and not all_issues:
            enriched = state.get("enriched_receipt")
            llm_issue = llm_suspicious_confidence_check(receipt, enriched, confidence_score)
            if llm_issue:
                logger.info(f"🤖 LLM flagged suspicious confidence: {llm_issue.message}")
                all_issues.append(llm_issue)

        state["validation_result"] = ValidationResult(
            issues=all_issues,
            confidence_score=confidence_score,
        )

        _log_validation_results(state["validation_result"])
        return state

    except ValueError as e:
        state["status"] = WorkflowStatus.FAILED
        state["failure_reason"] = f"Validation failed: {str(e)}"
        logger.error(f"✗ Validation error: {e}")
        return state
    except Exception as e:
        state["status"] = WorkflowStatus.FAILED
        state["failure_reason"] = f"Unexpected validation error: {str(e)}"
        logger.exception(f"✗ Unexpected validation error: {e}")
        return state
