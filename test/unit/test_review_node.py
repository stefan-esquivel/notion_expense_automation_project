"""Unit tests for review_node.py"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from workflows.langgraph.nodes.review_node import review_node, _extract_base_merchant_name
from workflows.langgraph.state import ReceiptWorkflowState
from domain.enums import WorkflowStatus, Sources
from domain.models.workflow import WorkflowInput, ValidationResult, AugmentResults, ScanResults
from domain.models.recipts import Receipt, ReceiptItem


class TestExtractBaseMerchantName:
    """Test suite for _extract_base_merchant_name helper function."""
    
    def test_extract_amazon_order(self):
        """Test extracting base name from 'Amazon Order'."""
        assert _extract_base_merchant_name("Amazon Order") == "Amazon"
    
    def test_extract_walmart_order(self):
        """Test extracting base name from 'Walmart Order'."""
        assert _extract_base_merchant_name("Walmart Order") == "Walmart"
    
    def test_extract_electrical_bill(self):
        """Test extracting base name from 'Electrical Bill'."""
        assert _extract_base_merchant_name("Electrical Bill") == "Electrical"
    
    def test_extract_netflix_payment(self):
        """Test extracting base name from 'Netflix Payment'."""
        assert _extract_base_merchant_name("Netflix Payment") == "Netflix"
    
    def test_extract_no_suffix(self):
        """Test extracting base name when no suffix present."""
        assert _extract_base_merchant_name("Netflix") == "Netflix"
    
    def test_extract_groceries_suffix(self):
        """Test extracting base name with 'Groceries' suffix."""
        assert _extract_base_merchant_name("Longo's Groceries") == "Longo's"
    
    def test_extract_premium_suffix(self):
        """Test extracting base name with 'Premium' suffix."""
        assert _extract_base_merchant_name("YouTube Premium") == "YouTube"


class TestReviewNode:
    """Test suite for review_node functionality."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock Config values."""
        with patch('workflows.langgraph.nodes.review_node.Config') as mock:
            mock.YOUR_NAME = "Jon Doe"
            mock.PARTNER_NAME = "Jane Doe"
            mock.DEFAULT_SPLIT_PERCENTAGE = 50.0
            yield mock
    
    @pytest.fixture
    def mock_ui(self):
        """Mock ExpenseUI."""
        with patch('workflows.langgraph.nodes.review_node.ExpenseUI') as mock:
            yield mock
    
    @pytest.fixture
    def valid_receipt(self):
        """Create a valid receipt for testing."""
        return Receipt(
            recipt_id='ORD-12345',
            vendor='Walmart Order',
            transaction_type='Order',
            summary='Groceries',
            date='2026-05-08',
            items=[
                ReceiptItem(name='Milk', price=4.99),
                ReceiptItem(name='Bread', price=3.50)
            ],
            total=11.99
        )
    
    @pytest.fixture
    def valid_state(self, valid_receipt):
        """Create a valid state with receipt and validation data."""
        return ReceiptWorkflowState(
            status=WorkflowStatus.VALIDATING,
            workflow_input=WorkflowInput(
                source=Sources.LOCAL_FOLDER,
                file_path="/path/to/receipt.pdf",
                raw_text="Sample text"
            ),
            receipt=valid_receipt,
            scan_results=ScanResults(has_missing_data=False, missing_fields=[]),
            augment_results=None,
            enriched_receipt=None,
            validation_result=ValidationResult(
                issues=[],
                confidence_score=0.95
            ),
            acknowledged_warnings=set(),
            review_data=None,
            expense_summary=None,
            results=None,
            failure_reason=None
        )
    
    def test_review_node_success(self, valid_state, mock_config, mock_ui):
        """Test successful review with user approval."""
        # Setup UI mocks
        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        
        # Mock UI responses
        mock_ui_instance.review_and_edit.return_value = {
            'amount': 11.99,
            'description': 'Walmart Order (Groceries)',
            'date': datetime(2026, 5, 8)
        }
        mock_ui_instance.select_payer.return_value = "Jon Doe"
        mock_ui_instance.confirm_split.return_value = (True, 50.0)
        
        # Execute
        result = review_node(valid_state)
        
        # Assertions
        assert result["status"] == WorkflowStatus.REVIEWING
        assert result["review_data"] is not None
        assert result["review_data"].paid_by == "Jon Doe"
        assert result["review_data"].approved is True
        assert result["expense_summary"] is not None
        assert result["expense_summary"].amount == 11.99
        assert result["failure_reason"] is None
    
    def test_review_node_updates_status(self, valid_state, mock_config, mock_ui):
        """Test that status is updated to REVIEWING."""
        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        mock_ui_instance.review_and_edit.return_value = {
            'amount': 11.99,
            'description': 'Walmart Order (Groceries)',
            'date': datetime(2026, 5, 8)
        }
        mock_ui_instance.select_payer.return_value = "Jon Doe"
        mock_ui_instance.confirm_split.return_value = (True, 50.0)
        
        assert valid_state["status"] == WorkflowStatus.VALIDATING
        
        result = review_node(valid_state)
        
        assert result["status"] == WorkflowStatus.REVIEWING
    
    def test_review_node_no_receipt(self, mock_config, mock_ui):
        """Test failure when no receipt is in state."""
        state = ReceiptWorkflowState(
            status=WorkflowStatus.VALIDATING,
            workflow_input=None,
            receipt=None,
            enriched_receipt=None,
            validation_result=None,
            review_data=None,
            expense_summary=None,
            results=None,
            failure_reason=None
        )
        
        result = review_node(state)
        
        assert result["status"] == WorkflowStatus.FAILED
        assert "No receipt data found" in result["failure_reason"]
    
    def test_review_node_user_cancelled(self, valid_state, mock_config, mock_ui):
        """Test handling of user cancellation (KeyboardInterrupt)."""
        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        mock_ui_instance.review_and_edit.side_effect = KeyboardInterrupt()
        
        result = review_node(valid_state)
        
        assert result["status"] == WorkflowStatus.FAILED
        assert "Review cancelled by user" in result["failure_reason"]
    
    def test_review_node_with_amount_override(self, valid_state, mock_config, mock_ui):
        """Test review with user correcting the amount."""
        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        
        # User changes amount from 11.99 to 15.00
        mock_ui_instance.review_and_edit.return_value = {
            'amount': 15.00,
            'description': 'Walmart Order (Groceries)',
            'date': datetime(2026, 5, 8)
        }
        mock_ui_instance.select_payer.return_value = "Jon Doe"
        mock_ui_instance.confirm_split.return_value = (True, 50.0)
        
        result = review_node(valid_state)
        
        assert result["review_data"].amount_override == 15.00
        assert result["expense_summary"].amount == 15.00
    
    def test_review_node_with_merchant_override(self, valid_state, mock_config, mock_ui):
        """Test review with user correcting the merchant description."""
        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        
        # User changes description
        mock_ui_instance.review_and_edit.return_value = {
            'amount': 11.99,
            'description': 'Walmart Order (Milk and Bread)',
            'date': datetime(2026, 5, 8)
        }
        mock_ui_instance.select_payer.return_value = "Jon Doe"
        mock_ui_instance.confirm_split.return_value = (True, 50.0)
        
        result = review_node(valid_state)
        
        assert result["review_data"].merchant_override == 'Walmart Order (Milk and Bread)'
        assert result["expense_summary"].merchant_description == 'Walmart Order (Milk and Bread)'
    
    def test_review_node_with_date_override(self, valid_state, mock_config, mock_ui):
        """Test review with user correcting the date."""
        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        
        # User changes date
        new_date = datetime(2026, 5, 10)
        mock_ui_instance.review_and_edit.return_value = {
            'amount': 11.99,
            'description': 'Walmart Order (Groceries)',
            'date': new_date
        }
        mock_ui_instance.select_payer.return_value = "Jon Doe"
        mock_ui_instance.confirm_split.return_value = (True, 50.0)
        
        result = review_node(valid_state)
        
        assert result["review_data"].date_override == new_date
        assert result["expense_summary"].date == new_date
    
    def test_review_node_partner_pays(self, valid_state, mock_config, mock_ui):
        """Test review when partner is selected as payer."""
        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        
        mock_ui_instance.review_and_edit.return_value = {
            'amount': 11.99,
            'description': 'Walmart Order (Groceries)',
            'date': datetime(2026, 5, 8)
        }
        mock_ui_instance.select_payer.return_value = "Jane Doe"
        mock_ui_instance.confirm_split.return_value = (True, 50.0)
        
        result = review_node(valid_state)
        
        assert result["review_data"].paid_by == "Jane Doe"
        assert result["expense_summary"].paid_by == "Jane Doe"
        # Split should be owed by Jon Doe (the non-payer)
        assert result["expense_summary"].splits[0].person == "Jon Doe"
    
    def test_review_node_no_split(self, valid_state, mock_config, mock_ui):
        """Test review when user chooses not to split."""
        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        
        mock_ui_instance.review_and_edit.return_value = {
            'amount': 11.99,
            'description': 'Walmart Order (Groceries)',
            'date': datetime(2026, 5, 8)
        }
        mock_ui_instance.select_payer.return_value = "Jon Doe"
        mock_ui_instance.confirm_split.return_value = (False, 0.0)
        
        result = review_node(valid_state)
        
        assert result["expense_summary"].splits is None
    
    def test_review_node_custom_split_percentage(self, valid_state, mock_config, mock_ui):
        """Test review with custom split percentage."""
        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        
        mock_ui_instance.review_and_edit.return_value = {
            'amount': 100.00,
            'description': 'Walmart Order (Groceries)',
            'date': datetime(2026, 5, 8)
        }
        mock_ui_instance.select_payer.return_value = "Jon Doe"
        mock_ui_instance.confirm_split.return_value = (True, 60.0)
        
        result = review_node(valid_state)
        
        assert result["expense_summary"].splits[0].share_percent == 60.0
    
    def test_review_node_generates_split_title(self, valid_state, mock_config, mock_ui):
        """Test that split title is properly generated."""
        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        
        mock_ui_instance.review_and_edit.return_value = {
            'amount': 11.99,
            'description': 'Walmart Order (Groceries)',
            'date': datetime(2026, 5, 8)
        }
        mock_ui_instance.select_payer.return_value = "Jon Doe"
        mock_ui_instance.confirm_split.return_value = (True, 50.0)
        
        result = review_node(valid_state)
        
        # Split should be: "Jane's Walmart Food Split (Groceries)"
        assert result["expense_summary"].splits[0].title == "Jane Doe's Walmart Food Split (Groceries)"
    
    def test_review_node_split_title_without_summary(self, valid_state, mock_config, mock_ui):
        """Test split title generation when description has no summary."""
        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        
        mock_ui_instance.review_and_edit.return_value = {
            'amount': 11.99,
            'description': 'Walmart Order',
            'date': datetime(2026, 5, 8)
        }
        mock_ui_instance.select_payer.return_value = "Jon Doe"
        mock_ui_instance.confirm_split.return_value = (True, 50.0)
        
        result = review_node(valid_state)
        
        # Split should be: "Jane's Walmart Food Split"
        assert result["expense_summary"].splits[0].title == "Jane Doe's Walmart Food Split"
    
    def test_review_node_generates_receipt_filename(self, valid_state, mock_config, mock_ui):
        """Test that receipt filename is properly generated."""
        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        
        mock_ui_instance.review_and_edit.return_value = {
            'amount': 11.99,
            'description': 'Walmart Order (Groceries)',
            'date': datetime(2026, 5, 8)
        }
        mock_ui_instance.select_payer.return_value = "Jon Doe"
        mock_ui_instance.confirm_split.return_value = (True, 50.0)
        
        result = review_node(valid_state)
        
        # Filename should be: 2026-05-08_Walmart_Order_Groceries_$11.99.pdf
        assert result["expense_summary"].receipt_filename == "2026-05-08_Walmart_Order_Groceries_$11.99.pdf"
    
    def test_review_node_displays_final_preview(self, valid_state, mock_config, mock_ui):
        """Test that final preview is displayed to user."""
        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        
        mock_ui_instance.review_and_edit.return_value = {
            'amount': 11.99,
            'description': 'Walmart Order (Groceries)',
            'date': datetime(2026, 5, 8)
        }
        mock_ui_instance.select_payer.return_value = "Jon Doe"
        mock_ui_instance.confirm_split.return_value = (True, 50.0)
        
        result = review_node(valid_state)
        
        # Verify display_final_preview was called
        mock_ui_instance.display_final_preview.assert_called_once()
        
        # Verify confirm_send_to_notion was called
        mock_ui_instance.confirm_send_to_notion.assert_called_once()
    
    def test_review_node_missing_required_field_from_ui(self, valid_state, mock_config, mock_ui):
        """Test failure when UI doesn't return required fields."""
        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        
        # UI returns incomplete data (missing 'amount')
        mock_ui_instance.review_and_edit.return_value = {
            'description': 'Walmart Order (Groceries)',
            'date': datetime(2026, 5, 8)
        }
        
        result = review_node(valid_state)
        
        assert result["status"] == WorkflowStatus.FAILED
        assert "did not return required fields" in result["failure_reason"]
    
    def test_review_node_receipt_without_summary(self, mock_config, mock_ui):
        """Test review when receipt has no summary."""
        receipt = Receipt(
            recipt_id='ORD-999',
            vendor='Netflix',
            transaction_type='Payment',
            summary='',
            date='2026-05-01',
            items=[],
            total=15.99
        )
        
        state = ReceiptWorkflowState(
            status=WorkflowStatus.VALIDATING,
            workflow_input=WorkflowInput(
                source=Sources.LOCAL_FOLDER,
                file_path="/path/to/receipt.pdf",
                raw_text="Sample text"
            ),
            receipt=receipt,
            enriched_receipt=None,
            validation_result=None,
            review_data=None,
            expense_summary=None,
            results=None,
            failure_reason=None
        )
        
        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        
        mock_ui_instance.review_and_edit.return_value = {
            'amount': 15.99,
            'description': 'Netflix',
            'date': datetime(2026, 5, 1)
        }
        mock_ui_instance.select_payer.return_value = "Jon Doe"
        mock_ui_instance.confirm_split.return_value = (True, 50.0)
        
        result = review_node(state)
        
        # Should handle missing summary gracefully
        assert result["expense_summary"].merchant_description == 'Netflix'
    
    def test_review_node_preserves_receipt_file_path(self, valid_state, mock_config, mock_ui):
        """Test that receipt file path is preserved in expense summary."""
        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        
        mock_ui_instance.review_and_edit.return_value = {
            'amount': 11.99,
            'description': 'Walmart Order (Groceries)',
            'date': datetime(2026, 5, 8)
        }
        mock_ui_instance.select_payer.return_value = "Jon Doe"
        mock_ui_instance.confirm_split.return_value = (True, 50.0)
        
        result = review_node(valid_state)

        assert result["expense_summary"].receipt_file_path == Path("/path/to/receipt.pdf")

    def test_review_node_displays_augment_summary_when_present(self, valid_state, mock_config, mock_ui):
        """Test that scan + augment narrative is shown with filled/missing detail."""
        valid_state["scan_results"] = ScanResults(
            has_missing_data=True, missing_fields=["date", "vendor"]
        )
        valid_state["augment_results"] = AugmentResults(
            filled_fields={"date": "llm_extraction"},
            still_missing=["vendor"]
        )

        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        mock_ui_instance.review_and_edit.return_value = {
            'amount': 11.99,
            'description': 'Walmart Order (Groceries)',
            'date': datetime(2026, 5, 8)
        }
        mock_ui_instance.select_payer.return_value = "Jon Doe"
        mock_ui_instance.confirm_split.return_value = (True, 50.0)

        review_node(valid_state)

        mock_ui_instance.display_scan_augment_summary.assert_called_once()
        _, kwargs = mock_ui_instance.display_scan_augment_summary.call_args
        assert kwargs["originally_missing"] == ["date", "vendor"]
        assert kwargs["filled_fields"] == {"date": "llm_extraction"}
        assert kwargs["still_missing"] == ["vendor"]

    def test_review_node_no_augment_summary_when_absent(self, valid_state, mock_config, mock_ui):
        """Test the scan summary is shown (clean) when no fields were missing."""
        # valid_state already has scan_results with no missing fields — panel still shown
        assert valid_state.get("augment_results") is None

        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        mock_ui_instance.review_and_edit.return_value = {
            'amount': 11.99,
            'description': 'Walmart Order (Groceries)',
            'date': datetime(2026, 5, 8)
        }
        mock_ui_instance.select_payer.return_value = "Jon Doe"
        mock_ui_instance.confirm_split.return_value = (True, 50.0)

        review_node(valid_state)

        # Panel is always shown on first pass when scan_results is present
        mock_ui_instance.display_scan_augment_summary.assert_called_once()
        _, kwargs = mock_ui_instance.display_scan_augment_summary.call_args
        assert kwargs["originally_missing"] == []
        assert kwargs["filled_fields"] == {}
        assert kwargs["still_missing"] == []

    def test_review_node_no_augment_summary_when_empty(self, valid_state, mock_config, mock_ui):
        """Test empty AugmentResults with scan showing no missing: panel shows clean state."""
        valid_state["augment_results"] = AugmentResults(filled_fields={}, still_missing=[])

        mock_ui_instance = Mock()
        mock_ui.return_value = mock_ui_instance
        mock_ui_instance.review_and_edit.return_value = {
            'amount': 11.99,
            'description': 'Walmart Order (Groceries)',
            'date': datetime(2026, 5, 8)
        }
        mock_ui_instance.select_payer.return_value = "Jon Doe"
        mock_ui_instance.confirm_split.return_value = (True, 50.0)

        review_node(valid_state)

        # Panel is shown on first pass (scan_results present), reporting clean state
        mock_ui_instance.display_scan_augment_summary.assert_called_once()
        _, kwargs = mock_ui_instance.display_scan_augment_summary.call_args
        assert kwargs["originally_missing"] == []
        assert kwargs["filled_fields"] == {}
        assert kwargs["still_missing"] == []


@pytest.mark.unit
def test_generated_description_uses_plain_words():
    from types import SimpleNamespace
    from workflows.langgraph.nodes.review_node import _receipt_description
    receipt = SimpleNamespace(
        vendor="Electrical Bill", transaction_type="Charge",
        summary="Electricity Charge, Bulk Bill HST, Electricity Charges (Delivery Charge)",
    )
    assert _receipt_description(receipt) == (
        "Electrical Bill Charge Electricity Charge Bulk Bill HST "
        "Electricity Charges Delivery Charge"
    )
