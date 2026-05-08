
"""Enrich node for LangGraph workflow."""

from workflows.langgraph.state import ReceiptWorkflowState
from domain.enums import WorkflowStatus
from llm.receipt_extractor import llm_enrich_receipt
from logger import get_logger

logger = get_logger(__name__)


def enrich_node(state: ReceiptWorkflowState) -> ReceiptWorkflowState:
    """
    Enrich node: Categorizes receipt using LLM.
    
    This node:
    1. Updates status to ENRICHING
    2. Uses LLM to categorize the receipt based on merchant and items
    3. Stores enriched data in state
    4. Handles errors gracefully
    
    Args:
        state: Current workflow state with receipt data
        
    Returns:
        Updated state with enriched_receipt or failure information
    """
    state["status"] = WorkflowStatus.ENRICHING

    try:
        # Get receipt from state
        receipt = state.get("receipt")
        if not receipt:
            raise ValueError("No receipt data found in state")
        
        # Enrich receipt using LLM
        logger.info(f"🤖 Enriching receipt: {receipt.vendor}")
        enriched_receipt = llm_enrich_receipt(receipt)
        
        # Store enriched receipt in state
        state["enriched_receipt"] = enriched_receipt
        
        logger.info(f"✓ Categorized as: {enriched_receipt.merchant_category} (confidence: {enriched_receipt.confidence_score:.2f})")
        if enriched_receipt.notes:
            logger.info(f"  Notes: {enriched_receipt.notes}")
        
        return state

    except Exception as e:
        # Handle enrichment failure
        state["status"] = WorkflowStatus.FAILED
        state["failure_reason"] = f"Enrichment failed: {str(e)}"
        logger.error(f"✗ Enrichment error: {e}")
        return state