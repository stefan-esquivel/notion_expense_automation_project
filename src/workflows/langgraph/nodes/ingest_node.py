from config import Config
from services.ui import ExpenseUI
from workflows.langgraph.state import ReceiptWorkflowState
from domain.enums import WorkflowStatus
from pathlib import Path
from logger import get_logger

logger = get_logger(__name__)
    

def ingest_node(state: ReceiptWorkflowState) -> ReceiptWorkflowState:
    """
    Ingest node: Validates input and prepares workflow.
    
    This is the entry point of the workflow that:
    1. Updates status to INGESTING
    2. Validates the workflow_input
    3. Prepares the state for extraction
    """

    state["status"] = WorkflowStatus.INGESTING

    ui = ExpenseUI(
        your_name=Config.YOUR_NAME,
        partner_name=Config.PARTNER_NAME
    )
    # Validate input
    workflow_input = state.get("workflow_input")
    if not workflow_input:
        state["status"] = WorkflowStatus.FAILED
        state["failure_reason"] = "No workflow input provided"
        return state
    
    # Validate file path exists
    if not workflow_input.file_path:
        state["status"] = WorkflowStatus.FAILED
        state["failure_reason"] = "No file path provided"
        return state

    # Validate file exists
    file_path = Path(workflow_input.file_path)
    if not file_path.exists():
        state["status"] = WorkflowStatus.FAILED
        state["failure_reason"] = f"File does not exist: {workflow_input.file_path}"
        return state
    
    # raw_text is already populated by create_initial_state() before the
    # graph starts, so there's nothing left to extract here.
    ui.display_processing(workflow_input.file_path)

    # Log ingestion
    logger.info(f"Ingesting receipt from: {workflow_input.file_path}")
    logger.info(f"Source: {workflow_input.source.value}")
    
    return state

