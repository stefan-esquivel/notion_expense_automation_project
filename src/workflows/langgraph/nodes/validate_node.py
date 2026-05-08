"""Validate node for LangGraph workflow."""

from datetime import datetime
from typing import List, Optional, Tuple

from workflows.langgraph.state import ReceiptWorkflowState
from domain.enums import WorkflowStatus
from domain.models.workflow import ValidationResult
from domain.models.recipts import Receipt, ReceiptItem
from domain.models.enrichment import EnrichedReceipt
from logger import get_logger

logger = get_logger(__name__)

# Validation thresholds
HIGH_AMOUNT_THRESHOLD = 10000
MIN_REASONABLE_YEAR = 2000
LOW_CONFIDENCE_THRESHOLD = 0.7
TOTAL_MISMATCH_TOLERANCE = 0.15
MIN_TOLERANCE_AMOUNT = 0.10  # Minimum $0.10 tolerance for rounding

# Confidence multipliers
CONFIDENCE_HIGH_AMOUNT = 0.9
CONFIDENCE_OLD_DATE = 0.8
CONFIDENCE_TOTAL_MISMATCH = 0.85


def _validate_required_fields(receipt: Receipt) -> Tuple[List[str], float]:
    """Validate required fields are present and non-empty.
    
    Args:
        receipt: Receipt object to validate
        
    Returns:
        Tuple of (errors list, confidence score)
    """
    errors = []
    confidence = 1.0
    
    if not receipt.vendor or receipt.vendor.strip() == "":
        errors.append("Missing merchant name")
    if not receipt.date or receipt.date.strip() == "":
        errors.append("Missing transaction date")
    if receipt.total is None:
        errors.append("Missing total amount")
    
    return errors, confidence


def _validate_amount(amount: Optional[float]) -> Tuple[List[str], List[str], float]:
    """Validate amount is positive and reasonable.
    
    Args:
        amount: Amount to validate
        
    Returns:
        Tuple of (errors list, warnings list, confidence score)
    """
    errors, warnings = [], []
    confidence = 1.0
    
    if amount is not None:
        if amount <= 0:
            errors.append(f"Invalid amount: ${amount:.2f} (must be positive)")
        elif amount > HIGH_AMOUNT_THRESHOLD:
            warnings.append(f"Unusually high amount: ${amount:.2f}")
            confidence *= CONFIDENCE_HIGH_AMOUNT
    
    return errors, warnings, confidence


def _validate_date(date_str: Optional[str]) -> Tuple[List[str], List[str], float]:
    """Validate date format and reasonableness.
    
    Args:
        date_str: ISO format date string to validate
        
    Returns:
        Tuple of (errors list, warnings list, confidence score)
    """
    errors, warnings = [], []
    confidence = 1.0
    
    if not date_str:
        return errors, warnings, confidence
    
    try:
        parsed_date = datetime.fromisoformat(date_str)
        current_date = datetime.now().date()
        
        if parsed_date.year < MIN_REASONABLE_YEAR:
            warnings.append(f"Date is very old: {date_str}")
            confidence *= CONFIDENCE_OLD_DATE
        elif parsed_date.date() > current_date:
            errors.append(f"Date is in the future: {date_str}")
    except (ValueError, TypeError):
        errors.append(f"Invalid date format: {date_str} (expected ISO format YYYY-MM-DD)")
    
    return errors, warnings, confidence


def _validate_total_calculation(
    items: Optional[List[ReceiptItem]],
    total: Optional[float]
) -> Tuple[List[str], float]:
    """Verify total matches sum of items within tolerance.
    
    Args:
        items: List of receipt items
        total: Total amount from receipt
        
    Returns:
        Tuple of (warnings list, confidence score)
    """
    warnings = []
    confidence = 1.0
    
    if not items or not total:
        return warnings, confidence
    
    calculated_total = sum(item.price for item in items)
    difference = abs(total - calculated_total)
    tolerance = max(total * TOTAL_MISMATCH_TOLERANCE, MIN_TOLERANCE_AMOUNT)
    
    if difference > tolerance:
        warnings.append(
            f"Total mismatch: Receipt shows ${total:.2f}, "
            f"items sum to ${calculated_total:.2f} (difference: ${difference:.2f})"
        )
        confidence *= CONFIDENCE_TOTAL_MISMATCH
    
    return warnings, confidence


