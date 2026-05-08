"""Unit tests for enrich_node.py"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from workflows.langgraph.nodes.enrich_node import enrich_node
from workflows.langgraph.state import ReceiptWorkflowState
from domain.enums import WorkflowStatus, Sources
from domain.models.workflow import WorkflowInput
from domain.models.recipts import Receipt, ReceiptItem
from domain.models.enrichment import EnrichedReceipt


class TestEnrichNode:
    """Test suite for enrich_node functionality."""
    
    @pytest.fixture
    def mock_llm_enrich(self):
        """Mock llm_enrich_receipt function."""
        with patch('workflows.langgraph.nodes.enrich_node.llm_enrich_receipt') as mock:
            yield mock
    
    @pytest.fixture
    def valid_receipt(self):
        """Create a valid receipt for testing."""
        return Receipt(
            recipt_id='ORD-12345',
            vendor='Walmart',
            summary='Groceries',
            date='2026-05-08',
            items=[
                ReceiptItem(name='Milk', price=4.99, quantity=1),
                ReceiptItem(name='Bread', price=3.50, quantity=2)
            ],
            total=11.99
        )
    
    @pytest.fixture
    def valid_state(self, valid_receipt):
        """Create a valid state with receipt data."""
        return ReceiptWorkflowState(
            status=WorkflowStatus.EXTRACTING,
            workflow_input=WorkflowInput(
                source=Sources.LOCAL_FOLDER,
                file_path="/path/to/receipt.pdf",
                raw_text="Sample text"
            ),
            receipt=valid_receipt,
            enriched_receipt=None,
            validation_result=None,
            review_data=None,
            expense_summary=None,
            results=None,
            failure_reason=None
        )
    
    @pytest.fixture
    def sample_enriched_receipt(self):
        """Sample enriched receipt data."""
        return EnrichedReceipt(
            merchant_category='Groceries',
            confidence_score=0.95,
            notes='High confidence categorization'
        )
    
    def test_enrich_node_success(self, valid_state, mock_llm_enrich, sample_enriched_receipt):
        """Test successful enrichment of a receipt."""
        # Setup mock
        mock_llm_enrich.return_value = sample_enriched_receipt
        
        # Execute
        result = enrich_node(valid_state)
        
        # Assertions
        assert result["status"] == WorkflowStatus.ENRICHING
        assert result["enriched_receipt"] is not None
        assert result["enriched_receipt"].merchant_category == 'Groceries'
        assert result["enriched_receipt"].confidence_score == 0.95
        assert result["enriched_receipt"].notes == 'High confidence categorization'
        assert result["failure_reason"] is None
        
        # Verify LLM was called with receipt
        mock_llm_enrich.assert_called_once_with(valid_state["receipt"])
    
    def test_enrich_node_updates_status(self, valid_state, mock_llm_enrich, sample_enriched_receipt):
        """Test that status is updated to ENRICHING."""
        mock_llm_enrich.return_value = sample_enriched_receipt
        
        assert valid_state["status"] == WorkflowStatus.EXTRACTING
        
        result = enrich_node(valid_state)
        
        assert result["status"] == WorkflowStatus.ENRICHING
    
    def test_enrich_node_no_receipt(self, mock_llm_enrich):
        """Test failure when no receipt is in state."""
        state = ReceiptWorkflowState(
            status=WorkflowStatus.EXTRACTING,
            workflow_input=None,
            receipt=None,
            enriched_receipt=None,
            validation_result=None,
            review_data=None,
            expense_summary=None,
            results=None,
            failure_reason=None
        )
        
        result = enrich_node(state)
        
        assert result["status"] == WorkflowStatus.FAILED
        assert "No receipt data found" in result["failure_reason"]
        
        # LLM should not be called
        mock_llm_enrich.assert_not_called()
    
    def test_enrich_node_llm_error(self, valid_state, mock_llm_enrich):
        """Test failure when LLM enrichment raises an exception."""
        # Setup mock to raise exception
        mock_llm_enrich.side_effect = Exception("LLM API error")
        
        # Execute
        result = enrich_node(valid_state)
        
        # Assertions
        assert result["status"] == WorkflowStatus.FAILED
        assert "Enrichment failed" in result["failure_reason"]
        assert "LLM API error" in result["failure_reason"]
    
    def test_enrich_node_low_confidence(self, valid_state, mock_llm_enrich):
        """Test enrichment with low confidence score."""
        low_confidence_enriched = EnrichedReceipt(
            merchant_category='Unknown',
            confidence_score=0.3,
            notes='Low confidence - unclear merchant type'
        )
        mock_llm_enrich.return_value = low_confidence_enriched
        
        result = enrich_node(valid_state)
        
        assert result["status"] == WorkflowStatus.ENRICHING
        assert result["enriched_receipt"].confidence_score == 0.3
        assert result["enriched_receipt"].merchant_category == 'Unknown'
    
    def test_enrich_node_with_notes(self, valid_state, mock_llm_enrich):
        """Test enrichment that includes notes."""
        enriched_with_notes = EnrichedReceipt(
            merchant_category='Utilities',
            confidence_score=0.88,
            notes='Electrical bill detected from merchant name pattern'
        )
        mock_llm_enrich.return_value = enriched_with_notes
        
        result = enrich_node(valid_state)
        
        assert result["enriched_receipt"].notes is not None
        assert 'Electrical bill' in result["enriched_receipt"].notes
    
    def test_enrich_node_without_notes(self, valid_state, mock_llm_enrich):
        """Test enrichment without notes."""
        enriched_no_notes = EnrichedReceipt(
            merchant_category='Groceries',
            confidence_score=0.95,
            notes=None
        )
        mock_llm_enrich.return_value = enriched_no_notes
        
        result = enrich_node(valid_state)
        
        assert result["enriched_receipt"].notes is None
    
    def test_enrich_node_logs_enrichment_info(self, valid_state, mock_llm_enrich, sample_enriched_receipt):
        """Test that enrichment logs appropriate information."""
        mock_llm_enrich.return_value = sample_enriched_receipt
        
        with patch('workflows.langgraph.nodes.enrich_node.logger') as mock_logger:
            result = enrich_node(valid_state)
            
            # Should log enrichment info
            assert mock_logger.info.call_count >= 2
            
            # Check for specific log messages
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any("Enriching receipt" in str(call) for call in log_calls)
            assert any("Categorized as" in str(call) for call in log_calls)
    
    def test_enrich_node_logs_notes_when_present(self, valid_state, mock_llm_enrich):
        """Test that notes are logged when present."""
        enriched_with_notes = EnrichedReceipt(
            merchant_category='Subscription',
            confidence_score=0.92,
            notes='Netflix subscription detected'
        )
        mock_llm_enrich.return_value = enriched_with_notes
        
        with patch('workflows.langgraph.nodes.enrich_node.logger') as mock_logger:
            result = enrich_node(valid_state)
            
            # Check that notes were logged
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any("Notes:" in str(call) for call in log_calls)
    
    def test_enrich_node_logs_error(self, valid_state, mock_llm_enrich):
        """Test that errors are properly logged."""
        mock_llm_enrich.side_effect = Exception("Test error")
        
        with patch('workflows.langgraph.nodes.enrich_node.logger') as mock_logger:
            result = enrich_node(valid_state)
            
            # Should log error
            assert mock_logger.error.call_count >= 1
            
            # Check error message
            error_calls = [str(call) for call in mock_logger.error.call_args_list]
            assert any("Enrichment error" in str(call) for call in error_calls)
    
    def test_enrich_node_different_categories(self, valid_state, mock_llm_enrich):
        """Test enrichment with different merchant categories."""
        categories = [
            'Groceries',
            'Utilities',
            'Subscription',
            'Entertainment',
            'Transportation',
            'Healthcare'
        ]
        
        for category in categories:
            enriched = EnrichedReceipt(
                merchant_category=category,
                confidence_score=0.9,
                notes=f'Categorized as {category}'
            )
            mock_llm_enrich.return_value = enriched
            
            result = enrich_node(valid_state)
            
            assert result["enriched_receipt"].merchant_category == category
    
    def test_enrich_node_preserves_receipt_data(self, valid_state, mock_llm_enrich, sample_enriched_receipt):
        """Test that original receipt data is preserved after enrichment."""
        mock_llm_enrich.return_value = sample_enriched_receipt
        
        original_receipt = valid_state["receipt"]
        
        result = enrich_node(valid_state)
        
        # Original receipt should be unchanged
        assert result["receipt"] == original_receipt
        assert result["receipt"].vendor == 'Walmart'
        assert result["receipt"].total == 11.99
    
    def test_enrich_node_high_confidence_threshold(self, valid_state, mock_llm_enrich):
        """Test enrichment with very high confidence."""
        high_confidence = EnrichedReceipt(
            merchant_category='Groceries',
            confidence_score=0.99,
            notes='Very clear categorization'
        )
        mock_llm_enrich.return_value = high_confidence
        
        result = enrich_node(valid_state)
        
        assert result["enriched_receipt"].confidence_score >= 0.95
    
    def test_enrich_node_edge_case_zero_confidence(self, valid_state, mock_llm_enrich):
        """Test enrichment with zero confidence (edge case)."""
        zero_confidence = EnrichedReceipt(
            merchant_category='Unknown',
            confidence_score=0.0,
            notes='Unable to categorize'
        )
        mock_llm_enrich.return_value = zero_confidence
        
        result = enrich_node(valid_state)
        
        assert result["status"] == WorkflowStatus.ENRICHING
        assert result["enriched_receipt"].confidence_score == 0.0