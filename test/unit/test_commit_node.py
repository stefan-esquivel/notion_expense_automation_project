"""Unit tests for commit_node.py"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from workflows.langgraph.nodes.commit_node import commit_node
from workflows.langgraph.state import ReceiptWorkflowState
from domain.enums import WorkflowStatus, Sources
from domain.models.workflow import WorkflowInput, ReviewData
from domain.models.expense import ExpenseSummary, SplitDetail
from domain.models.recipts import Receipt


class TestCommitNode:
    """Test suite for commit_node functionality."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock Config values."""
        with patch('workflows.langgraph.nodes.commit_node.Config') as mock:
            mock.NOTION_API_TOKEN = "test_token_123"
            mock.EXPENSE_TABLE_DATABASE_ID = "expense_db_id"
            mock.SPLIT_DETAILS_DATABASE_ID = "split_db_id"
            mock.BALANCES_PAGE_ID = "balance_page_id"
            mock.YOUR_NAME = "Jon Doe"
            mock.PARTNER_NAME = "Jane Doe"
            mock.PROCESSED_FOLDER = "/path/to/processed"
            yield mock
    
    @pytest.fixture
    def mock_notion_client(self):
        """Mock NotionExpenseClient."""
        with patch('workflows.langgraph.nodes.commit_node.NotionExpenseClient') as mock:
            yield mock
    
    @pytest.fixture
    def mock_file_organizer(self):
        """Mock FileOrganizer."""
        with patch('workflows.langgraph.nodes.commit_node.FileOrganizer') as mock:
            yield mock
    
    @pytest.fixture
    def mock_ui(self):
        """Mock ExpenseUI."""
        with patch('workflows.langgraph.nodes.commit_node.ExpenseUI') as mock:
            yield mock
    
    @pytest.fixture
    def valid_expense_summary(self, tmp_path):
        """Create a valid expense summary."""
        test_file = tmp_path / "receipt.pdf"
        test_file.write_text("dummy content")
        
        return ExpenseSummary(
            merchant_description="Walmart Order (Groceries)",
            date=datetime(2026, 5, 8),
            amount=50.00,
            paid_by="Jon Doe",
            receipt_file_path=test_file,
            receipt_filename="2026-05-08_Walmart_Order_(Groceries)_$50.00.pdf",
            splits=[
                SplitDetail(
                    person="Jane Doe",
                    share_percent=50.0,
                    title="Jane Doe's Walmart Order Split (Groceries)"
                )
            ]
        )
    
    @pytest.fixture
    def valid_state(self, valid_expense_summary):
        """Create a valid state ready for commit."""
        return ReceiptWorkflowState(
            status=WorkflowStatus.REVIEWING,
            workflow_input=WorkflowInput(
                source=Sources.LOCAL_FOLDER,
                file_path=str(valid_expense_summary.receipt_file_path),
                raw_text="Sample text"
            ),
            receipt=Receipt(
                recipt_id='ORD-123',
                vendor='Walmart',
                summary='Groceries',
                date='2026-05-08',
                items=[],
                total=50.00
            ),
            enriched_receipt=None,
            validation_result=None,
            review_data=ReviewData(
                paid_by="Jon Doe",
                amount_override=None,
                merchant_override=None,
                date_override=None,
                notes=None,
                approved=True,
                reviewed_at=datetime.now()
            ),
            expense_summary=valid_expense_summary,
            results=None,
            failure_reason=None
        )
    
    def test_commit_node_success(self, valid_state, mock_config, mock_notion_client, mock_file_organizer, mock_ui):
        """Test successful commit to Notion and file organization."""
        # Setup mocks
        mock_notion_instance = Mock()
        mock_notion_instance.create_expense_entry.return_value = "27361377bcc3807b883be5176931dea4"
        mock_notion_instance.create_split_entry.return_value = "35961377bcc38172a93bef826e153c5a"
        mock_notion_client.return_value = mock_notion_instance
        
        mock_organizer_instance = Mock()
        mock_organizer_instance.organize_file.return_value = Path("/processed/2026/May/receipt.pdf")
        mock_file_organizer.return_value = mock_organizer_instance
        
        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        
        # Execute
        result = commit_node(valid_state)
        
        # Assertions
        assert result["status"] == WorkflowStatus.COMPLETED
        assert result["results"] is not None
        assert result["results"].notion_expense_id == "27361377bcc3807b883be5176931dea4"
        assert "35961377bcc38172a93bef826e153c5a" in result["results"].notion_split_ids
        assert result["failure_reason"] is None
        
        # Verify Notion client was initialized correctly
        mock_notion_client.assert_called_once_with(
            "test_token_123",
            "expense_db_id",
            split_db_id="split_db_id",
            balance_page_id="balance_page_id"
        )
        
        # Verify expense entry was created
        mock_notion_instance.create_expense_entry.assert_called_once()
        
        # Verify split entry was created
        mock_notion_instance.create_split_entry.assert_called_once()
    
    def test_commit_node_updates_status(self, valid_state, mock_config, mock_notion_client, mock_file_organizer, mock_ui):
        """Test that status is updated through SUBMITTING to COMPLETED."""
        mock_notion_instance = Mock()
        mock_notion_instance.create_expense_entry.return_value = "27361377bcc3807b883be5176931dea4"
        mock_notion_instance.create_split_entry.return_value = "35961377bcc38172a93bef826e153c5a"
        mock_notion_client.return_value = mock_notion_instance
        
        mock_organizer_instance = Mock()
        mock_organizer_instance.organize_file.return_value = Path("/processed/receipt.pdf")
        mock_file_organizer.return_value = mock_organizer_instance
        
        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        
        assert valid_state["status"] == WorkflowStatus.REVIEWING
        
        result = commit_node(valid_state)
        
        assert result["status"] == WorkflowStatus.COMPLETED
    
    def test_commit_node_no_expense_summary(self, mock_config):
        """Test failure when no expense summary is in state."""
        state = ReceiptWorkflowState(
            status=WorkflowStatus.REVIEWING,
            workflow_input=None,
            receipt=None,
            enriched_receipt=None,
            validation_result=None,
            review_data=None,
            expense_summary=None,
            results=None,
            failure_reason=None
        )
        
        result = commit_node(state)
        
        assert result["status"] == WorkflowStatus.FAILED
        assert "No expense_summary found" in result["failure_reason"]
    
    def test_commit_node_missing_notion_token(self, valid_state, mock_file_organizer, mock_ui):
        """Test failure when NOTION_API_TOKEN is not configured."""
        with patch('workflows.langgraph.nodes.commit_node.Config') as mock_config:
            mock_config.NOTION_API_TOKEN = None
            mock_config.YOUR_NAME = "Jon Doe"
            mock_config.PARTNER_NAME = "Jane Doe"
            
            result = commit_node(valid_state)
            
            assert result["status"] == WorkflowStatus.FAILED
            assert "NOTION_API_TOKEN is not configured" in result["failure_reason"]
    
    def test_commit_node_missing_expense_db_id(self, valid_state, mock_file_organizer, mock_ui):
        """Test failure when EXPENSE_TABLE_DATABASE_ID is not configured."""
        with patch('workflows.langgraph.nodes.commit_node.Config') as mock_config:
            mock_config.NOTION_API_TOKEN = "token"
            mock_config.EXPENSE_TABLE_DATABASE_ID = None
            mock_config.YOUR_NAME = "Jon Doe"
            mock_config.PARTNER_NAME = "Jane Doe"
            
            result = commit_node(valid_state)
            
            assert result["status"] == WorkflowStatus.FAILED
            assert "EXPENSE_TABLE_DATABASE_ID is not configured" in result["failure_reason"]
    
    def test_commit_node_notion_api_error(self, valid_state, mock_config, mock_notion_client, mock_ui):
        """Test failure when Notion API raises an exception."""
        mock_notion_instance = Mock()
        mock_notion_instance.create_expense_entry.side_effect = Exception("Notion API error")
        mock_notion_client.return_value = mock_notion_instance
        
        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        
        result = commit_node(valid_state)
        
        assert result["status"] == WorkflowStatus.FAILED
        assert "Failed to commit to notion" in result["failure_reason"]
        assert "Notion API error" in result["failure_reason"]
    
    def test_commit_node_without_splits(self, valid_state, mock_config, mock_notion_client, mock_file_organizer, mock_ui):
        """Test commit when expense has no splits."""
        # Remove splits from expense summary
        valid_state["expense_summary"].splits = None
        
        mock_notion_instance = Mock()
        mock_notion_instance.create_expense_entry.return_value = "27361377bcc3807b883be5176931dea4"
        mock_notion_client.return_value = mock_notion_instance
        
        mock_organizer_instance = Mock()
        mock_organizer_instance.organize_file.return_value = Path("/processed/receipt.pdf")
        mock_file_organizer.return_value = mock_organizer_instance
        
        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        
        result = commit_node(valid_state)
        
        assert result["status"] == WorkflowStatus.COMPLETED
        assert result["results"].notion_split_ids == []
        
        # Verify split entry was NOT created
        mock_notion_instance.create_split_entry.assert_not_called()
    
    def test_commit_node_multiple_splits(self, valid_state, mock_config, mock_notion_client, mock_file_organizer, mock_ui):
        """Test commit with multiple split entries."""
        # Add multiple splits
        valid_state["expense_summary"].splits = [
            SplitDetail(person="Jane Doe", share_percent=30.0, title="Jane's Split"),
            SplitDetail(person="John Smith", share_percent=30.0, title="John's Split"),
            SplitDetail(person="Bob Jones", share_percent=40.0, title="Bob's Split")
        ]
        
        mock_notion_instance = Mock()
        mock_notion_instance.create_expense_entry.return_value = "27361377bcc3807b883be5176931dea4"
        mock_notion_instance.create_split_entry.side_effect = [
            "35961377bcc38172a93bef826e153c5a",
            "45961377bcc38172a93bef826e153c5b",
            "55961377bcc38172a93bef826e153c5c"
        ]
        mock_notion_client.return_value = mock_notion_instance
        
        mock_organizer_instance = Mock()
        mock_organizer_instance.organize_file.return_value = Path("/processed/receipt.pdf")
        mock_file_organizer.return_value = mock_organizer_instance
        
        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        
        result = commit_node(valid_state)
        
        assert result["status"] == WorkflowStatus.COMPLETED
        assert len(result["results"].notion_split_ids) == 3
        assert "35961377bcc38172a93bef826e153c5a" in result["results"].notion_split_ids
        assert "45961377bcc38172a93bef826e153c5b" in result["results"].notion_split_ids
        assert "55961377bcc38172a93bef826e153c5c" in result["results"].notion_split_ids
        
        # Verify split entry was created 3 times
        assert mock_notion_instance.create_split_entry.call_count == 3
    
    def test_commit_node_organizes_file(self, valid_state, mock_config, mock_notion_client, mock_file_organizer, mock_ui):
        """Test that file is organized after Notion commit."""
        mock_notion_instance = Mock()
        mock_notion_instance.create_expense_entry.return_value = "27361377bcc3807b883be5176931dea4"
        mock_notion_instance.create_split_entry.return_value = "35961377bcc38172a93bef826e153c5a"
        mock_notion_client.return_value = mock_notion_instance
        
        mock_organizer_instance = Mock()
        organized_path = Path("/processed/2026/May/walmart_order/receipt.pdf")
        mock_organizer_instance.organize_file.return_value = organized_path
        mock_file_organizer.return_value = mock_organizer_instance
        
        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        
        result = commit_node(valid_state)
        
        # Verify FileOrganizer was initialized
        mock_file_organizer.assert_called_once_with(processed_folder="/path/to/processed")
        
        # Verify organize_file was called
        mock_organizer_instance.organize_file.assert_called_once()
        
        # Verify archive path in results
        assert result["results"].archive_path == organized_path
    
    def test_commit_node_extracts_merchant_for_folder(self, valid_state, mock_config, mock_notion_client, mock_file_organizer, mock_ui):
        """Test that merchant name is extracted correctly for folder organization."""
        # Set merchant description with parentheses
        valid_state["expense_summary"].merchant_description = "Amazon Order (Pint Glasses)"
        
        mock_notion_instance = Mock()
        mock_notion_instance.create_expense_entry.return_value = "27361377bcc3807b883be5176931dea4"
        mock_notion_instance.create_split_entry.return_value = "35961377bcc38172a93bef826e153c5a"
        mock_notion_client.return_value = mock_notion_instance
        
        mock_organizer_instance = Mock()
        mock_organizer_instance.organize_file.return_value = Path("/processed/receipt.pdf")
        mock_file_organizer.return_value = mock_organizer_instance
        
        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        
        result = commit_node(valid_state)
        
        # Verify organize_file was called with extracted merchant name
        call_args = mock_organizer_instance.organize_file.call_args
        assert call_args[1]['merchant_name'] == "Amazon Order"  # Without "(Pint Glasses)"
    
    def test_commit_node_without_receipt_file(self, valid_state, mock_config, mock_notion_client, mock_file_organizer, mock_ui):
        """Test commit when there's no receipt file path."""
        # Remove receipt file path
        valid_state["expense_summary"].receipt_file_path = None
        
        mock_notion_instance = Mock()
        mock_notion_instance.create_expense_entry.return_value = "27361377bcc3807b883be5176931dea4"
        mock_notion_instance.create_split_entry.return_value = "35961377bcc38172a93bef826e153c5a"
        mock_notion_client.return_value = mock_notion_instance
        
        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        
        result = commit_node(valid_state)
        
        assert result["status"] == WorkflowStatus.COMPLETED
        assert result["results"].archive_path == Path("unknown")
        
        # Verify FileOrganizer was NOT called
        mock_file_organizer.assert_not_called()
    
    def test_commit_node_stores_timestamp(self, valid_state, mock_config, mock_notion_client, mock_file_organizer, mock_ui):
        """Test that results include a timestamp."""
        mock_notion_instance = Mock()
        mock_notion_instance.create_expense_entry.return_value = "27361377bcc3807b883be5176931dea4"
        mock_notion_instance.create_split_entry.return_value = "35961377bcc38172a93bef826e153c5a"
        mock_notion_client.return_value = mock_notion_instance
        
        mock_organizer_instance = Mock()
        mock_organizer_instance.organize_file.return_value = Path("/processed/receipt.pdf")
        mock_file_organizer.return_value = mock_organizer_instance
        
        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        
        before_time = datetime.now()
        result = commit_node(valid_state)
        after_time = datetime.now()
        
        assert result["results"].timestamp >= before_time
        assert result["results"].timestamp <= after_time
    
    def test_commit_node_logs_success(self, valid_state, mock_config, mock_notion_client, mock_file_organizer, mock_ui):
        """Test that successful commit is logged."""
        mock_notion_instance = Mock()
        mock_notion_instance.create_expense_entry.return_value = "27361377bcc3807b883be5176931dea4"
        mock_notion_instance.create_split_entry.return_value = "35961377bcc38172a93bef826e153c5a"
        mock_notion_client.return_value = mock_notion_instance
        
        mock_organizer_instance = Mock()
        mock_organizer_instance.organize_file.return_value = Path("/processed/receipt.pdf")
        mock_file_organizer.return_value = mock_organizer_instance
        
        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        
        with patch('workflows.langgraph.nodes.commit_node.logger') as mock_logger:
            result = commit_node(valid_state)
            
            # Verify logging
            assert mock_logger.info.call_count >= 2
            
            # Check for specific log messages
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any("Creating Notion entries" in str(call) for call in log_calls)
            assert any("Successfully committed" in str(call) for call in log_calls)
            assert any("27361377bcc3807b883be5176931dea4" in str(call) for call in log_calls)
    
    def test_commit_node_logs_error(self, valid_state, mock_config, mock_notion_client, mock_ui):
        """Test that errors are properly logged."""
        mock_notion_instance = Mock()
        mock_notion_instance.create_expense_entry.side_effect = Exception("Test error")
        mock_notion_client.return_value = mock_notion_instance
        
        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        
        with patch('workflows.langgraph.nodes.commit_node.logger') as mock_logger:
            result = commit_node(valid_state)
            
            # Verify error logging
            assert mock_logger.error.call_count >= 1
            
            # Check for error message
            error_calls = [str(call) for call in mock_logger.error.call_args_list]
            assert any("Failed to commit" in str(call) for call in error_calls)