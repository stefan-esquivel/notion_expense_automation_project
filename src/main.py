"""Main application entry point."""
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from config import Config
from pdf_extractor import PDFExtractor
from file_organizer import FileOrganizer
from notion_api import NotionExpenseClient
from ui import ExpenseUI


# Set up logging
def setup_logging():
    """Configure logging to file and console."""
    log_file = Config.LOG_FOLDER / f"expense_automation_{datetime.now().strftime('%Y%m%d')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


class ExpenseAutomation:
    """Main application class orchestrating the expense automation workflow."""
    
    def __init__(self):
        self.logger = setup_logging()
        self.config = Config
        self.ui = ExpenseUI(Config.YOUR_NAME, Config.PARTNER_NAME)
        self.pdf_extractor = PDFExtractor()
        self.file_organizer = FileOrganizer(Config.PROCESSED_FOLDER)
        self.notion_client = NotionExpenseClient(
            Config.NOTION_API_TOKEN,
            Config.EXPENSE_TABLE_DATABASE_ID,
            split_db_id=Config.SPLIT_DETAILS_DATABASE_ID,
            balance_page_id=Config.BALANCES_PAGE_ID
        )
    
    def process_receipt(self, pdf_path: Path) -> bool:
        """
        Process a single receipt through the entire workflow.
        Returns True if successful, False otherwise.
        """
        try:
            self.ui.display_processing(pdf_path.name)
            
            # Step 1: Extract information from PDF
            self.logger.info(f"Extracting information from {pdf_path.name}")
            receipt_info = self.pdf_extractor.parse_receipt(pdf_path)
            
            # Validate required fields
            if not receipt_info.get('amount') or not receipt_info.get('date'):
                self.ui.display_error("Could not extract amount or date from receipt")
                self.logger.error(f"Missing required fields in {pdf_path.name}")
                return False
            
            # Step 2: Review and edit information
            receipt_info = self.ui.review_and_edit(receipt_info)
            
            # Step 3: Select who paid
            paid_by = self.ui.select_payer()
            
            # Determine who didn't pay (for split entry)
            other_person = (
                self.config.PARTNER_NAME if paid_by == self.config.YOUR_NAME
                else self.config.YOUR_NAME
            )
            
            # Step 4: Confirm split details
            use_split, split_percentage = self.ui.confirm_split(
                receipt_info['amount'],
                split_percentage=self.config.DEFAULT_SPLIT_PERCENTAGE
            )
            
            # Step 5: Prepare data for Notion
            expense_data = {
                'description': receipt_info['description'],
                'date': receipt_info['date'],
                'amount': receipt_info['amount'],
                'paid_by': paid_by,
                'receipt_filename': pdf_path.name
            }
            
            split_data = None
            if use_split:
                split_title = self.notion_client.generate_split_title(
                    other_person,
                    receipt_info['merchant_name'],
                    receipt_info['description'],
                    receipt_info['date']
                )
                
                split_data = {
                    'title': split_title,
                    'person': other_person,
                    'date': receipt_info['date'],
                    'share_percentage': split_percentage
                }
            
            # Step 6: Display final preview
            self.ui.display_final_preview(expense_data, split_data)
            
            # Step 7: Confirm before sending to Notion
            if not self.ui.confirm_send_to_notion():
                self.logger.info("User cancelled sending to Notion")
                return False
            
            # Step 8: Create Notion entries
            self.logger.info("Creating Notion entries")
            expense_page_id = self.notion_client.create_expense_entry(
                expense_data['description'],
                expense_data['date'],
                expense_data['amount'],
                expense_data['paid_by'],
                pdf_path,  # Pass the file path for upload
                expense_data['receipt_filename']
            )
            
            if split_data:
                self.notion_client.create_split_entry(
                    split_data['title'],
                    split_data['person'],
                    split_data['share_percentage'],
                    expense_page_id
                )
            
            # Step 9: Organize file
            self.logger.info("Organizing receipt file")
            organized_path = self.file_organizer.organize_file(
                pdf_path,
                receipt_info['date'],
                receipt_info['merchant_name'],
                receipt_info['description'],
                receipt_info['amount']
            )
            
            # Step 10: Success!
            self.ui.display_success(str(organized_path))
            self.logger.info(f"Successfully processed {pdf_path.name}")
            return True
            
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
            
            # Test Notion connection
            self.logger.info("Testing Notion API connection")
            if not self.notion_client.test_connection():
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
                if self.process_receipt(pdf_file):
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

# Made with Bob
