
"""Enrich node for LangGraph workflow."""

from workflows.langgraph.state import ReceiptWorkflowState
from domain.enums import WorkflowStatus
from llm.receipt_extractor import llm_enrich_receipt, keyword_enrich_receipt, FALLBACK_CONFIDENCE
from logger import get_logger

logger = get_logger(__name__)

# Confidence score thresholds used for logging/downstream routing
CONFIDENCE_HIGH = 0.85
CONFIDENCE_MEDIUM_LOW = 0.60


def _confidence_band(score: float) -> str:
    """Return a human-readable label for a confidence score."""
    if score >= CONFIDENCE_HIGH:
        return "high"
    if score >= CONFIDENCE_MEDIUM_LOW:
        return "medium"
    return "low"


def enrich_node(state: ReceiptWorkflowState) -> ReceiptWorkflowState:
    """
    Enrich node: Categorizes receipt using LLM, with keyword-matching fallback.

    This node:
    1. Updates status to ENRICHING
    2. Attempts LLM-based categorisation
    3. Falls back to keyword matching (confidence 0.5) if the LLM call fails
    4. Stores enriched data in state

    Confidence bands:
        ≥ 0.85  → high   (auto-commit eligible)
        0.60–0.84 → medium (routed to review)
        < 0.60  → low    (routed to review, flagged in validate)

    Args:
        state: Current workflow state with receipt data

    Returns:
        Updated state with enriched_receipt
    """
    state["status"] = WorkflowStatus.ENRICHING

    receipt = state.get("receipt")
    if not receipt:
        state["status"] = WorkflowStatus.FAILED
        state["failure_reason"] = "Enrichment failed: No receipt data found in state"
        logger.error("✗ Enrichment error: No receipt data found in state")
        return state

    # Skip LLM enrichment for manually-entered / unknown receipts
    if receipt.vendor.lower() == "unknown":
        logger.info("🤖 Skipping LLM enrichment for manual receipts")
        return state

    try:
        logger.info(f"🤖 Enriching receipt: {receipt.vendor}")
        enriched_receipt = llm_enrich_receipt(receipt)

    except Exception as e:
        # LLM failed — fall back to keyword matching so the workflow continues
        logger.warning(f"⚠ LLM enrichment failed ({e}); falling back to keyword matching")
        enriched_receipt = keyword_enrich_receipt(receipt)

    state["enriched_receipt"] = enriched_receipt

    band = _confidence_band(enriched_receipt.confidence_score)
    logger.info(
        f"✓ Categorized as: {enriched_receipt.merchant_category} "
        f"(confidence: {enriched_receipt.confidence_score:.2f} — {band})"
    )
    if enriched_receipt.notes:
        logger.info(f"  Notes: {enriched_receipt.notes}")

    return state
