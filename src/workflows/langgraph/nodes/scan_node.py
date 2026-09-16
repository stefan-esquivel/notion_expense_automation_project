"""Scan node for LangGraph workflow."""

from domain.enums import WorkflowStatus
from domain.models.workflow import ScanResults
from domain.models.recipts import get_missing_required_fields
from workflows.langgraph.state import ReceiptWorkflowState
from logger import get_logger

logger = get_logger(__name__)


def scan_node(state: ReceiptWorkflowState) -> ReceiptWorkflowState:
    """
    Scan node: Detects required receipt fields missing before enrichment,
    so enrichment/LLM calls aren't wasted on structurally incomplete data.

    Args:
        state: Current workflow state with receipt data

    Returns:
        Updated state with scan_results
    """
    state["status"] = WorkflowStatus.SCANNING

    try:
        receipt = state.get("receipt")
        if not receipt:
            raise ValueError("No receipt data found in state")

        missing_fields = get_missing_required_fields(receipt)

        state["scan_results"] = ScanResults(
            has_missing_data=len(missing_fields) > 0,
            missing_fields=missing_fields
        )

        if missing_fields:
            logger.info(f"⚠️  Scan found missing fields: {', '.join(missing_fields)}")
        else:
            logger.info("✓ Scan found no missing fields")

        return state

    except Exception as e:
        state["status"] = WorkflowStatus.FAILED
        state["failure_reason"] = f"Scan failed: {str(e)}"
        logger.error(f"✗ Scan error: {e}")
        return state
