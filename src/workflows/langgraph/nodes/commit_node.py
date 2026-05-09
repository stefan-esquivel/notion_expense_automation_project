from logging import Logger
from pathlib import Path
from datetime import datetime
from config import Config
from domain.enums import WorkflowStatus
from services.notion_api import NotionExpenseClient
from services.file_organizer import FileOrganizer
from services.ui import ExpenseUI
from workflows.langgraph.state import ReceiptWorkflowState
from domain.models.workflow import WorkflowResults
from logger import get_logger

logger: Logger = get_logger(__name__)

def commit_node(state: ReceiptWorkflowState) -> ReceiptWorkflowState:
    """Commit the receipt to the database."""

    state["status"] = WorkflowStatus.SUBMITTING

    try:
        # Check if QA_SKIP_COMMIT is enabled
        if Config.QA_SKIP_COMMIT:
            logger.info("⚠️  QA_SKIP_COMMIT enabled - Skipping Notion commit and file moving")
            logger.info("✓ Workflow completed successfully (QA mode - no commit)")
            
            # Mark as completed without actually committing
            # Use valid 32-character mock UUIDs for QA mode
            state["status"] = WorkflowStatus.COMPLETED
            state["results"] = WorkflowResults(
                notion_expense_id="00000000000000000000000000000000",  # 32-char mock UUID
                notion_split_ids=[],
                archive_path=Path("qa-skipped"),
                timestamp=datetime.now()
            )
            return state
        
        # Validate required config values
        if not Config.NOTION_API_TOKEN:
            raise ValueError("NOTION_API_TOKEN is not configured")
        if not Config.EXPENSE_TABLE_DATABASE_ID:
            raise ValueError("EXPENSE_TABLE_DATABASE_ID is not configured")
        if not Config.SPLIT_DETAILS_DATABASE_ID:
            raise ValueError("SPLIT_DETAILS_DATABASE_ID is not configured")
        if not Config.BALANCES_PAGE_ID:
            raise ValueError("BALANCES_PAGE_ID is not configured")

        notion_client = NotionExpenseClient(
            Config.NOTION_API_TOKEN,
            Config.EXPENSE_TABLE_DATABASE_ID,
            split_db_id=Config.SPLIT_DETAILS_DATABASE_ID,
            balance_page_id=Config.BALANCES_PAGE_ID
        )

        ui = ExpenseUI(
            your_name=Config.YOUR_NAME,
            partner_name=Config.PARTNER_NAME,
            notion_client=notion_client
        )

        logger.info("Creating Notion entries")

        # Get data from state
        expense_summary = state.get("expense_summary")
        
        if not expense_summary:
            raise ValueError("No expense_summary found in state")

        # Create expense entry in Notion
        expense_page_id = notion_client.create_expense_entry(
            merchant_description=expense_summary.merchant_description,
            date=expense_summary.date,
            amount=expense_summary.amount,
            paid_by=expense_summary.paid_by,
            receipt_file_path=expense_summary.receipt_file_path,
            receipt_filename=expense_summary.receipt_filename
        )
        
        # Create split entries if present
        split_ids = []
        if expense_summary.splits:
            for split in expense_summary.splits:
                split_id = notion_client.create_split_entry(
                    split.title,
                    split.person,
                    split.share_percent,
                    expense_page_id
                )
                split_ids.append(split_id)

        logger.info(f"Successfully committed expense to Notion (page_id: {expense_page_id})")

        # Organize the file (move to processed folder)
        if expense_summary.receipt_file_path:
            file_organizer = FileOrganizer(
                processed_folder=Config.PROCESSED_FOLDER
            )
            
            # Extract vendor name (part before parentheses) for folder organization
            # Example: "Amazon Order (Pint Glasses)" -> "Amazon Order"
            merchant_name_for_folder = expense_summary.merchant_description
            if '(' in expense_summary.merchant_description:
                merchant_name_for_folder = expense_summary.merchant_description.split('(')[0].strip()
            
            organized_path = file_organizer.organize_file(
                source_path=expense_summary.receipt_file_path,
                date=expense_summary.date,
                merchant_name=merchant_name_for_folder,
                description=expense_summary.merchant_description,
                amount=expense_summary.amount
            )
            
            logger.info(f"File organized to: {organized_path}")
        else:
            organized_path = Path("unknown")
            logger.warning("No receipt file path found, skipping file organization")

        # Store results in state
        state["results"] = WorkflowResults(
            notion_expense_id=expense_page_id,
            notion_split_ids=split_ids,
            archive_path=organized_path,
            timestamp=datetime.now()
        )
        
        state["status"] = WorkflowStatus.COMPLETED

    except Exception as e:
        logger.error(f"Failed to commit to Notion: {str(e)}")
        state["status"] = WorkflowStatus.FAILED
        state["failure_reason"] = f"Failed to commit to notion: {str(e)}"
        return state

    return state