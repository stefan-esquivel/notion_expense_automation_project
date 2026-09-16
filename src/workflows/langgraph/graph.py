
from pathlib import Path
from langgraph.graph import StateGraph, END

from domain.enums import Sources, WorkflowStatus
from domain.models.workflow import WorkflowInput
from services.pdf_extractor import PDFExtractor
from workflows.langgraph.nodes.ingest_node import ingest_node
from workflows.langgraph.nodes.extract_node import extract_node
from workflows.langgraph.nodes.scan_node import scan_node
from workflows.langgraph.nodes.augment_node import augment_node
from workflows.langgraph.nodes.enrich_node import enrich_node
from workflows.langgraph.nodes.review_node import review_node
from workflows.langgraph.nodes.validate_node import validate_node
from workflows.langgraph.nodes.commit_node import commit_node
from workflows.langgraph.state import ReceiptWorkflowState

def _route_or_end(next_node: str):
    """Build a router that stops the graph if the previous node failed.

    Returns a function suitable for add_conditional_edges: "failed" (routed
    to END) if the node that just ran set status to FAILED, else "continue"
    (routed to next_node).
    """
    def _router(state: ReceiptWorkflowState) -> str:
        return "failed" if state.get("status") == WorkflowStatus.FAILED else "continue"
    return _router


def missing_information(state: ReceiptWorkflowState) -> str:
    """
    Route after scan: stop if scan (or an earlier node) failed, otherwise
    check if any required information is missing from the receipt.

    Args:
        state: The current state of the receipt workflow.

    Returns:
        "failed", "augment", or "enrich".
    """
    if state.get("status") == WorkflowStatus.FAILED:
        return "failed"
    scan_results = state.get("scan_results")
    return "augment" if (scan_results and scan_results.has_missing_data) else "enrich"


def _route_after_review(state: ReceiptWorkflowState) -> str:
    """Route after review back to validate or forward to commit.

    Returns:
        "failed"   – review node itself failed (user cancelled, etc.)
        "validate" – loop: user made edits; re-run validation
        "commit"   – all issues are GREEN; safe to commit
    """
    if state.get("status") == WorkflowStatus.FAILED:
        return "failed"

    # Re-run validation so we evaluate the updated/corrected receipt
    state = validate_node(state)

    validation_result = state.get("validation_result")
    acknowledged = state.get("acknowledged_warnings") or set()

    # If there is no validation result yet, or it is not green, go back to validate.
    if validation_result is None or not validation_result.is_green(acknowledged):
        return "validate"

    return "commit"


def build_graph():

    graph = StateGraph(ReceiptWorkflowState)  # type: ignore[misc]

    graph.add_node("ingest", ingest_node)
    graph.add_node("extract", extract_node)
    graph.add_node("scan", scan_node)
    graph.add_node("augment", augment_node)
    graph.add_node("enrich", enrich_node)
    graph.add_node("validate", validate_node)
    graph.add_node("review", review_node)
    graph.add_node("commit", commit_node)

    graph.set_entry_point("ingest")

    graph.add_conditional_edges("ingest", _route_or_end("extract"), {"continue": "extract", "failed": END})

    graph.add_conditional_edges("extract", _route_or_end("scan"), {"continue": "scan", "failed": END})

    graph.add_conditional_edges(
        "scan",
        missing_information, {"failed": END, "augment": "augment", "enrich": "enrich"})

    graph.add_conditional_edges("augment", _route_or_end("enrich"), {"continue": "enrich", "failed": END})

    graph.add_conditional_edges("enrich", _route_or_end("validate"), {"continue": "validate", "failed": END})

    graph.add_conditional_edges(
        "validate",
        _route_or_end("review"),
        {"continue": "review", "failed": END},
    )

    graph.add_conditional_edges(
        "review",
        _route_after_review,
        {"validate": "validate", "commit": "commit", "failed": END},
    )

    graph.add_edge("commit", END)

    return graph.compile()


def create_initial_state(pdf_path: str, source: Sources = Sources.LOCAL_FOLDER) -> ReceiptWorkflowState:
    """Create initial workflow state from a PDF file path."""
    
    # Extract raw text
    extractor = PDFExtractor()
    raw_text = extractor.extract_text(Path(pdf_path))
    
    # Create workflow input
    workflow_input = WorkflowInput(
        source=source,
        file_path=pdf_path,
        raw_text=raw_text
    )
    
    # Return initial state
    return {
        "status": WorkflowStatus.PENDING,
        "workflow_input": workflow_input,
        "receipt": None,
        "scan_results": None,
        "augment_results": None,
        "enriched_receipt": None,
        "validation_result": None,
        "acknowledged_warnings": set(),
        "review_data": None,
        "expense_summary": None,
        "results": None,
        "failure_reason": None
    }

def main():
    """Test the workflow with a sample PDF."""
    from logger import get_logger
    
    logger = get_logger(__name__)
    
    # Build the graph
    app = build_graph()
    
    # Create initial state with the test PDF
    pdf_path = "receipts/test_input/2026-03-07_Amazon_Order_Baking_Sheets_$49.60.pdf"
    logger.info(f"Testing workflow with PDF: {pdf_path}")
    
    initial_state = create_initial_state(pdf_path)
    
    # Run the workflow
    logger.info("Running workflow...")
    result = app.invoke(initial_state)
    
    # Log results
    logger.info(f"Workflow completed with status: {result['status'].value}")
    
    if result.get('failure_reason'):
        logger.error(f"Workflow failed: {result['failure_reason']}")
    else:
        logger.info("Workflow completed successfully")
        
        if result.get('receipt'):
            receipt = result['receipt']
            logger.info(f"Receipt extracted: {receipt.vendor} - ${receipt.total:.2f}")
        
        if result.get('results'):
            results = result['results']
            logger.info(f"Notion expense created: {results.notion_expense_id}")
            logger.info(f"File archived to: {results.archive_path}")


if __name__ == "__main__":
    main()
