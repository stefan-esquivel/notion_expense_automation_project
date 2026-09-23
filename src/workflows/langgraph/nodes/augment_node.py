"""Augment node for LangGraph workflow."""

from typing import Dict

from domain.enums import WorkflowStatus
from domain.models.workflow import AugmentResults
from domain.models.recipts import get_missing_required_fields
from llm.receipt_extractor import llm_extract_receipt
from workflows.langgraph.state import ReceiptWorkflowState
from logger import get_logger

logger = get_logger(__name__)


def augment_node(state: ReceiptWorkflowState) -> ReceiptWorkflowState:
    """
    Augment node: Attempts to auto-fill required fields that scan found missing.

    This node:
    1. Updates status to AUGMENTING
    2. Re-runs LLM extraction on the raw receipt text to try to recover
       values for whichever required fields scan flagged as missing
    3. Fills in whatever it can directly on the existing receipt, and
       records how each field was filled (for display during review)
    4. Records any fields that are still missing after the attempt

    Args:
        state: Current workflow state with receipt and scan_results

    Returns:
        Updated state with receipt (possibly filled in) and augment_results
    """
    state["status"] = WorkflowStatus.AUGMENTING

    try:
        receipt = state.get("receipt")
        if not receipt:
            raise ValueError("No receipt data found in state")

        scan_results = state.get("scan_results")
        missing_fields = (
            list(scan_results.missing_fields)
            if scan_results else get_missing_required_fields(receipt)
        )

        if not missing_fields:
            logger.info("✓ No missing fields to augment")
            state["augment_results"] = AugmentResults(filled_fields={}, still_missing=[])
            state["status"] = WorkflowStatus.ENRICHING
            return state

        logger.info(f"🔧 Attempting to auto-fill missing fields: {', '.join(missing_fields)}")

        workflow_input = state.get("workflow_input")
        raw_text = workflow_input.raw_text if workflow_input else ""

        filled_fields: Dict[str, str] = {}

        if raw_text:
            try:
                llm_guess = llm_extract_receipt(raw_text)
            except Exception as e:
                logger.warning(f"LLM augment extraction failed: {e}")
                llm_guess = None

            if llm_guess:
                for field in missing_fields:
                    guessed_value = getattr(llm_guess, field, None)
                    if guessed_value in (None, ""):
                        continue
                    setattr(receipt, field, guessed_value)
                    filled_fields[field] = "llm_extraction"

        still_missing = get_missing_required_fields(receipt)

        state["receipt"] = receipt
        state["augment_results"] = AugmentResults(
            filled_fields=filled_fields,
            still_missing=still_missing
        )

        if filled_fields:
            logger.info(f"✓ Auto-filled: {', '.join(filled_fields.keys())}")
        if still_missing:
            logger.info(f"⚠️  Still missing after augment: {', '.join(still_missing)}")

        state["status"] = WorkflowStatus.ENRICHING
        return state

    except Exception as e:
        state["status"] = WorkflowStatus.FAILED
        state["failure_reason"] = f"Augment failed: {str(e)}"
        logger.error(f"✗ Augment error: {e}")
        return state
