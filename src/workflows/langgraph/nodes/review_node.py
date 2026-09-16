"""Review node for LangGraph workflow - Human-in-the-loop."""

from datetime import datetime
from pathlib import Path
from typing import Optional

from workflows.langgraph.state import ReceiptWorkflowState
from domain.enums import WorkflowStatus, ValidationSeverity
from domain.models.workflow import ReviewData, ValidationIssue
from domain.models.expense import ExpenseSummary, SplitDetail
from config import Config
from services.ui import ExpenseUI, OVERRIDE_SENTINEL
from logger import get_logger

logger = get_logger(__name__)

_MERCHANT_NAME_SUFFIXES = ("Order", "Bill", "Payment", "Premium", "Groceries", "Charge")


def _extract_base_merchant_name(name: str) -> str:
    """Strip a trailing transaction-type/plan word from a merchant name."""
    parts = name.strip().split()
    if len(parts) > 1 and parts[-1] in _MERCHANT_NAME_SUFFIXES:
        return " ".join(parts[:-1])
    return name.strip()


def _resolve_issues(
    state: ReceiptWorkflowState,
    ui: "ExpenseUI",
) -> bool:
    """Display tiered validation issues and collect fixes / acknowledgements.

    Prompts the user to correct every RED field and to explicitly acknowledge
    every YELLOW warning.  Writes corrections directly back onto
    ``state["receipt"]`` and accumulates acknowledged keys in
    ``state["acknowledged_warnings"]``.

    Returns:
        True  – user resolved / acknowledged everything and wants to continue.
        False – user cancelled (KeyboardInterrupt).
    """
    validation_result = state.get("validation_result")
    if not validation_result or not validation_result.issues:
        return True

    acknowledged: set = state.get("acknowledged_warnings") or set()
    receipt = state["receipt"]

    red_issues = [i for i in validation_result.issues if i.severity == ValidationSeverity.RED]
    yellow_issues = [
        i for i in validation_result.issues
        if i.severity == ValidationSeverity.YELLOW and i.key not in acknowledged
    ]

    if not red_issues and not yellow_issues:
        return True

    # ── Display the issue panel ──────────────────────────────────────────
    ui.display_validation_issues(red_issues, yellow_issues)

    # ── Fix each RED issue ───────────────────────────────────────────────
    for issue in red_issues:
        while True:
            fixed = ui.prompt_fix_red_issue(issue, receipt)
            if fixed is None:
                return False  # user cancelled

            # User chose to keep the current value and override the RED error.
            # Downgrade it to an acknowledged YELLOW so the loop can exit.
            if fixed == OVERRIDE_SENTINEL:
                acknowledged.add(issue.key)
                logger.info(f"⚠️  RED issue overridden by user: {issue.key} ({issue.message})")
                break

            # Apply the corrected value to the receipt
            if issue.field == "date":
                receipt.date = fixed
                break
            elif issue.field == "vendor":
                receipt.vendor = fixed
                break
            elif issue.field == "total":
                cleaned = fixed.replace("$", "").replace(",", "").strip()
                try:
                    receipt.total = float(cleaned)
                    break
                except ValueError:
                    from rich.console import Console
                    console = Console()
                    console.print("[bold red]❌ Invalid total amount. Please enter a valid number (e.g., 12.50).[/bold red]")

    state["receipt"] = receipt

    # ── Acknowledge each unacknowledged YELLOW issue ─────────────────────
    for issue in yellow_issues:
        ack = ui.prompt_acknowledge_yellow(issue)
        if ack is None:
            return False  # user cancelled
        if ack:
            acknowledged.add(issue.key)

    state["acknowledged_warnings"] = acknowledged
    return True


