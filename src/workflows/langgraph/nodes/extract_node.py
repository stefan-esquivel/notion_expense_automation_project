"""Extract node for LangGraph workflow."""

from logging import Logger


from pathlib import Path
from uuid import uuid4

from workflows.langgraph.state import ReceiptWorkflowState
from domain.enums import WorkflowStatus
from domain.models.recipts import Receipt
from services.pdf_extractor import PDFExtractor
from logger import get_logger

logger: Logger = get_logger(__name__)


def extract_node(state: ReceiptWorkflowState) -> ReceiptWorkflowState:
    """
    Extract node: Extracts raw data from PDF receipt.
    
    This node:
    1. Updates status to EXTRACTING
    2. Uses PDFExtractor to parse the PDF
    3. Converts extracted data to Receipt model
    4. Handles errors gracefully
    
    Args:
        state: Current workflow state with workflow_input containing file_path
        
    Returns:
        Updated state with receipt data or failure information
    """
    # Update status
    state["status"] = WorkflowStatus.EXTRACTING
    
    file_path = None
    try:
        # Get file path from workflow input
        workflow_input = state.get("workflow_input")
        if not workflow_input or not workflow_input.file_path:
            raise ValueError("No file path provided in workflow input")
        
        file_path = Path(workflow_input.file_path)
        logger.info(f"Starting extraction for: {file_path.name}")
        
        # Validate file exists
        if not file_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")
        
        # Initialize PDF extractor
        extractor = PDFExtractor(use_llm_for_items=True)
        
        # Extract data from PDF
        logger.info(f"📄 Extracting data from: {file_path.name}")
        logger.debug(f"Using PDFExtractor with LLM enabled")
        extracted_data = extractor.parse_receipt(file_path)
        logger.debug(f"Extracted {len(extracted_data.get('items', []))} items")
        
        # Convert to Receipt model
        # Validate that we have a valid amount
        amount = extracted_data.get("amount")
        if not amount or amount <= 0:
            raise ValueError(f"Invalid or missing amount in receipt: {amount}")
        
        receipt = Receipt(
            recipt_id=extracted_data["order_id"],
            vendor=extracted_data["merchant_name"],
            transaction_type=extracted_data["transaction_type"],
            summary=extracted_data["summary"],
            date=extracted_data["date"].isoformat() if extracted_data["date"] else "",
            items=extracted_data["items"],
            total=amount
        )
        
        # Store receipt in state
        state["receipt"] = receipt
        
        logger.info(f"✓ Extraction complete: {receipt.vendor} {receipt.transaction_type} - ${receipt.total:.2f}")
        
        return state
        
    except Exception as e:
        # Handle extraction failure
        state["status"] = WorkflowStatus.FAILED
        state["failure_reason"] = f"Extraction failed: {str(e)}"
        file_name = file_path.name if file_path else "unknown file"
        logger.error(f"✗ Extraction failed for {file_name}: {e}", exc_info=True)
        return state