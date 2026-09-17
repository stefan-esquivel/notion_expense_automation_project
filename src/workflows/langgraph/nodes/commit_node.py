from logging import Logger
from pathlib import Path
from datetime import datetime
from config import Config
from domain.enums import WorkflowStatus
from services.notion_api import NotionExpenseClient
from services.file_organizer import FileOrganizer
from workflows.langgraph.state import ReceiptWorkflowState
from domain.models.expense import ExpenseSummary
from domain.models.workflow import WorkflowResults
from logger import get_logger

logger: Logger = get_logger(__name__)

QA_MOCK_EXPENSE_ID = "0" * 32


def _commit_to_notion(
    notion_client: NotionExpenseClient,
    expense_summary: ExpenseSummary,
) -> tuple[str, list[str]]:
    """Create the expense entry and any split entries in Notion."""
    expense_page_id = notion_client.create_expense_entry(
        merchant_description=expense_summary.merchant_description,
        date=expense_summary.date,
        amount=expense_summary.amount,
        paid_by=expense_summary.paid_by,
        receipt_file_path=expense_summary.receipt_file_path,
        receipt_filename=expense_summary.receipt_filename,
    )
    split_ids = [
        notion_client.create_split_entry(
            split.title, split.person, split.share_percent, expense_page_id
        )
        for split in (expense_summary.splits or [])
    ]
    logger.info(f"Successfully committed expense to Notion (page_id: {expense_page_id})")
    return expense_page_id, split_ids


def _organize_receipt_file(expense_summary: ExpenseSummary) -> Path:
    """Move the receipt file into the processed folder hierarchy."""
    if not expense_summary.receipt_file_path:
        logger.warning("No receipt file path found, skipping file organization")
        return Path("unknown")

    merchant_name = expense_summary.merchant_description.split("(")[0].strip()
    organized_path = FileOrganizer(
        processed_folder=Config.PROCESSED_FOLDER
    ).organize_file(
        source_path=expense_summary.receipt_file_path,
        date=expense_summary.date,
        merchant_name=merchant_name,
        description=expense_summary.merchant_description,
        amount=expense_summary.amount,
    )
    logger.info(f"File organized to: {organized_path}")
    return organized_path


def commit_node(state: ReceiptWorkflowState) -> ReceiptWorkflowState:
    """Commit the receipt to the database."""

    state["status"] = WorkflowStatus.SUBMITTING

    try:
        if Config.QA_SKIP_COMMIT:
            logger.info("⚠️  QA_SKIP_COMMIT enabled - Skipping Notion commit and file moving")
            logger.info("✓ Workflow completed successfully (QA mode - no commit)")
            state["status"] = WorkflowStatus.COMPLETED
            state["results"] = WorkflowResults(
                notion_expense_id=QA_MOCK_EXPENSE_ID,
                notion_split_ids=[],
                archive_path=Path("qa-skipped"),
                timestamp=datetime.now(),
            )
            return state

        Config.validate()

        notion_client = NotionExpenseClient(
            Config.NOTION_API_TOKEN,
            Config.EXPENSE_TABLE_DATABASE_ID,
            split_db_id=Config.SPLIT_DETAILS_DATABASE_ID,
            balance_page_id=Config.BALANCES_PAGE_ID,
        )

        expense_summary = state.get("expense_summary")
        if not expense_summary:
            raise ValueError("No expense_summary found in state")

        logger.info("Creating Notion entries")

        expense_page_id, split_ids = _commit_to_notion(notion_client, expense_summary)
        organized_path = _organize_receipt_file(expense_summary)

        state["results"] = WorkflowResults(
            notion_expense_id=expense_page_id,
            notion_split_ids=split_ids,
            archive_path=organized_path,
            timestamp=datetime.now(),
        )
        state["status"] = WorkflowStatus.COMPLETED

    except Exception as e:
        logger.error(f"Failed to commit to Notion: {str(e)}")
        state["status"] = WorkflowStatus.FAILED
        state["failure_reason"] = f"Failed to commit to notion: {str(e)}"
        return state

    return state
