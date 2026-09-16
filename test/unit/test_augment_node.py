"""Unit tests for augment_node.py"""

import pytest
from unittest.mock import Mock, patch
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from workflows.langgraph.nodes.augment_node import augment_node
from workflows.langgraph.state import ReceiptWorkflowState
from domain.enums import WorkflowStatus, Sources
from domain.models.workflow import WorkflowInput, ScanResults
from domain.models.recipts import Receipt, ReceiptItem


class TestAugmentNode:
    """Test suite for augment_node functionality."""

    @pytest.fixture
    def receipt_missing_date(self):
        """Create a receipt missing its date."""
        return Receipt(
            recipt_id='ORD-12345',
            vendor='Walmart',
            transaction_type='Order',
            summary='Groceries',
            date='',
            items=[ReceiptItem(name='Milk', price=4.99)],
            total=11.99
        )

    @pytest.fixture
    def valid_state(self, receipt_missing_date):
        """Create a state with scan_results flagging the missing date."""
        return ReceiptWorkflowState(
            status=WorkflowStatus.SCANNING,
            workflow_input=WorkflowInput(
                source=Sources.LOCAL_FOLDER,
                file_path="/path/to/receipt.pdf",
                raw_text="Sample receipt text"
            ),
            receipt=receipt_missing_date,
            scan_results=ScanResults(has_missing_data=True, missing_fields=["date"]),
            augment_results=None,
            enriched_receipt=None,
            validation_result=None,
            review_data=None,
            expense_summary=None,
            results=None,
            failure_reason=None
        )

    def test_augment_node_fills_missing_date(self, valid_state):
        """Test augment fills a missing date via LLM re-extraction."""
        llm_guess = Receipt(
            recipt_id='ORD-99999',
            vendor='Walmart',
            transaction_type='Order',
            date='2026-05-08',
            items=[],
            total=11.99
        )

        with patch('workflows.langgraph.nodes.augment_node.llm_extract_receipt', return_value=llm_guess):
            result = augment_node(valid_state)

        assert result["status"] == WorkflowStatus.ENRICHING
        assert result["receipt"].date == "2026-05-08"
        assert result["augment_results"].filled_fields == {"date": "llm_extraction"}
        assert result["augment_results"].still_missing == []

    def test_augment_node_llm_also_missing_field(self, valid_state):
        """Test a field stays in still_missing if the LLM guess is also empty."""
        llm_guess = Receipt(
            recipt_id='ORD-99999',
            vendor='Walmart',
            transaction_type='Order',
            date='',
            items=[],
            total=11.99
        )

        with patch('workflows.langgraph.nodes.augment_node.llm_extract_receipt', return_value=llm_guess):
            result = augment_node(valid_state)

        assert result["augment_results"].filled_fields == {}
        assert result["augment_results"].still_missing == ["date"]

    def test_augment_node_llm_raises(self, valid_state):
        """Test the node doesn't fail outright if the LLM call itself errors."""
        with patch(
            'workflows.langgraph.nodes.augment_node.llm_extract_receipt',
            side_effect=Exception("LLM unavailable")
        ):
            result = augment_node(valid_state)

        assert result["status"] == WorkflowStatus.ENRICHING
        assert result["augment_results"].filled_fields == {}
        assert result["augment_results"].still_missing == ["date"]

    def test_augment_node_no_missing_fields(self, valid_state):
        """Test augment is a no-op when scan found nothing missing."""
        valid_state["receipt"].date = "2026-05-08"
        valid_state["scan_results"] = ScanResults(has_missing_data=False, missing_fields=[])

        with patch('workflows.langgraph.nodes.augment_node.llm_extract_receipt') as mock_llm:
            result = augment_node(valid_state)

        mock_llm.assert_not_called()
        assert result["augment_results"].filled_fields == {}
        assert result["augment_results"].still_missing == []

    def test_augment_node_falls_back_without_scan_results(self, valid_state):
        """Test augment derives missing fields itself if scan_results is None."""
        valid_state["scan_results"] = None
        llm_guess = Receipt(
            recipt_id='ORD-99999',
            vendor='Walmart',
            transaction_type='Order',
            date='2026-05-08',
            items=[],
            total=11.99
        )

        with patch('workflows.langgraph.nodes.augment_node.llm_extract_receipt', return_value=llm_guess):
            result = augment_node(valid_state)

        assert result["augment_results"].filled_fields == {"date": "llm_extraction"}

    def test_augment_node_no_receipt(self):
        """Test failure when no receipt is in state."""
        state = ReceiptWorkflowState(
            status=WorkflowStatus.SCANNING,
            workflow_input=None,
            receipt=None,
            scan_results=None,
            augment_results=None,
            enriched_receipt=None,
            validation_result=None,
            review_data=None,
            expense_summary=None,
            results=None,
            failure_reason=None
        )

        result = augment_node(state)

        assert result["status"] == WorkflowStatus.FAILED
        assert "No receipt data found" in result["failure_reason"]
