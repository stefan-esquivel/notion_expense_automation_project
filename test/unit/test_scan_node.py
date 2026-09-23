"""Unit tests for scan_node.py"""

import pytest
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from workflows.langgraph.nodes.scan_node import scan_node
from workflows.langgraph.state import ReceiptWorkflowState
from domain.enums import WorkflowStatus, Sources
from domain.models.workflow import WorkflowInput
from domain.models.recipts import Receipt, ReceiptItem


class TestScanNode:
    """Test suite for scan_node functionality."""

    @pytest.fixture
    def valid_receipt(self):
        """Create a receipt with all required fields present."""
        return Receipt(
            recipt_id='ORD-12345',
            vendor='Walmart',
            transaction_type='Order',
            summary='Groceries',
            date='2026-05-08',
            items=[ReceiptItem(name='Milk', price=4.99)],
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
            scan_results=None,
            augment_results=None,
            enriched_receipt=None,
            validation_result=None,
            review_data=None,
            expense_summary=None,
            results=None,
            failure_reason=None
        )

    def test_scan_node_no_missing_fields(self, valid_state):
        """Test scan finds nothing missing on a complete receipt."""
        result = scan_node(valid_state)

        assert result["status"] == WorkflowStatus.SCANNING
        assert result["scan_results"] is not None
        assert result["scan_results"].has_missing_data is False
        assert result["scan_results"].missing_fields == []
        assert result["failure_reason"] is None

    def test_scan_node_missing_date(self, valid_state):
        """Test scan detects a missing date."""
        valid_state["receipt"].date = ""

        result = scan_node(valid_state)

        assert result["scan_results"].has_missing_data is True
        assert result["scan_results"].missing_fields == ["date"]

    def test_scan_node_missing_vendor_and_date(self, valid_state):
        """Test scan detects multiple missing fields."""
        valid_state["receipt"].vendor = ""
        valid_state["receipt"].date = ""

        result = scan_node(valid_state)

        assert result["scan_results"].has_missing_data is True
        assert result["scan_results"].missing_fields == ["vendor", "date"]

    def test_scan_node_no_receipt(self):
        """Test failure when no receipt is in state."""
        state = ReceiptWorkflowState(
            status=WorkflowStatus.EXTRACTING,
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

        result = scan_node(state)

        assert result["status"] == WorkflowStatus.FAILED
        assert "No receipt data found" in result["failure_reason"]
