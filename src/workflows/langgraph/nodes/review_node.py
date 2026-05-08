"""Review node for LangGraph workflow - Human-in-the-loop."""

from datetime import datetime
from pathlib import Path
from typing import Optional

from workflows.langgraph.state import ReceiptWorkflowState
from domain.enums import WorkflowStatus
from domain.models.workflow import ReviewData
from domain.models.expense import ExpenseSummary, SplitDetail
from config import Config
from services.ui import ExpenseUI
from logger import get_logger

logger = get_logger(__name__)


def _extract_base_merchant_name(vendor: str) -> str:
    """
    Extract base merchant name from vendor string.
    Examples:
        "Amazon Order" -> "Amazon"
        "Walmart Order" -> "Walmart"
        "Electrical Bill" -> "Electrical"
        "Netflix" -> "Netflix"
    """
    # Common suffixes to remove
    suffixes = [' Order', ' Bill', ' Payment', ' Groceries', ' Premium']
    
    base_name = vendor
    for suffix in suffixes:
        if vendor.endswith(suffix):
            base_name = vendor[:-len(suffix)]
            break
    
    return base_name


def review_node(state: ReceiptWorkflowState) -> ReceiptWorkflowState:
    """
    Review node: Human-in-the-loop for reviewing and correcting receipt data.
    
    This node:
    1. Updates status to REVIEWING
    2. Uses ExpenseUI to display receipt and prompt for review
    3. Collects user inputs (edits, who paid, split confirmation)
    4. Creates ReviewData with user inputs
    5. Creates ExpenseSummary with final data for Notion
    6. Stores review_data and expense_summary in state
    
    Args:
        state: Current workflow state with receipt and validation_result
        
    Returns:
        Updated state with review_data and expense_summary
    """
    state["status"] = WorkflowStatus.REVIEWING
    
    try:
        # Get receipt from state
        receipt = state.get("receipt")
        if not receipt:
            raise ValueError("No receipt data found in state")
        
        # Initialize UI
        ui = ExpenseUI(
            your_name=Config.YOUR_NAME,
            partner_name=Config.PARTNER_NAME
        )
        
        # Convert receipt to dict format expected by UI
        workflow_input = state.get('workflow_input')
        pdf_filename = workflow_input.file_path if workflow_input else 'Unknown'
        
        # Extract base merchant name (e.g., "Amazon" from "Amazon Order")
        base_merchant_name = _extract_base_merchant_name(receipt.vendor)
        
        # Combine vendor and summary into merchant description format: "Vendor (Summary)"
        merchant_description = receipt.vendor
        if receipt.summary:
            merchant_description = f"{receipt.vendor} ({receipt.summary})"
        
        receipt_info = {
            'merchant_name': base_merchant_name,
            'description': merchant_description,
            'amount': receipt.total,
            'date': datetime.fromisoformat(receipt.date) if receipt.date else datetime.now(),
            'pdf_filename': pdf_filename
        }
        
        # Use UI to review and edit
        updated_receipt_info = ui.review_and_edit(receipt_info)
        
        # Validate that UI returned all required fields
        required_fields = ['amount', 'description', 'date']
        missing_fields = [field for field in required_fields if field not in updated_receipt_info]
        if missing_fields:
            raise ValueError(f"UI review_and_edit() did not return required fields: {', '.join(missing_fields)}")
        
        # Extract overrides
        amount_override = None
        merchant_override = None
        date_override = None
        
        try:
            if updated_receipt_info['amount'] != receipt.total:
                amount_override = updated_receipt_info['amount']
        except (KeyError, TypeError) as e:
            raise ValueError(f"Failed to process amount from UI: {e}. Updated receipt info: {updated_receipt_info}")
        
        try:
            # Compare against the combined merchant_description format
            original_description = receipt.vendor
            if receipt.summary:
                original_description = f"{receipt.vendor} ({receipt.summary})"
            
            if updated_receipt_info['description'] != original_description:
                merchant_override = updated_receipt_info['description']
        except (KeyError, TypeError) as e:
            raise ValueError(f"Failed to process description from UI: {e}. Updated receipt info: {updated_receipt_info}")
        
        try:
            original_date = datetime.fromisoformat(receipt.date) if receipt.date else datetime.now()
            if updated_receipt_info['date'] != original_date:
                date_override = updated_receipt_info['date']
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(f"Failed to process date from UI: {e}. Updated receipt info: {updated_receipt_info}")
        
        # Use UI to select who paid
        paid_by = ui.select_payer()
        
        # Use UI to confirm split
        final_amount = amount_override if amount_override else receipt.total
        use_split, split_percentage = ui.confirm_split(final_amount, Config.DEFAULT_SPLIT_PERCENTAGE)
        
        # Create ReviewData
        review_data = ReviewData(
            paid_by=paid_by,
            amount_override=amount_override,
            merchant_override=merchant_override,
            date_override=date_override,
            notes=None,  # UI doesn't collect notes in review_and_edit
            approved=True,  # If we got here, user approved
            reviewed_at=datetime.now()
        )

        # Determine final values (use overrides if present, otherwise use original)
        final_merchant_description = merchant_override if merchant_override else updated_receipt_info['description']
        final_date = date_override if date_override else updated_receipt_info['date']
        final_amount = amount_override if amount_override else updated_receipt_info['amount']
        
        # Get receipt file path
        receipt_file_path: Optional[Path] = None
        if workflow_input and workflow_input.file_path:
            receipt_file_path = Path(workflow_input.file_path)
        
        # Generate receipt filename
        receipt_filename = None
        if receipt_file_path:
            # Format: YYYY-MM-DD_Merchant_Description_$Amount.pdf
            date_str = final_date.strftime('%Y-%m-%d')
            merchant_clean = final_merchant_description.replace(' ', '_').replace('/', '_')
            receipt_filename = f"{date_str}_{merchant_clean}_${final_amount:.2f}.pdf"
        
        # Create splits list if split is enabled
        splits = None
        if use_split:
            # Determine who owes the split (the person who didn't pay)
            split_person = Config.PARTNER_NAME if paid_by == Config.YOUR_NAME else Config.YOUR_NAME
            
            # Generate split title with format: "Person's Vendor Split (Summary)"
            # Extract vendor and summary from final_merchant_description
            if '(' in final_merchant_description and ')' in final_merchant_description:
                # Format is "Vendor (Summary)"
                vendor_part = final_merchant_description.split('(')[0].strip()
                summary_part = final_merchant_description.split('(')[1].split(')')[0].strip()
                split_title = f"{split_person}'s {vendor_part} Split ({summary_part})"
            else:
                # No summary, just use vendor
                split_title = f"{split_person}'s {final_merchant_description} Split"
            
            splits = [
                SplitDetail(
                    person=split_person,
                    share_percent=split_percentage,
                    title=split_title
                )
            ]
        
        # Create ExpenseSummary for Notion submission
        expense_summary = ExpenseSummary(
            merchant_description=final_merchant_description,
            date=final_date,
            amount=final_amount,
            paid_by=paid_by,
            receipt_file_path=receipt_file_path,
            receipt_filename=receipt_filename,
            splits=splits
        )
        
        # Prepare data for UI preview
        expense_data = {
            'description': expense_summary.merchant_description,
            'date': expense_summary.date,
            'amount': expense_summary.amount,
            'paid_by': expense_summary.paid_by,
            'receipt_filename': expense_summary.receipt_filename
        }
        
        split_data = None
        if expense_summary.splits:
            split = expense_summary.splits[0]  # Get first split for preview
            split_data = {
                'title': split.title,
                'person': split.person,
                'share_percentage': split.share_percent
            }

        # Display final preview
        ui.display_final_preview(expense_data, split_data)
        
        # Confirm before sending to Notion
        ui.confirm_send_to_notion()
        
        # Store in state
        state["review_data"] = review_data
        state["expense_summary"] = expense_summary
        
        return state
        
    except KeyboardInterrupt:
        # User cancelled review
        state["status"] = WorkflowStatus.FAILED
        state["failure_reason"] = "Review cancelled by user"
        logger.info(f"\n\n❌ Review cancelled")
        return state
        
    except ValueError as e:
        # Handle validation errors with detailed message
        state["status"] = WorkflowStatus.FAILED
        state["failure_reason"] = f"Review validation error: {str(e)}"
        logger.error(f"\n✗ Review validation error: {e}")
        return state
        
    except Exception as e:
        # Handle unexpected review failures with full context
        import traceback
        error_details = traceback.format_exc()
        state["status"] = WorkflowStatus.FAILED
        state["failure_reason"] = f"Review failed: {str(e)}"
        logger.error(f"\n✗ Review error: {e}")
        logger.debug(f"\nFull error details:\n{error_details}")
        return state