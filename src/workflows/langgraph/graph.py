
from pathlib import Path
from langgraph.graph import StateGraph, END

from domain.enums import Sources, WorkflowStatus
from domain.models.workflow import WorkflowInput
from services.pdf_extractor import PDFExtractor
from workflows.langgraph.nodes.commit_node import commit_node
from workflows.langgraph.nodes.ingest_node import ingest_node
from workflows.langgraph.nodes.extract_node import extract_node
from workflows.langgraph.nodes.enrich_node import enrich_node
from workflows.langgraph.nodes.review_node import review_node
from workflows.langgraph.nodes.validate_node import validate_node
from workflows.langgraph.state import ReceiptWorkflowState

def build_graph():

    graph = StateGraph(ReceiptWorkflowState)

    graph.add_node("ingest", ingest_node)
    graph.add_node("extract", extract_node)
    graph.add_node("enrich", enrich_node)
    graph.add_node("validate", validate_node)
    graph.add_node("review", review_node)
    graph.add_node("commit", commit_node)

    graph.set_entry_point("ingest")

    graph.add_edge("ingest", "extract")

    graph.add_edge("extract", "enrich")

    graph.add_edge("enrich", "validate")

    # For prototyping: Always go to review after validation
    graph.add_edge("validate", "review")

    graph.add_edge("review", "commit")

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
        "enriched_receipt": None,
        "validation_result": None,
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
