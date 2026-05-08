"""Unit tests for validate_node.py"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from workflows.langgraph.nodes.validate_node import validate_node
from workflows.langgraph.state import ReceiptWorkflowState
from domain.enums import WorkflowStatus, Sources
from domain.models.workflow import WorkflowInput
from domain.models.recipts import Receipt, ReceiptItem
from domain.models.enrichment import EnrichedReceipt


class TestValidateNode:
    """Test suite for validate_node functionality."""
    
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
            status=WorkflowStatus.ENRICHING,
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
    
    def test_validate_node_success(self, valid_state):
        """Test successful validation of a valid receipt."""
        # Execute
        result = validate_node(valid_state)
        
        # Assertions
        assert result["status"] == WorkflowStatus.VALIDATING
        assert result["validation_result"] is not None
        assert result["validation_result"].is_valid is True
        assert len(result["validation_result"].errors) == 0
        assert result["validation_result"].requires_review is True  # Always true for prototyping
        assert result["failure_reason"] is None
    
    def test_validate_node_updates_status(self, valid_state):
        """Test that status is updated to VALIDATING."""
        assert valid_state["status"] == WorkflowStatus.ENRICHING
        
        result = validate_node(valid_state)
        
        assert result["status"] == WorkflowStatus.VALIDATING
    
    def test_validate_node_no_receipt(self):
        """Test failure when no receipt is in state."""
        state = ReceiptWorkflowState(
            status=WorkflowStatus.ENRICHING,
            workflow_input=None,
            receipt=None,
            enriched_receipt=None,
            validation_result=None,
            review_data=None,
            expense_summary=None,
            results=None,
            failure_reason=None
        )
        
        result = validate_node(state)
        
        assert result["status"] == WorkflowStatus.FAILED
        assert "No receipt data found" in result["failure_reason"]
    
    def test_validate_node_missing_merchant(self, valid_state):
        """Test validation error when merchant name is missing."""
        valid_state["receipt"].vendor = ""
        
        result = validate_node(valid_state)
        
        assert result["validation_result"].is_valid is False
        assert "Missing merchant name" in result["validation_result"].errors
    
    def test_validate_node_missing_date(self, valid_state):
        """Test validation error when date is missing."""
        valid_state["receipt"].date = ""
        
        result = validate_node(valid_state)
        
        assert result["validation_result"].is_valid is False
        assert "Missing transaction date" in result["validation_result"].errors
    
    def test_validate_node_missing_amount(self, valid_state):
        """Test validation error when amount is None."""
        valid_state["receipt"].total = None
        
        result = validate_node(valid_state)
        
        assert result["validation_result"].is_valid is False
        assert "Missing total amount" in result["validation_result"].errors
    
    def test_validate_node_negative_amount(self, valid_state):
        """Test validation error when amount is negative."""
        valid_state["receipt"].total = -50.00
        
        result = validate_node(valid_state)
        
        assert result["validation_result"].is_valid is False
        assert any("must be positive" in error for error in result["validation_result"].errors)
    
    def test_validate_node_zero_amount(self, valid_state):
        """Test validation error when amount is zero."""
        valid_state["receipt"].total = 0.0
        
        result = validate_node(valid_state)
        
        assert result["validation_result"].is_valid is False
        assert any("must be positive" in error for error in result["validation_result"].errors)
    
    def test_validate_node_high_amount_warning(self, valid_state):
        """Test warning when amount is unusually high."""
        valid_state["receipt"].total = 15000.00
        
        result = validate_node(valid_state)
        
        assert result["validation_result"].is_valid is True
        assert any("Unusually high amount" in warning for warning in result["validation_result"].warnings)
        assert result["validation_result"].confidence_score < 1.0
    
    def test_validate_node_invalid_date_format(self, valid_state):
        """Test validation error for invalid date format."""
        valid_state["receipt"].date = "not-a-date"
        
        result = validate_node(valid_state)
        
        assert result["validation_result"].is_valid is False
        assert any("Invalid date format" in error for error in result["validation_result"].errors)
    
    def test_validate_node_future_date(self, valid_state):
        """Test validation error when date is in the future."""
        future_year = datetime.now().year + 2
        valid_state["receipt"].date = f"{future_year}-01-01"
        
        result = validate_node(valid_state)
        
        assert result["validation_result"].is_valid is False
        assert any("Date is in the future" in error for error in result["validation_result"].errors)
    
    def test_validate_node_old_date_warning(self, valid_state):
        """Test warning when date is very old."""
        valid_state["receipt"].date = "1999-12-31"
        
        result = validate_node(valid_state)
        
        assert result["validation_result"].is_valid is True
        assert any("Date is very old" in warning for warning in result["validation_result"].warnings)
        assert result["validation_result"].confidence_score < 1.0
    
    def test_validate_node_total_mismatch_warning(self, valid_state):
        """Test warning when total doesn't match sum of items."""
        # Items sum to 11.99, but set total to 50.00 (way off)
        valid_state["receipt"].total = 50.00
        
        result = validate_node(valid_state)
        
        assert result["validation_result"].is_valid is True
        assert any("Total mismatch" in warning for warning in result["validation_result"].warnings)
        assert result["validation_result"].confidence_score < 1.0
    
    def test_validate_node_total_within_tolerance(self, valid_state):
        """Test no warning when total is within tolerance of items sum."""
        # Items sum to 8.49 (4.99 + 3.50, note: quantity field doesn't exist in ReceiptItem)
        # Set total to 9.50 to be within 15% tolerance
        # Difference: 9.50 - 8.49 = 1.01
        # Tolerance: 9.50 * 0.15 = 1.425
        # Since 1.01 < 1.425, should be within tolerance
        valid_state["receipt"].total = 9.50
        
        result = validate_node(valid_state)
        
        assert result["validation_result"].is_valid is True
        # Should not have total mismatch warning since within tolerance
        assert not any("Total mismatch" in warning for warning in result["validation_result"].warnings)
    
    def test_validate_node_with_enriched_data_low_confidence(self, valid_state):
        """Test warning when enriched data has low confidence."""
        enriched = EnrichedReceipt(
            merchant_category='Groceries',
            confidence_score=0.5,
            notes='Low confidence detection'
        )
        valid_state["enriched_receipt"] = enriched
        
        result = validate_node(valid_state)
        
        assert result["validation_result"].is_valid is True
        assert any("Low enrichment confidence" in warning for warning in result["validation_result"].warnings)
        assert result["validation_result"].confidence_score < 1.0
    
    def test_validate_node_with_enriched_data_high_confidence(self, valid_state):
        """Test no warning when enriched data has high confidence."""
        enriched = EnrichedReceipt(
            merchant_category='Groceries',
            confidence_score=0.95,
            notes='High confidence detection'
        )
        valid_state["enriched_receipt"] = enriched
        
        result = validate_node(valid_state)
        
        assert result["validation_result"].is_valid is True
        # Should not have low confidence warning
        assert not any("Low enrichment confidence" in warning for warning in result["validation_result"].warnings)
    
    def test_validate_node_multiple_errors(self, valid_state):
        """Test validation with multiple errors."""
        valid_state["receipt"].vendor = ""
        valid_state["receipt"].date = ""
        valid_state["receipt"].total = None
        
        result = validate_node(valid_state)
        
        assert result["validation_result"].is_valid is False
        assert len(result["validation_result"].errors) == 3
        assert "Missing merchant name" in result["validation_result"].errors
        assert "Missing transaction date" in result["validation_result"].errors
        assert "Missing total amount" in result["validation_result"].errors
    
    def test_validate_node_always_requires_review(self, valid_state):
        """Test that validation always requires review (prototyping mode)."""
        result = validate_node(valid_state)
        
        # For prototyping, always require review
        assert result["validation_result"].requires_review is True
    
    def test_validate_node_confidence_score_calculation(self, valid_state):
        """Test that confidence score is properly calculated."""
        # Add multiple warnings to reduce confidence
        valid_state["receipt"].total = 12000.00  # High amount warning (0.9)
        valid_state["receipt"].date = "1999-01-01"  # Old date warning (0.8)
        
        enriched = EnrichedReceipt(
            merchant_category='Groceries',
            confidence_score=0.6,  # Low confidence (0.6)
            notes='Test'
        )
        valid_state["enriched_receipt"] = enriched
        
        result = validate_node(valid_state)
        
        # Confidence calculation:
        # Base: 1.0
        # High amount (>10000): × 0.9
        # Old date (<2000): × 0.8
        # Total mismatch (12000 vs 8.49): × 0.85
        # Low enrichment (0.6): × 0.6
        # Expected: 1.0 × 0.9 × 0.8 × 0.85 × 0.6 = 0.3672
        assert result["validation_result"].confidence_score < 0.4
        assert result["validation_result"].confidence_score > 0.35
    
    def test_validate_node_logs_validation_results(self, valid_state):
        """Test that validation logs appropriate information."""
        with patch('workflows.langgraph.nodes.validate_node.logger') as mock_logger:
            result = validate_node(valid_state)
            
            # Should log validation info
            assert mock_logger.info.call_count >= 1
            
            # Check for validation log message
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any("Validating receipt" in str(call) for call in log_calls)
    
    def test_validate_node_logs_errors(self, valid_state):
        """Test that validation errors are logged."""
        valid_state["receipt"].vendor = ""
        valid_state["receipt"].total = -10.0
        
        with patch('workflows.langgraph.nodes.validate_node.logger') as mock_logger:
            result = validate_node(valid_state)
            
            # Should log warnings for validation failure
            assert mock_logger.warning.call_count >= 1
    
    def test_validate_node_no_items(self, valid_state):
        """Test validation with no items (e.g., bills)."""
        valid_state["receipt"].items = []
        
        result = validate_node(valid_state)
        
        # Should still be valid, no total mismatch warning
        assert result["validation_result"].is_valid is True
        assert not any("Total mismatch" in warning for warning in result["validation_result"].warnings)