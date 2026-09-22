from config import Config
from services.ui import ExpenseUI
from services.pdf_extractor import PDFExtractor
from services.submission_journal import SubmissionJournal, file_sha256, submission_scope
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
    3. Skips completed duplicates before parsing or review
    4. Populates raw text for extraction
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
    
    try:
        if not Config.QA_SKIP_COMMIT:
            scope = submission_scope(Config.ENVIRONMENT, Config.EXPENSE_TABLE_DATABASE_ID,
                                     Config.SPLIT_DETAILS_DATABASE_ID)
            existing_id = SubmissionJournal(Config.SUBMISSION_JOURNAL_PATH).find_completed(
                scope, file_sha256(file_path))
            if existing_id:
                state["status"] = WorkflowStatus.DUPLICATE
                state["duplicate_expense_id"] = existing_id
                state["failure_reason"] = None
                logger.info(f"Already submitted; skipping {file_path.name} (Notion page: {existing_id})")
                return state
        if not workflow_input.raw_text:
            workflow_input.raw_text = PDFExtractor().extract_text(file_path)
    except Exception as error:
        state["status"] = WorkflowStatus.FAILED
        state["failure_reason"] = f"Ingestion failed: {error}"
        logger.error(state["failure_reason"])
        return state

    ui.display_processing(workflow_input.file_path)

    # Log ingestion
    logger.info(f"Ingesting receipt from: {workflow_input.file_path}")
    logger.info(f"Source: {workflow_input.source.value}")
    
    return state

