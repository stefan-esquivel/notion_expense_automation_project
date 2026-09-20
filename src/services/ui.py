"""User interface module for interactive prompts and displays."""
from datetime import datetime
from typing import TYPE_CHECKING, Dict, Any, Optional, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
import inquirer
from config import Config

if TYPE_CHECKING:
    from domain.models.workflow import ValidationIssue
    from domain.models.recipts import Receipt


console = Console()

# Returned by prompt_fix_red_issue when the user chooses to keep the current
# value and override the RED error (downgrades it to an acknowledged YELLOW).
OVERRIDE_SENTINEL = "__OVERRIDE__"


class ExpenseUI:
    """Handle all user interface interactions."""
    
    def __init__(self, your_name: str, partner_name: str, notion_client=None):
        self.your_name = your_name
        self.partner_name = partner_name
        self.notion_client = notion_client
    
    def display_welcome(self):
        """Display welcome message."""
        console.print("\n[bold cyan]═══════════════════════════════════════════════════════[/bold cyan]")
        console.print("[bold cyan]   Notion Expense Automation System[/bold cyan]")
        console.print("[bold cyan]═══════════════════════════════════════════════════════[/bold cyan]\n")
    
    def display_extracted_info(self, receipt_info: Dict[str, Any]):
        """Display extracted receipt information."""
        table = Table(title="📄 Extracted Receipt Information", show_header=True)
        table.add_column("Field", style="cyan", width=20)
        table.add_column("Value", style="green")
        
        table.add_row("Merchant", receipt_info.get('merchant_name', 'Unknown'))
        table.add_row("Description", receipt_info.get('description', 'N/A'))
        
        amount = receipt_info.get('amount')
        if amount:
            table.add_row("Amount", f"CA${amount:.2f}")
        else:
            table.add_row("Amount", "[red]Not detected[/red]")
        
        date = receipt_info.get('date')
        if date:
            table.add_row("Date", date.strftime('%B %d, %Y'))
        else:
            table.add_row("Date", "[red]Not detected[/red]")
        
        table.add_row("PDF File", receipt_info.get('pdf_filename', 'N/A'))
        
        console.print("\n")
        console.print(table)
        console.print("\n")
    
    def display_validation_issues(
        self,
        red_issues: "List[ValidationIssue]",
        yellow_issues: "List[ValidationIssue]",
    ) -> None:
        """Display a colour-coded panel of RED (blocking) and YELLOW (advisory) issues.

        Called at the top of every review pass so the user always sees the
        current state before being asked to fix or acknowledge anything.
        """
        if not red_issues and not yellow_issues:
            console.print("\n[bold green]✅ All validation checks passed — receipt is GREEN[/bold green]\n")
            return

        lines = []
        if red_issues:
            lines.append("[bold red]🔴 BLOCKING — must be fixed before commit:[/bold red]")
            for issue in red_issues:
                field_tag = f" [dim](field: {issue.field})[/dim]" if issue.field else ""
                lines.append(f"  [red]● {issue.message}[/red]{field_tag}")
        if yellow_issues:
            if lines:
                lines.append("")
            lines.append("[bold yellow]🟡 ADVISORY — must be acknowledged before commit:[/bold yellow]")
            for issue in yellow_issues:
                field_tag = f" [dim](field: {issue.field})[/dim]" if issue.field else ""
                lines.append(f"  [yellow]● {issue.message}[/yellow]{field_tag}")

        console.print(
            Panel(
                "\n".join(lines),
                title="[bold]Validation Issues[/bold]",
                border_style="red" if red_issues else "yellow",
                padding=(1, 2),
            )
        )
        console.print()

    def prompt_fix_red_issue(
        self,
        issue: "ValidationIssue",
        receipt: "Receipt",
    ) -> Optional[str]:
        """Prompt the user to provide a corrected value for a RED issue.

        Returns:
            str  – the corrected value to apply to the receipt.
            ``OVERRIDE_SENTINEL`` – the user chose to keep the current value
                and override the error (converts the RED to an acknowledged YELLOW).
            None – the user cancelled (KeyboardInterrupt).

        The caller is responsible for applying the value to the receipt.
        """
        console.print(f"[bold red]🔴 Fix required:[/bold red] {issue.message}")

        if issue.field == "date":
            current = receipt.date or ""
            try:
                new_val = Prompt.ask(
                    "  Enter corrected date (YYYY-MM-DD), or press Enter to override with a warning",
                    default=current,
                )
            except KeyboardInterrupt:
                return None
            # User left the value unchanged — offer to override rather than fix
            if new_val == current:
                try:
                    confirmed = Confirm.ask(
                        "  ⚠️  Keep the current value and proceed with a warning?",
                        default=False,
                    )
                except KeyboardInterrupt:
                    return None
                if confirmed:
                    return OVERRIDE_SENTINEL
                # User said no — loop back (return the unchanged value so the
                # caller's while-loop will re-prompt)
                return current
            return new_val

        if issue.field == "vendor":
            current = receipt.vendor or ""
            try:
                new_val = Prompt.ask("  Enter corrected merchant name", default=current)
            except KeyboardInterrupt:
                return None
            return new_val

        if issue.field == "total":
            current = str(receipt.total) if receipt.total else "0.0"
            try:
                new_val = Prompt.ask("  Enter corrected amount (number only)", default=current)
            except KeyboardInterrupt:
                return None
            return new_val

        # Generic fallback for any future RED field
        try:
            new_val = Prompt.ask(f"  Enter corrected value for '{issue.field}'")
        except KeyboardInterrupt:
            return None
        return new_val

    def prompt_acknowledge_yellow(
        self,
        issue: "ValidationIssue",
    ) -> Optional[bool]:
        """Ask the user to acknowledge a YELLOW advisory issue.

        Returns True if acknowledged, False if they want to fix it instead
        (which will cause re-validation), or None if they cancelled.
        """
        console.print(f"[bold yellow]🟡 Advisory:[/bold yellow] {issue.message}")
        try:
            ack = Confirm.ask(
                "  Acknowledge and proceed with this warning?",
                default=True,
            )
        except KeyboardInterrupt:
            return None
        return ack

    def display_scan_augment_summary(
        self,
        originally_missing: List[str],
        filled_fields: Dict[str, str],
        still_missing: List[str],
        field_values: Dict[str, Any],
    ) -> None:
        """Display a narrative panel summarising the scan → augment pipeline.

        Shows three sections in one panel:
          • What scan detected as missing
          • What augment managed to deduce automatically
          • What is still missing and needs the user to provide it

        Args:
            originally_missing: Fields scan flagged as missing before augment ran.
            filled_fields:      Maps field name → method used to auto-fill it.
            still_missing:      Fields augment could not fill; user must provide.
            field_values:       Maps field name → current value on the receipt.
        """
        lines: List[str] = []

        # ── Section 1: what scan found ──────────────────────────────────
        if originally_missing:
            lines.append("[bold cyan]🔎 Scan detected missing fields:[/bold cyan]")
            for field in originally_missing:
                lines.append(f"  [cyan]● {field}[/cyan]")
        else:
            lines.append("[bold green]🔎 Scan found all required fields present[/bold green]")

        lines.append("")

        # ── Section 2: what augment deduced ─────────────────────────────
        if filled_fields:
            lines.append("[bold green]✅ Augment successfully deduced:[/bold green]")
            for field, method in filled_fields.items():
                value = field_values.get(field, "N/A")
                friendly_method = "LLM extraction" if method == "llm_extraction" else method
                lines.append(
                    f"  [green]● {field}[/green]"
                    f"  →  [bold]{value}[/bold]"
                    f"  [dim](via {friendly_method})[/dim]"
                )
            lines.append(
                "\n[dim italic]  These values were deduced automatically — "
                "please verify and correct them below if wrong.[/dim italic]"
            )
        elif originally_missing:
            lines.append("[yellow]⚠️  Augment could not deduce any missing fields automatically.[/yellow]")

        # ── Section 3: still missing ─────────────────────────────────────
        if still_missing:
            lines.append("")
            lines.append("[bold red]❌ Still missing — you must provide these during review:[/bold red]")
            for field in still_missing:
                lines.append(f"  [red]● {field}[/red]")

        # Choose border colour: red if anything is still missing, green if all resolved
        border = "red" if still_missing else ("green" if filled_fields else "cyan")

        console.print(
            Panel(
                "\n".join(lines),
                title="[bold]Scan & Augment Summary[/bold]",
                border_style=border,
                padding=(1, 2),
            )
        )
        console.print()

    def _print_edit_diff(self, original: Dict[str, Any], updated: Dict[str, Any]) -> None:
        """Print a before/after table for any fields that changed."""
        editable_fields = ["description", "amount", "date"]
        changed = [
            (field, original.get(field), updated.get(field))
            for field in editable_fields
            if str(original.get(field)) != str(updated.get(field))
        ]
        if not changed:
            console.print("\n[dim]No fields were changed.[/dim]\n")
            return

        table = Table(title="📝 Review Your Changes", show_header=True, header_style="bold")
        table.add_column("Field", style="bold")
        table.add_column("Before (scanned)", style="red")
        table.add_column("After (your edit)", style="green")
        for field, before, after in changed:
            before_str = before.strftime('%Y-%m-%d') if isinstance(before, datetime) else str(before)
            after_str = after.strftime('%Y-%m-%d') if isinstance(after, datetime) else str(after)
            table.add_row(field.capitalize(), before_str, after_str)

        unchanged = [f for f in editable_fields if f not in {r[0] for r in changed}]
        console.print(table)
        if unchanged:
            console.print(f"[dim]Unchanged: {', '.join(unchanged)}[/dim]\n")

    def review_and_edit(self, receipt_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Allow user to review and edit extracted information.
        Returns updated receipt_info.
        """
        self.display_extracted_info(receipt_info)

        # Ask if user wants to edit
        if not Confirm.ask("📝 Do you want to edit any information?", default=False):
            return receipt_info

        # Snapshot originals before any edits
        original = {
            "description": receipt_info.get("description", ""),
            "amount": receipt_info.get("amount", 0.0),
            "date": receipt_info.get("date", datetime.now()),
        }
        updated = dict(receipt_info)

        # Edit description
        current_desc = updated.get('description', '')
        new_desc = Prompt.ask(
            "Enter description",
            default=current_desc
        )
        updated['description'] = new_desc

        # Edit amount
        current_amount = updated.get('amount', 0.0)
        new_amount = Prompt.ask(
            "Enter amount (without CA$ or $)",
            default=str(current_amount)
        )
        try:
            updated['amount'] = float(new_amount)
        except ValueError:
            console.print("[yellow]Invalid amount, keeping original[/yellow]")

        # Edit date
        current_date = updated.get('date', datetime.now())
        new_date_str = Prompt.ask(
            "Enter date (YYYY-MM-DD)",
            default=current_date.strftime('%Y-%m-%d')
        )
        try:
            updated['date'] = datetime.strptime(new_date_str, '%Y-%m-%d')
        except ValueError:
            console.print("[yellow]Invalid date format, keeping original[/yellow]")

        # Show before/after diff and confirm
        self._print_edit_diff(original, updated)
        if Confirm.ask("Apply these changes?", default=True):
            receipt_info.update(updated)
            console.print("\n[green]✓ Information updated[/green]\n")
        else:
            console.print("\n[dim]Changes discarded — keeping original values.[/dim]\n")

        return receipt_info
    
    def select_payer(self) -> str:
        """Prompt user to select who paid for the expense."""
        questions = [
            inquirer.List(
                'payer',
                message="💳 Who paid for this expense?",
                choices=[self.your_name, self.partner_name],
            ),
        ]
        answers = inquirer.prompt(questions)
        if answers is None:
            raise KeyboardInterrupt("User cancelled selection")
        return answers['payer']
    
    def confirm_split(self, amount: float, split_percentage: float) -> tuple[bool, float]:
        """
        Confirm split amount and allow override.
        Returns: (use_split, split_amount)
        """
        split_amount = amount * (split_percentage / 100)
        
        console.print(f"\n💰 Total Amount: [bold]CA${amount:.2f}[/bold]")
        console.print(f"📊 Default Split ({split_percentage}%): [bold]CA${split_amount:.2f}[/bold] each\n")
        
        # Ask if they want to use default split
        use_default = Confirm.ask("Use 50/50 split?", default=True)
        
        if use_default:
            return True, split_percentage
        
        # Ask if they want custom split or no split
        questions = [
            inquirer.List(
                'split_type',
                message="How should this expense be handled?",
                choices=[
                    'Custom split percentage',
                    'No split (100% individual expense)'
                ],
            ),
        ]
        answers = inquirer.prompt(questions)
        
        if answers is None:
            raise KeyboardInterrupt("User cancelled selection")
        
        if answers['split_type'] == 'No split (100% individual expense)':
            return False, 0.0
        
        # Custom split amount
        custom_percentage = Prompt.ask(
            "Enter custom split percentage for the other person",
            default=str(split_percentage)
        )
        try:
            return True, float(custom_percentage)
        except ValueError:
            console.print("[yellow]Invalid amount, using default split[/yellow]")
            return True, split_percentage
    
    def display_final_preview(
        self,
        expense_data: Dict[str, Any],
        split_data: Optional[Dict[str, Any]]
    ):
        """Display final preview before sending to Notion."""
        console.print("\n[bold cyan]═══════════════════════════════════════════════════════[/bold cyan]")
        console.print("[bold cyan]   Final Preview - Ready to Send to Notion[/bold cyan]")
        console.print("[bold cyan]═══════════════════════════════════════════════════════[/bold cyan]\n")
        
        # Get emoji for expense entry
        merchant_emoji = Config.get_merchant_emoji(expense_data['description'])
        
        # Expense entry
        expense_table = Table(title="📊 Expense Table Entry", show_header=True)
        expense_table.add_column("Field", style="cyan")
        expense_table.add_column("Value", style="green")
        
        expense_table.add_row("Icon", merchant_emoji)
        expense_table.add_row("Merchant/Description", expense_data['description'])
        expense_table.add_row("Date", expense_data['date'].strftime('%B %d, %Y'))
        expense_table.add_row("Amount", f"CA${expense_data['amount']:.2f}")
        
        # Resolve person name from user ID if notion_client is available
        paid_by_display = expense_data['paid_by']
        if self.notion_client and 'paid_by_user_id' in expense_data:
            paid_by_display = self.notion_client.get_username_from_id(expense_data['paid_by_user_id'])
        
        expense_table.add_row("Paid By", paid_by_display)

        expense_table.add_row("Receipt", expense_data.get('receipt_filename', 'N/A'))
        
        console.print(expense_table)
        console.print()
        
        # Split entry (if applicable)
        if split_data:
            # Resolve person name from user ID if notion_client is available
            person_display = split_data['person']
            if self.notion_client and 'person_user_id' in split_data:
                person_display = self.notion_client.get_username_from_id(split_data['person_user_id'])
            
            # Get emoji for split entry
            person_emoji = Config.get_person_emoji(split_data['person'])
            
            split_table = Table(title="💸 Split Details Entry", show_header=True)
            split_table.add_column("Field", style="cyan")
            split_table.add_column("Value", style="yellow")
            
            split_table.add_row("Icon", person_emoji)
            split_table.add_row("Title", split_data['title'])
            split_table.add_row("Person (Owes)", person_display)
            split_table.add_row("Date", expense_data['date'].strftime('%B %d, %Y'))
            split_table.add_row("Share Percentage", f"%{split_data['share_percentage']:.2f}")
            
            console.print(split_table)
        else:
            console.print("[yellow]ℹ️  No split entry (100% individual expense)[/yellow]")
        
        console.print()
    
    def confirm_send_to_notion(self) -> bool:
        """Ask user to confirm sending data to Notion."""
        return Confirm.ask("✅ Send this data to Notion?", default=True)
    
    def display_success(self, organized_path: str):
        """Display success message."""
        console.print("\n[bold green]✓ Success![/bold green]")
        console.print(f"[green]Receipt organized to: {organized_path}[/green]")
        console.print("[green]Expense and split entries created in Notion[/green]\n")
    
    def display_error(self, error_message: str):
        """Display error message."""
        console.print(f"\n[bold red]✗ Error:[/bold red] {error_message}\n")
    
    def display_processing(self, filename: str):
        """Display processing message."""
        console.print(f"\n[cyan]🔄 Processing receipt: {filename}[/cyan]\n")