def review_node(state: ReceiptWorkflowState) -> ReceiptWorkflowState:
    """
    Review node: Human-in-the-loop for reviewing and correcting receipt data.

    On each pass through the validate→review loop this node:
    1. Shows the current RED / YELLOW issues and collects fixes / acknowledgements.
    2. Shows the receipt fields for general editing (description, amount, date).
    3. On the first pass only: collects who paid and the split configuration.
    4. Builds ExpenseSummary and ReviewData, then shows the final preview.
    5. Asks for explicit Notion confirmation.

    After the user makes edits the graph routes back to validate.  The loop
    exits (→ commit) only when is_green() returns True.
    """
    state["status"] = WorkflowStatus.REVIEWING

    try:
        receipt = state.get("receipt")
        if not receipt:
            raise ValueError("No receipt data found in state")

        ui = ExpenseUI(
            your_name=Config.YOUR_NAME,
            partner_name=Config.PARTNER_NAME,
        )

        # ── Step 1: resolve validation issues ────────────────────────────
        ok = _resolve_issues(state, ui)
        if not ok:
            state["status"] = WorkflowStatus.FAILED
            state["failure_reason"] = "Review cancelled by user"
            logger.info("\n\n❌ Review cancelled")
            return state

        # Re-read receipt after possible edits in _resolve_issues
        receipt = state["receipt"]

        # ── Step 2: general receipt edit ─────────────────────────────────
        workflow_input = state.get("workflow_input")
        pdf_filename = workflow_input.file_path if workflow_input else "Unknown"

        merchant_description = receipt.vendor
        if receipt.summary:
            merchant_description = f"{receipt.vendor} {receipt.transaction_type} ({receipt.summary})"

        receipt_info = {
            "merchant_name": receipt.vendor,
            "description": merchant_description,
            "amount": receipt.total,
            "date": datetime.fromisoformat(receipt.date) if receipt.date else datetime.now(),
            "pdf_filename": pdf_filename,
        }

        # Surface scan → augment narrative on the first pass only.
        # We detect "first pass" by checking whether expense_summary has been
        # built yet (it's None before the first review completes).
        is_first_pass = state.get("expense_summary") is None
        scan_results = state.get("scan_results")
        augment_results = state.get("augment_results")

        if is_first_pass and scan_results:
            originally_missing = list(scan_results.missing_fields)
            filled_fields = augment_results.filled_fields if augment_results else {}
            still_missing = augment_results.still_missing if augment_results else originally_missing

            field_values = {
                "vendor": receipt.vendor,
                "date": receipt.date,
                "total": receipt.total,
            }
            ui.display_scan_augment_summary(
                originally_missing=originally_missing,
                filled_fields=filled_fields,
                still_missing=still_missing,
                field_values=field_values,
            )

        updated_receipt_info = ui.review_and_edit(receipt_info)

        # Validate UI returned required fields
        required_fields = ["amount", "description", "date"]
        missing_fields = [f for f in required_fields if f not in updated_receipt_info]
        if missing_fields:
            raise ValueError(
                f"UI review_and_edit() did not return required fields: {', '.join(missing_fields)}"
            )

        # Detect overrides
        amount_override = None
        merchant_override = None
        date_override = None

        try:
            if updated_receipt_info["amount"] != receipt.total:
                amount_override = updated_receipt_info["amount"]
        except (KeyError, TypeError) as e:
            raise ValueError(f"Failed to process amount from UI: {e}")

        try:
            original_description = receipt.vendor
            if receipt.summary:
                original_description = f"{receipt.vendor} {receipt.transaction_type} ({receipt.summary})"
            if updated_receipt_info["description"] != original_description:
                merchant_override = updated_receipt_info["description"]
        except (KeyError, TypeError) as e:
            raise ValueError(f"Failed to process description from UI: {e}")

        try:
            original_date = datetime.fromisoformat(receipt.date) if receipt.date else datetime.now()
            if updated_receipt_info["date"] != original_date:
                date_override = updated_receipt_info["date"]
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(f"Failed to process date from UI: {e}")

        # Apply edits back onto the receipt so re-validation sees them
        if amount_override is not None:
            receipt.total = amount_override
        if date_override is not None:
            receipt.date = date_override.isoformat()
        if merchant_override is not None:
            receipt.vendor = merchant_override

        state["receipt"] = receipt

        # ── Step 3: payer + split (re-use from previous pass if present) ─
        existing_summary = state.get("expense_summary")

        if existing_summary:
            # Preserve payer / split choices from a previous loop iteration
            paid_by = existing_summary.paid_by
            use_split = existing_summary.splits is not None
            split_percentage = (
                existing_summary.splits[0].share_percent if existing_summary.splits else Config.DEFAULT_SPLIT_PERCENTAGE
            )
        else:
            paid_by = ui.select_payer()
            final_amount_for_split = amount_override if amount_override else receipt.total
            use_split, split_percentage = ui.confirm_split(final_amount_for_split, Config.DEFAULT_SPLIT_PERCENTAGE)

        # ── Step 4: build ExpenseSummary ──────────────────────────────────
        final_merchant_description = merchant_override if merchant_override else updated_receipt_info["description"]
        final_date = date_override if date_override else updated_receipt_info["date"]
        final_amount = amount_override if amount_override else updated_receipt_info["amount"]

        receipt_file_path: Optional[Path] = None
        if workflow_input and workflow_input.file_path:
            receipt_file_path = Path(workflow_input.file_path)

        receipt_filename = None
        if receipt_file_path:
            date_str = final_date.strftime("%Y-%m-%d")
            merchant_clean = final_merchant_description.replace(" ", "_").replace("/", "_")
            receipt_filename = f"{date_str}_{merchant_clean}_${final_amount:.2f}.pdf"

        splits = None
        if use_split:
            split_person = Config.PARTNER_NAME if paid_by == Config.YOUR_NAME else Config.YOUR_NAME

            if "(" in final_merchant_description and ")" in final_merchant_description:
                vendor_part = final_merchant_description.split("(")[0].strip()
                summary_part = final_merchant_description.split("(")[1].split(")")[0].strip()
                split_title = f"{split_person}'s {vendor_part} Split ({summary_part})"
            else:
                split_title = f"{split_person}'s {final_merchant_description} Split"

            splits = [
                SplitDetail(
                    person=split_person,
                    share_percent=split_percentage,
                    title=split_title,
                )
            ]

        expense_summary = ExpenseSummary(
            merchant_description=final_merchant_description,
            date=final_date,
            amount=final_amount,
            paid_by=paid_by,
            receipt_file_path=receipt_file_path,
            receipt_filename=receipt_filename,
            splits=splits,
        )

        # ── Step 5: preview + Notion confirmation ─────────────────────────
        expense_data = {
            "description": expense_summary.merchant_description,
            "date": expense_summary.date,
            "amount": expense_summary.amount,
            "paid_by": expense_summary.paid_by,
            "receipt_filename": expense_summary.receipt_filename,
        }

        split_data = None
        if expense_summary.splits:
            split = expense_summary.splits[0]
            split_data = {
                "title": split.title,
                "person": split.person,
                "share_percentage": split.share_percent,
            }

        ui.display_final_preview(expense_data, split_data)

        user_confirmed = ui.confirm_send_to_notion()
        if not user_confirmed:
            state["status"] = WorkflowStatus.FAILED
            state["failure_reason"] = "User declined to send data to Notion"
            logger.info("\n\n❌ User declined to send data to Notion")
            return state

        # ── Persist ───────────────────────────────────────────────────────
        state["review_data"] = ReviewData(
            paid_by=paid_by,
            amount_override=amount_override,
            merchant_override=merchant_override,
            date_override=date_override,
            notes=None,
            approved=True,
            reviewed_at=datetime.now(),
        )
        state["expense_summary"] = expense_summary

        return state

    except KeyboardInterrupt:
        state["status"] = WorkflowStatus.FAILED
        state["failure_reason"] = "Review cancelled by user"
        logger.info("\n\n❌ Review cancelled")
        return state

    except ValueError as e:
        state["status"] = WorkflowStatus.FAILED
        state["failure_reason"] = f"Review validation error: {str(e)}"
        logger.error(f"\n✗ Review validation error: {e}")
        return state

    except Exception as e:
        import traceback
        state["status"] = WorkflowStatus.FAILED
        state["failure_reason"] = f"Review failed: {str(e)}"
        logger.error(f"\n✗ Review error: {e}")
        logger.debug(f"\nFull error details:\n{traceback.format_exc()}")
        return state
