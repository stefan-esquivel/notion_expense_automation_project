"""Unit tests for ingest_node.py"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from workflows.langgraph.nodes.ingest_node import ingest_node
from workflows.langgraph.state import ReceiptWorkflowState
from domain.enums import WorkflowStatus, Sources
from domain.models.workflow import WorkflowInput


class TestIngestNode:
    """Test suite for ingest_node functionality."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock Config values."""
        with patch('workflows.langgraph.nodes.ingest_node.Config') as mock:
            mock.YOUR_NAME = "Jon Doe"
            mock.PARTNER_NAME = "Jane Doe"
            yield mock
    
    @pytest.fixture
    def mock_ui(self):
        """Mock ExpenseUI."""
        with patch('workflows.langgraph.nodes.ingest_node.ExpenseUI') as mock:
            yield mock
    
    @pytest.fixture
    def mock_pdf_extractor(self):
        """Mock PDFExtractor."""
        with patch('workflows.langgraph.nodes.ingest_node.PDFExtractor') as mock:
            yield mock
    
    @pytest.fixture
    def valid_state(self, tmp_path):
        """Create a valid state with a real temporary file."""
        # Create a temporary PDF file
        test_file = tmp_path / "test_receipt.pdf"
        test_file.write_text("dummy pdf content")
        
        return ReceiptWorkflowState(
            status=WorkflowStatus.PENDING,
            workflow_input=WorkflowInput(
                source=Sources.LOCAL_FOLDER,
                file_path=str(test_file),
                raw_text="placeholder text"
            ),
            receipt=None,
            enriched_receipt=None,
            validation_result=None,
            review_data=None,
            expense_summary=None,
            results=None,
            failure_reason=None
        )
    
    def test_ingest_node_success(self, valid_state, mock_config, mock_ui, mock_pdf_extractor):
        """Test successful ingestion of a receipt."""
        # Setup mocks
        mock_extractor_instance = Mock()
        mock_extractor_instance.extract_text.return_value = "Sample receipt text content"
        mock_pdf_extractor.return_value = mock_extractor_instance
        
        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        
        # Execute
        result = ingest_node(valid_state)
        
        # Assertions
        assert result["status"] == WorkflowStatus.INGESTING
        assert result["workflow_input"].raw_text == "Sample receipt text content"
        assert result["failure_reason"] is None
        
        # Verify UI was initialized with correct names
        mock_ui.assert_called_once_with(
            your_name="Jon Doe",
            partner_name="Jane Doe"
        )
        
        # Verify display_processing was called
        mock_ui_instance.display_processing.assert_called_once_with(valid_state["workflow_input"].file_path)
        
        # Verify PDFExtractor was used
        mock_pdf_extractor.assert_called_once()
        mock_extractor_instance.extract_text.assert_called_once()
    
    def test_ingest_node_no_workflow_input(self, mock_config, mock_ui):
        """Test failure when no workflow input is provided."""
        state = ReceiptWorkflowState(
            status=WorkflowStatus.PENDING,
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
        result = ingest_node(state)
        
        # Assertions
        assert result["status"] == WorkflowStatus.FAILED
        assert result["failure_reason"] == "No workflow input provided"
    
    def test_ingest_node_no_file_path(self, mock_config, mock_ui):
        """Test failure when workflow_input is None (no file path scenario)."""
        state = ReceiptWorkflowState(
            status=WorkflowStatus.PENDING,
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
        result = ingest_node(state)
        
        # Assertions
        assert result["status"] == WorkflowStatus.FAILED
        assert result["failure_reason"] == "No workflow input provided"
    
    def test_ingest_node_file_not_exists(self, mock_config, mock_ui):
        """Test failure when file does not exist."""
        state = ReceiptWorkflowState(
            status=WorkflowStatus.PENDING,
            workflow_input=WorkflowInput(
                source=Sources.LOCAL_FOLDER,
                file_path="/nonexistent/path/receipt.pdf",
                raw_text="dummy text"
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
        result = ingest_node(state)
        
        # Assertions
        assert result["status"] == WorkflowStatus.FAILED
        assert "File does not exist" in result["failure_reason"]
        assert "/nonexistent/path/receipt.pdf" in result["failure_reason"]
    
    def test_ingest_node_pdf_extraction_error(self, valid_state, mock_config, mock_ui, mock_pdf_extractor):
        """Test failure when PDF extraction raises an exception."""
        # Setup mocks
        mock_extractor_instance = Mock()
        mock_extractor_instance.extract_text.side_effect = Exception("PDF is corrupted")
        mock_pdf_extractor.return_value = mock_extractor_instance
        
        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        
        # Execute
        result = ingest_node(valid_state)
        
        # Assertions
        assert result["status"] == WorkflowStatus.FAILED
        assert "Failed to extract text from PDF" in result["failure_reason"]
        assert "PDF is corrupted" in result["failure_reason"]
    
    def test_ingest_node_updates_raw_text(self, valid_state, mock_config, mock_ui, mock_pdf_extractor):
        """Test that raw_text is properly updated in workflow_input."""
        # Setup mocks
        extracted_text = "WALMART\nTotal: $50.00\nDate: 2026-05-08"
        mock_extractor_instance = Mock()
        mock_extractor_instance.extract_text.return_value = extracted_text
        mock_pdf_extractor.return_value = mock_extractor_instance
        
        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        
        # Verify initial state (now has placeholder text due to validation)
        assert valid_state["workflow_input"].raw_text == "placeholder text"
        
        # Execute
        result = ingest_node(valid_state)
        
        # Assertions
        assert result["workflow_input"].raw_text == extracted_text
        assert result["status"] == WorkflowStatus.INGESTING
    
    def test_ingest_node_logs_source(self, valid_state, mock_config, mock_ui, mock_pdf_extractor):
        """Test that the node logs the source of the receipt."""
        # Setup mocks
        mock_extractor_instance = Mock()
        mock_extractor_instance.extract_text.return_value = "Sample text"
        mock_pdf_extractor.return_value = mock_extractor_instance
        
        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        
        # Execute with logging capture
        with patch('workflows.langgraph.nodes.ingest_node.logger') as mock_logger:
            result = ingest_node(valid_state)
            
            # Verify logging calls
            assert mock_logger.info.call_count >= 2
            
            # Check that file path and source were logged
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any("Ingesting receipt from" in str(call) for call in log_calls)
            assert any("Source:" in str(call) for call in log_calls)
    
    def test_ingest_node_with_gmail_source(self, tmp_path, mock_config, mock_ui, mock_pdf_extractor):
        """Test ingestion with GMAIL as source."""
        # Create a temporary PDF file
        test_file = tmp_path / "gmail_receipt.pdf"
        test_file.write_text("dummy pdf content")
        
        state = ReceiptWorkflowState(
            status=WorkflowStatus.PENDING,
            workflow_input=WorkflowInput(
                source=Sources.GMAIL,
                file_path=str(test_file),
                raw_text="placeholder text"
            ),
            receipt=None,
            enriched_receipt=None,
            validation_result=None,
            review_data=None,
            expense_summary=None,
            results=None,
            failure_reason=None
        )
        
        # Setup mocks
        mock_extractor_instance = Mock()
        mock_extractor_instance.extract_text.return_value = "Gmail receipt text"
        mock_pdf_extractor.return_value = mock_extractor_instance
        
        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        
        # Execute
        result = ingest_node(state)
        
        # Assertions
        assert result["status"] == WorkflowStatus.INGESTING
        assert result["workflow_input"].source == Sources.GMAIL
        assert result["workflow_input"].raw_text == "Gmail receipt text"