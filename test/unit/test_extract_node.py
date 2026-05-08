"""Unit tests for extract_node.py"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from workflows.langgraph.nodes.extract_node import extract_node
from workflows.langgraph.state import ReceiptWorkflowState
from domain.enums import WorkflowStatus, Sources
from domain.models.workflow import WorkflowInput
from domain.models.recipts import Receipt, ReceiptItem


class TestExtractNode:
    """Test suite for extract_node functionality."""
    
    @pytest.fixture
    def mock_pdf_extractor(self):
        """Mock PDFExtractor."""
        with patch('workflows.langgraph.nodes.extract_node.PDFExtractor') as mock:
            yield mock
    
    @pytest.fixture
    def valid_state(self, tmp_path):
        """Create a valid state with a temporary file."""
        test_file = tmp_path / "test_receipt.pdf"
        test_file.write_text("dummy pdf content")
        
        return ReceiptWorkflowState(
            status=WorkflowStatus.INGESTING,
            workflow_input=WorkflowInput(
                source=Sources.LOCAL_FOLDER,
                file_path=str(test_file),
                raw_text="Sample receipt text"
            ),
            receipt=None,
            enriched_receipt=None,
            validation_result=None,
            review_data=None,
            expense_summary=None,
            results=None,
            failure_reason=None
        )
    
    @pytest.fixture
    def sample_extracted_data(self):
        """Sample data returned by PDFExtractor.parse_receipt()."""
        return {
            'order_id': 'ORD-12345',
            'merchant_name': 'Walmart',
            'summary': 'Groceries',
            'date': datetime(2026, 5, 8),
            'items': [
                ReceiptItem(name='Milk', price=4.99, quantity=1),
                ReceiptItem(name='Bread', price=3.50, quantity=2)
            ],
            'amount': 11.99
        }
    
    def test_extract_node_success(self, valid_state, mock_pdf_extractor, sample_extracted_data):
        """Test successful extraction of receipt data."""
        # Setup mock
        mock_extractor_instance = Mock()
        mock_extractor_instance.parse_receipt.return_value = sample_extracted_data
        mock_pdf_extractor.return_value = mock_extractor_instance
        
        # Execute
        result = extract_node(valid_state)
        
        # Assertions
        assert result["status"] == WorkflowStatus.EXTRACTING
        assert result["receipt"] is not None
        assert result["receipt"].recipt_id == 'ORD-12345'
        assert result["receipt"].vendor == 'Walmart'
        assert result["receipt"].summary == 'Groceries'
        assert result["receipt"].total == 11.99
        assert len(result["receipt"].items) == 2
        assert result["failure_reason"] is None
        
        # Verify PDFExtractor was initialized with LLM enabled
        mock_pdf_extractor.assert_called_once_with(use_llm_for_items=True)
        
        # Verify parse_receipt was called with correct path
        mock_extractor_instance.parse_receipt.assert_called_once()
        call_args = mock_extractor_instance.parse_receipt.call_args[0][0]
        assert str(call_args) == valid_state["workflow_input"].file_path
    
    def test_extract_node_updates_status(self, valid_state, mock_pdf_extractor, sample_extracted_data):
        """Test that status is updated to EXTRACTING."""
        mock_extractor_instance = Mock()
        mock_extractor_instance.parse_receipt.return_value = sample_extracted_data
        mock_pdf_extractor.return_value = mock_extractor_instance
        
        # Verify initial status
        assert valid_state["status"] == WorkflowStatus.INGESTING
        
        # Execute
        result = extract_node(valid_state)
        
        # Verify status changed
        assert result["status"] == WorkflowStatus.EXTRACTING
    
    def test_extract_node_no_workflow_input(self, mock_pdf_extractor):
        """Test failure when no workflow input is provided."""
        state = ReceiptWorkflowState(
            status=WorkflowStatus.INGESTING,
            workflow_input=None,
            receipt=None,
            enriched_receipt=None,
            validation_result=None,
            review_data=None,
            expense_summary=None,
            results=None,
            failure_reason=None
        )
        
        # Execute
        result = extract_node(state)
        
        # Assertions
        assert result["status"] == WorkflowStatus.FAILED
        assert "No file path provided" in result["failure_reason"]
    
    def test_extract_node_no_file_path(self, mock_pdf_extractor):
        """Test failure when workflow input is None."""
        state = ReceiptWorkflowState(
            status=WorkflowStatus.INGESTING,
            workflow_input=None,
            receipt=None,
            enriched_receipt=None,
            validation_result=None,
            review_data=None,
            expense_summary=None,
            results=None,
            failure_reason=None
        )
        
        # Execute
        result = extract_node(state)
        
        # Assertions
        assert result["status"] == WorkflowStatus.FAILED
        assert "No file path provided" in result["failure_reason"]
    
    def test_extract_node_file_not_found(self, mock_pdf_extractor):
        """Test failure when PDF file does not exist."""
        state = ReceiptWorkflowState(
            status=WorkflowStatus.INGESTING,
            workflow_input=WorkflowInput(
                source=Sources.LOCAL_FOLDER,
                file_path="/nonexistent/receipt.pdf",
                raw_text="Some text"
            ),
            receipt=None,
            enriched_receipt=None,
            validation_result=None,
            review_data=None,
            expense_summary=None,
            results=None,
            failure_reason=None
        )
        
        # Execute
        result = extract_node(state)
        
        # Assertions
        assert result["status"] == WorkflowStatus.FAILED
        assert "PDF file not found" in result["failure_reason"]
        assert "/nonexistent/receipt.pdf" in result["failure_reason"]
    
    def test_extract_node_extraction_error(self, valid_state, mock_pdf_extractor):
        """Test failure when PDFExtractor raises an exception."""
        # Setup mock to raise exception
        mock_extractor_instance = Mock()
        mock_extractor_instance.parse_receipt.side_effect = Exception("Failed to parse PDF")
        mock_pdf_extractor.return_value = mock_extractor_instance
        
        # Execute
        result = extract_node(valid_state)
        
        # Assertions
        assert result["status"] == WorkflowStatus.FAILED
        assert "Extraction failed" in result["failure_reason"]
        assert "Failed to parse PDF" in result["failure_reason"]
    
    def test_extract_node_with_null_date(self, valid_state, mock_pdf_extractor):
        """Test extraction when date is None."""
        extracted_data = {
            'order_id': 'ORD-12345',
            'merchant_name': 'Amazon',
            'summary': 'Books',
            'date': None,
            'items': [],
            'amount': 25.00
        }
        
        mock_extractor_instance = Mock()
        mock_extractor_instance.parse_receipt.return_value = extracted_data
        mock_pdf_extractor.return_value = mock_extractor_instance
        
        # Execute
        result = extract_node(valid_state)
        
        # Assertions
        assert result["status"] == WorkflowStatus.EXTRACTING
        assert result["receipt"].date == ""
        assert result["receipt"].total == 25.00
    
    def test_extract_node_with_null_amount(self, valid_state, mock_pdf_extractor):
        """Test extraction when amount is None fails validation."""
        extracted_data = {
            'order_id': 'ORD-12345',
            'merchant_name': 'Netflix',
            'summary': 'Subscription',
            'date': datetime(2026, 5, 1),
            'items': [],
            'amount': None
        }
        
        mock_extractor_instance = Mock()
        mock_extractor_instance.parse_receipt.return_value = extracted_data
        mock_pdf_extractor.return_value = mock_extractor_instance
        
        # Execute
        result = extract_node(valid_state)
        
        # Assertions
        assert result["status"] == WorkflowStatus.FAILED
        assert "Invalid or missing amount" in result["failure_reason"]
    
    def test_extract_node_with_empty_items(self, valid_state, mock_pdf_extractor):
        """Test extraction with no items."""
        extracted_data = {
            'order_id': 'BILL-001',
            'merchant_name': 'Electrical Bill',
            'summary': 'Monthly',
            'date': datetime(2026, 5, 1),
            'items': [],
            'amount': 131.36
        }
        
        mock_extractor_instance = Mock()
        mock_extractor_instance.parse_receipt.return_value = extracted_data
        mock_pdf_extractor.return_value = mock_extractor_instance
        
        # Execute
        result = extract_node(valid_state)
        
        # Assertions
        assert result["status"] == WorkflowStatus.EXTRACTING
        assert result["receipt"].items == []
        assert result["receipt"].total == 131.36
    
    def test_extract_node_logs_extraction_info(self, valid_state, mock_pdf_extractor, sample_extracted_data):
        """Test that extraction logs appropriate information."""
        mock_extractor_instance = Mock()
        mock_extractor_instance.parse_receipt.return_value = sample_extracted_data
        mock_pdf_extractor.return_value = mock_extractor_instance
        
        # Execute with logging capture
        with patch('workflows.langgraph.nodes.extract_node.logger') as mock_logger:
            result = extract_node(valid_state)
            
            # Verify logging calls
            assert mock_logger.info.call_count >= 2
            assert mock_logger.debug.call_count >= 2
            
            # Check for specific log messages
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any("Starting extraction" in str(call) for call in log_calls)
            assert any("Extraction complete" in str(call) for call in log_calls)
    
    def test_extract_node_converts_date_to_isoformat(self, valid_state, mock_pdf_extractor):
        """Test that datetime is converted to ISO format string."""
        test_date = datetime(2026, 3, 15, 14, 30, 0)
        extracted_data = {
            'order_id': 'ORD-999',
            'merchant_name': 'Test Store',
            'summary': 'Test',
            'date': test_date,
            'items': [],
            'amount': 50.00
        }
        
        mock_extractor_instance = Mock()
        mock_extractor_instance.parse_receipt.return_value = extracted_data
        mock_pdf_extractor.return_value = mock_extractor_instance
        
        # Execute
        result = extract_node(valid_state)
        
        # Assertions
        assert result["receipt"].date == test_date.isoformat()
    
    def test_extract_node_preserves_receipt_items(self, valid_state, mock_pdf_extractor):
        """Test that receipt items are properly preserved."""
        items = [
            ReceiptItem(name='Item 1', price=10.00, category='produce'),
            ReceiptItem(name='Item 2', price=20.00, category='dairy'),
            ReceiptItem(name='Item 3', price=5.50, category='meat')
        ]
        
        extracted_data = {
            'order_id': 'ORD-ITEMS',
            'merchant_name': 'Store',
            'summary': 'Multiple Items',
            'date': datetime(2026, 5, 8),
            'items': items,
            'amount': 61.50
        }
        
        mock_extractor_instance = Mock()
        mock_extractor_instance.parse_receipt.return_value = extracted_data
        mock_pdf_extractor.return_value = mock_extractor_instance
        
        # Execute
        result = extract_node(valid_state)
        
        # Assertions
        assert len(result["receipt"].items) == 3
        assert result["receipt"].items[0].name == 'Item 1'
        assert result["receipt"].items[1].price == 20.00
        assert result["receipt"].items[2].category == 'meat'