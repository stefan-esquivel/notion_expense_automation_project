"""Main application entry point."""
from pathlib import Path

from config import Config
from services.notion_api import NotionExpenseClient
from services.ui import ExpenseUI
from logger import get_logger
from workflows.langgraph.graph import build_graph, create_initial_state
from domain.enums import WorkflowStatus


class ExpenseAutomation:
    """Main application class orchestrating the expense automation workflow."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.config = Config
        self.workflow = build_graph()
        self.ui = ExpenseUI(
            Config.YOUR_NAME,
            Config.PARTNER_NAME,
            notion_client=None  # Will be initialized in workflow nodes
        )
    
    def process_receipt(self, pdf_path: Path) -> bool:
        """
        Process a single receipt through the LangGraph workflow.
        Returns True if successful, False otherwise.
        """
        try:
            self.ui.display_processing(pdf_path.name)
            
            # Create initial workflow state
            self.logger.info(f"Starting workflow for {pdf_path.name}")
            initial_state = create_initial_state(str(pdf_path))
            
            # Run the workflow
            result = self.workflow.invoke(initial_state)
            
            # Check workflow status
            if result['status'] == WorkflowStatus.COMPLETED:
                if result.get('results'):
                    results = result['results']
                    self.ui.display_success(str(results.archive_path))
                    self.logger.info(f"Successfully processed {pdf_path.name}")
                    self.logger.info(f"Notion expense ID: {results.notion_expense_id}")
                    return True
                else:
                    self.ui.display_error("Workflow completed but no results found")
                    return False
            else:
                error_msg = result.get('failure_reason', 'Unknown error')
                self.ui.display_error(f"Workflow failed: {error_msg}")
                self.logger.error(f"Workflow failed for {pdf_path.name}: {error_msg}")
                return False
            
        except Exception as e:
            self.ui.display_error(str(e))
            self.logger.error(f"Error processing {pdf_path.name}: {e}", exc_info=True)
            return False
    
    def scan_input_folder(self) -> list[Path]:
        """Scan input folder for PDF files."""
        pdf_files = list(Config.INPUT_FOLDER.glob("*.pdf"))
        return sorted(pdf_files)
    
    def run(self):
        """Main application loop."""
        try:
            # Validate configuration
            self.logger.info("Validating configuration")
            Config.validate()
            
            # Test Notion connection (create temporary client for testing)
            self.logger.info("Testing Notion API connection")
            test_client = NotionExpenseClient(
                Config.NOTION_API_TOKEN,
                Config.EXPENSE_TABLE_DATABASE_ID,
                split_db_id=Config.SPLIT_DETAILS_DATABASE_ID,
                balance_page_id=Config.BALANCES_PAGE_ID
            )
            if not test_client.test_connection():
                self.ui.display_error("Failed to connect to Notion API. Check your credentials.")
                return
            
            # Display welcome
            self.ui.display_welcome()
            
            # Scan for receipts
            pdf_files = self.scan_input_folder()
            
            if not pdf_files:
                self.ui.display_error(f"No PDF files found in {Config.INPUT_FOLDER}")
                self.logger.info("No receipts to process")
                return
            
            self.logger.info(f"Found {len(pdf_files)} receipt(s) to process")
            
            # Process each receipt
            success_count = 0
            for pdf_file in pdf_files:
                if self.process_receipt(pdf_path=pdf_file):
                    success_count += 1
            
            # Summary
            self.logger.info(f"Processed {success_count}/{len(pdf_files)} receipts successfully")
            
        except ValueError as e:
            self.ui.display_error(f"Configuration error: {e}")
            self.logger.error(f"Configuration error: {e}")
        except KeyboardInterrupt:
            self.logger.info("Application interrupted by user")
            self.ui.display_error("Application interrupted")
        except Exception as e:
            self.ui.display_error(f"Unexpected error: {e}")
            self.logger.error(f"Unexpected error: {e}", exc_info=True)


def main():
    """Entry point for the application."""
    app = ExpenseAutomation()
    app.run()


if __name__ == "__main__":
    main()

