from logging import Logger
from pathlib import Path
from datetime import datetime
from uuid import uuid4
from services.submission_journal import SubmissionJournal, file_sha256, submission_scope
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
    journal: SubmissionJournal,
    submission_id: str,
) -> tuple[str, list[str]]:
    """Create the expense entry and any split entries in Notion."""
    expense_page_id = journal.run(submission_id, 'expense', lambda: notion_client.create_expense_entry(
        merchant_description=expense_summary.merchant_description,
        date=expense_summary.date,
        amount=expense_summary.amount,
        paid_by=expense_summary.paid_by,
        receipt_file_path=expense_summary.receipt_file_path,
        receipt_filename=expense_summary.receipt_filename,
    ), creates_page=True)
    split_ids = []
    for index, split in enumerate(expense_summary.splits or []):
        split_id = journal.run(submission_id, f'split:{index}', lambda: notion_client.create_split_entry(
            split.title, split.person, split.share_percent, expense_page_id, link=False), creates_page=True)
        split_ids.append(split_id)
        journal.run(submission_id, f'link:{index}', lambda: notion_client.link_split(expense_page_id, split_id))
    logger.info(f"Successfully committed expense to Notion (page_id: {expense_page_id})")
    return expense_page_id, split_ids


def _organize_receipt_file(expense_summary, journal, submission_id, receipt_hash) -> Path:
    if not expense_summary.receipt_file_path:
        logger.warning("No receipt file path found, skipping file organization")
        return Path("unknown")

    source = expense_summary.receipt_file_path
    merchant_name = expense_summary.merchant_description.split("(")[0].strip()
    organizer = FileOrganizer(processed_folder=Config.PROCESSED_FOLDER)
    arguments = dict(source_path=source, date=expense_summary.date,
                     merchant_name=merchant_name, description=expense_summary.merchant_description,
                     amount=expense_summary.amount)
    destination = journal.archive_destination(submission_id, lambda: organizer.plan_destination(**arguments))
    if destination.exists():
        if file_sha256(destination) != receipt_hash:
            raise RuntimeError(f'Archive destination has different content: {destination}; reconcile before retrying')
        # A previous move/copy may have finished before progress was recorded.
        if source.exists() and source.resolve() != destination.resolve():
            if file_sha256(source) != receipt_hash:
                raise RuntimeError('Receipt content changed before archiving')
            source.unlink()
        return destination
    if file_sha256(source) != receipt_hash:
        raise RuntimeError('Receipt content changed before archiving')
    organized_path = organizer.organize_file(**arguments, destination_path=destination)
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

        scope = submission_scope(Config.ENVIRONMENT, Config.EXPENSE_TABLE_DATABASE_ID,
                                 Config.SPLIT_DETAILS_DATABASE_ID)
        with SubmissionJournal(Config.SUBMISSION_JOURNAL_PATH) as journal:
            source = expense_summary.receipt_file_path
            if source:
                receipt_hash = (file_sha256(source) if source.exists() else
                                journal.receipt_hash_for_missing_source(scope, source))
            else:
                # Non-file callers must retain this token when resuming a submission.
                receipt_hash = state.get("submission_token") or str(uuid4())
                state["submission_token"] = receipt_hash
            payload = expense_summary.model_dump(mode='json', exclude={'receipt_file_path', 'receipt_filename'})
            payload['user_ids'] = [Config.YOUR_USER_ID, Config.PARTNER_USER_ID]
            payload['relation_property'] = Config.EXPENSE_RELATION_PROPERTY
            payload['balance_page_id'] = Config.BALANCES_PAGE_ID.replace('-', '').lower()
            submission_id = journal.prepare(scope, receipt_hash, payload, source)
            state["submission_id"] = submission_id
            expense_page_id, split_ids = _commit_to_notion(notion_client, expense_summary, journal, submission_id)
            organized_path = _organize_receipt_file(expense_summary, journal, submission_id, receipt_hash)
            state["results"] = WorkflowResults(
                notion_expense_id=expense_page_id,
                notion_split_ids=split_ids,
                archive_path=organized_path,
                timestamp=datetime.now(),
            )
        state["failure_reason"] = None
        state["status"] = WorkflowStatus.COMPLETED

    except Exception as e:
        logger.error(f"Failed to commit to Notion: {str(e)}")
        state["status"] = WorkflowStatus.FAILED
        state["failure_reason"] = f"Failed to commit to notion: {str(e)}"
        return state

    return state
