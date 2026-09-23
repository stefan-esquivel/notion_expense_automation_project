"""Extract node for LangGraph workflow."""

from logging import Logger
from pathlib import Path
from typing import Any

from workflows.langgraph.state import ReceiptWorkflowState
from domain.enums import WorkflowStatus
from domain.models.recipts import Receipt
from services.pdf_extractor import PDFExtractor
from logger import get_logger

logger: Logger = get_logger(__name__)


def _resolve_file_path(state: ReceiptWorkflowState) -> Path:
    """Resolve and validate the PDF file path from workflow input.

    Raises:
        ValueError: If workflow_input or file_path is missing.
        FileNotFoundError: If the file does not exist on disk.
    """
    workflow_input = state.get("workflow_input")
    if not workflow_input or not workflow_input.file_path:
        raise ValueError("No file path provided in workflow input")
    path = Path(workflow_input.file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {path}")
    return path


def _build_receipt(extracted_data: dict[str, Any]) -> Receipt:
    """Convert raw extracted data dict into a validated Receipt model.

    Raises:
        ValueError: If amount is missing or non-positive.
    """
    amount = extracted_data.get("amount")
    if not amount or amount <= 0:
        raise ValueError(f"Invalid or missing amount in receipt: {amount}")
    return Receipt(
        recipt_id=extracted_data["order_id"],
        vendor=extracted_data["merchant_name"],
        transaction_type=extracted_data["transaction_type"],
        summary=extracted_data["summary"],
        date=extracted_data["date"].isoformat() if extracted_data["date"] else "",
        items=extracted_data["items"],
        total=amount,
    )


def extract_node(state: ReceiptWorkflowState) -> ReceiptWorkflowState:
    """Extract node: Extracts raw data from PDF receipt.

    1. Updates status to EXTRACTING
    2. Resolves and validates the file path
    3. Uses PDFExtractor to parse the PDF
    4. Converts extracted data to a Receipt model
    5. Handles errors gracefully

    Args:
        state: Current workflow state with workflow_input containing file_path

    Returns:
        Updated state with receipt data or failure information
    """
    state["status"] = WorkflowStatus.EXTRACTING
    file_path: Path | None = None

    try:
        file_path = _resolve_file_path(state)
        logger.info(f"Starting extraction for: {file_path.name}")

        extractor = PDFExtractor(use_llm_for_items=True)
        logger.info(f"📄 Extracting data from: {file_path.name}")
        extracted_data = extractor.parse_receipt(
            file_path, raw_text=state["workflow_input"].raw_text
        )

        receipt = _build_receipt(extracted_data)
        state["receipt"] = receipt
        logger.info(
            f"✓ Extraction complete: {receipt.vendor} "
            f"{receipt.transaction_type} - ${receipt.total:.2f}"
        )
        return state

    except (FileNotFoundError, ValueError) as e:
        state["status"] = WorkflowStatus.FAILED
        state["failure_reason"] = f"Extraction failed: {e}"
        file_name = file_path.name if file_path else "unknown"
        logger.error(f"✗ Extraction failed for {file_name}: {e}")
        return state
    except Exception as e:
        state["status"] = WorkflowStatus.FAILED
        state["failure_reason"] = f"Extraction failed: {e}"
        file_name = file_path.name if file_path else "unknown"
        logger.exception(f"✗ Unexpected extraction error for {file_name}: {e}")
        return state