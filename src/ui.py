"""User interface module for interactive prompts and displays."""
from datetime import datetime
from typing import Dict, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
import inquirer
from config import Config


console = Console()


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
    
    def review_and_edit(self, receipt_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Allow user to review and edit extracted information.
        Returns updated receipt_info.
        """
        self.display_extracted_info(receipt_info)
        
        # Ask if user wants to edit
        if not Confirm.ask("📝 Do you want to edit any information?", default=False):
            return receipt_info
        
        # Edit description
        current_desc = receipt_info.get('description', '')
        new_desc = Prompt.ask(
            "Enter description",
            default=current_desc
        )
        receipt_info['description'] = new_desc
        
        # Edit amount
        current_amount = receipt_info.get('amount', 0.0)
        new_amount = Prompt.ask(
            "Enter amount (without CA$ or $)",
            default=str(current_amount)
        )
        try:
            receipt_info['amount'] = float(new_amount)
        except ValueError:
            console.print("[yellow]Invalid amount, keeping original[/yellow]")
        
        # Edit date
        current_date = receipt_info.get('date', datetime.now())
        new_date_str = Prompt.ask(
            "Enter date (YYYY-MM-DD)",
            default=current_date.strftime('%Y-%m-%d')
        )
        try:
            receipt_info['date'] = datetime.strptime(new_date_str, '%Y-%m-%d')
        except ValueError:
            console.print("[yellow]Invalid date format, keeping original[/yellow]")
        
        console.print("\n[green]✓ Information updated[/green]\n")
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
            split_table.add_row("Date", split_data['date'].strftime('%B %d, %Y'))
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