def _validate_enrichment_confidence(
    enriched: Optional[EnrichedReceipt]
) -> Tuple[List[str], float]:
    """Check enrichment confidence score.
    
    Args:
        enriched: Enriched receipt data
        
    Returns:
        Tuple of (warnings list, confidence score)
    """
    warnings = []
    confidence = 1.0
    
    if enriched and enriched.confidence_score < LOW_CONFIDENCE_THRESHOLD:
        warnings.append(f"Low enrichment confidence: {enriched.confidence_score:.2f}")
        confidence *= enriched.confidence_score
    
    return warnings, confidence


def _log_validation_results(
    result: ValidationResult,
    errors: List[str],
    warnings: List[str],
    confidence: float
) -> None:
    """Log validation results with appropriate severity.
    
    Args:
        result: Validation result object
        errors: List of validation errors
        warnings: List of validation warnings
        confidence: Overall confidence score
    """
    if result.is_valid and not result.requires_review:
        logger.info(f"✓ Validation passed (confidence: {confidence:.2f})")
    elif result.is_valid and result.requires_review:
        logger.info(f"⚠️  Validation passed with warnings (confidence: {confidence:.2f})")
        for warning in warnings:
            logger.info(f"    - {warning}")
    else:
        logger.warning(f"✗ Validation failed:")
        for error in errors:
            logger.warning(f"    - {error}")
        if warnings:
            logger.info(f"  Warnings:")
            for warning in warnings:
                logger.info(f"    - {warning}")


def validate_node(state: ReceiptWorkflowState) -> ReceiptWorkflowState:
    """Validate extracted and enriched receipt data.
    
    Performs comprehensive validation including:
    - Required field presence
    - Amount validity and reasonableness
    - Date format and temporal validity
    - Total calculation verification
    - Enrichment confidence assessment
    
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
        
        # Collect all validation results
        all_errors: List[str] = []
        all_warnings: List[str] = []
        confidence_score = 1.0
        
        # Run validation checks
        errors, conf = _validate_required_fields(receipt)
        all_errors.extend(errors)
        confidence_score *= conf
        
        errors, warnings, conf = _validate_amount(receipt.total)
        all_errors.extend(errors)
        all_warnings.extend(warnings)
        confidence_score *= conf
        
        errors, warnings, conf = _validate_date(receipt.date)
        all_errors.extend(errors)
        all_warnings.extend(warnings)
        confidence_score *= conf
        
        warnings, conf = _validate_total_calculation(receipt.items, receipt.total)
        all_warnings.extend(warnings)
        confidence_score *= conf
        
        warnings, conf = _validate_enrichment_confidence(state.get("enriched_receipt"))
        all_warnings.extend(warnings)
        confidence_score *= conf
        
        # Create validation result
        validation_result = ValidationResult(
            is_valid=len(all_errors) == 0,
            errors=all_errors,
            warnings=all_warnings,
            requires_review=True,  # Always require review for prototyping
            confidence_score=confidence_score
        )
        
        state["validation_result"] = validation_result
        _log_validation_results(validation_result, all_errors, all_warnings, confidence_score)
        
        return state
        
    except ValueError as e:
        # Handle expected validation errors
        state["status"] = WorkflowStatus.FAILED
        state["failure_reason"] = f"Validation failed: {str(e)}"
        logger.error(f"✗ Validation error: {e}")
        return state
    except Exception as e:
        # Handle unexpected errors with full context
        state["status"] = WorkflowStatus.FAILED
        state["failure_reason"] = f"Unexpected validation error: {str(e)}"
        logger.exception(f"✗ Unexpected validation error: {e}")
        return state