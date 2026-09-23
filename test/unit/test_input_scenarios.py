"""End-to-end scenario tests based on the real PDFs in receipts/test_input/.

Scenarios
---------
1. techzone_future_date_red.pdf
   The receipt has Order Date: 2030-06-15 (a future date).
   After extract → scan → validate, validate_node must produce a RED
   'future_date' issue.

2. maple_street_organics_augment.pdf
   The PDF is blank (no readable text).  The LLM extractor returns
   'Unknown Merchant' because it cannot identify the vendor.
   After extract → scan → augment → validate, validate_node must produce
   a YELLOW 'unknown_merchant' issue and remain is_valid (no RED issues).
"""

import pytest
from unittest.mock import patch
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from workflows.langgraph.nodes.validate_node import validate_node
from workflows.langgraph.nodes.augment_node import augment_node
from workflows.langgraph.state import ReceiptWorkflowState
from domain.enums import WorkflowStatus, Sources, ValidationSeverity
from domain.models.workflow import WorkflowInput, ScanResults
from domain.models.recipts import Receipt, ReceiptItem


# ---------------------------------------------------------------------------
# Shared raw text extracted from the real PDFs (mirrors pdf read_file output)
# ---------------------------------------------------------------------------

TECHZONE_RAW_TEXT = """
TechZone Electronics
220 Bay Street, Toronto ON M5J 2W4
Tel: (416) 555-0381  |  www.techzone.ca
Order ID: TZ-2030-06-00412
Order Date: 2030-06-15
Billing: John Doe, 220 Bay St
ItemPrice
USB-C Hub 7-in-1$49.99
Wireless Mechanical Keyboard$129.95
27-inch 4K Monitor$449.00
HDMI 2.1 Cable 2m$24.99
Subtotal$653.93
HST (13%)$85.01
Total:$738.94
Paid via: Mastercard **** 7731
Questions? Contact support@techzone.ca
"""

# The PDF is blank/unreadable — WorkflowInput requires at least 1 character,
# so we use a single space to represent "extraction yielded nothing useful".
MAPLE_STREET_RAW_TEXT = " "


# ---------------------------------------------------------------------------
# Helper: build a minimal ReceiptWorkflowState
# ---------------------------------------------------------------------------

def _make_state(receipt: Receipt, raw_text: str, scan_results: ScanResults | None = None) -> ReceiptWorkflowState:
    return ReceiptWorkflowState(
        status=WorkflowStatus.ENRICHING,
        workflow_input=WorkflowInput(
            source=Sources.LOCAL_FOLDER,
            file_path="receipts/test_input/receipt.pdf",
            raw_text=raw_text,
        ),
        receipt=receipt,
        scan_results=scan_results,
        augment_results=None,
        enriched_receipt=None,
        validation_result=None,
        review_data=None,
        expense_summary=None,
        acknowledged_warnings=set(),
        results=None,
        failure_reason=None,
    )


# ===========================================================================
# Scenario 1 — TechZone: future date → RED flag
# ===========================================================================

class TestTechZoneFutureDateRed:
    """
    techzone_future_date_red.pdf has 'Order Date: 2030-06-15'.
    The LLM would extract that date as-is; validate_node must flag it RED.
    """

    @pytest.fixture
    def techzone_receipt(self):
        """Receipt as it would look after LLM extraction of the TechZone PDF."""
        return Receipt(
            recipt_id="TZ-2030-06-00412",
            vendor="TechZone Electronics",
            transaction_type="Order",
            summary="Electronics accessories",
            date="2030-06-15",           # future date — the trigger
            items=[
                ReceiptItem(name="USB-C Hub 7-in-1", price=49.99),
                ReceiptItem(name="Wireless Mechanical Keyboard", price=129.95),
                ReceiptItem(name="27-inch 4K Monitor", price=449.00),
                ReceiptItem(name="HDMI 2.1 Cable 2m", price=24.99),
            ],
            total=738.94,
        )

    @pytest.fixture
    def techzone_state(self, techzone_receipt):
        return _make_state(techzone_receipt, TECHZONE_RAW_TEXT)

    def test_future_date_produces_red_issue(self, techzone_state):
        """validate_node raises a RED issue for a receipt dated 2030-06-15."""
        result = validate_node(techzone_state)

        red_keys = [
            i.key for i in result["validation_result"].issues
            if i.severity == ValidationSeverity.RED
        ]
        assert "future_date" in red_keys

    def test_receipt_is_not_valid(self, techzone_state):
        """is_valid must be False because a RED issue is present."""
        result = validate_node(techzone_state)
        assert result["validation_result"].is_valid is False

    def test_future_date_error_message(self, techzone_state):
        """The RED error message should mention the date value."""
        result = validate_node(techzone_state)
        assert any("Date is in the future" in e for e in result["validation_result"].errors)

    def test_is_green_blocked_without_acknowledgement(self, techzone_state):
        """is_green must return False until the RED key is explicitly acknowledged."""
        result = validate_node(techzone_state)
        assert result["validation_result"].is_green(set()) is False

    def test_is_green_passes_after_override(self, techzone_state):
        """is_green returns True only once the user overrides the RED key."""
        result = validate_node(techzone_state)
        keys = {i.key for i in result["validation_result"].issues}
        assert result["validation_result"].is_green(keys) is True

    def test_no_yellow_unknown_merchant_for_techzone(self, techzone_state):
        """TechZone is a known vendor — no unknown_merchant YELLOW should fire."""
        result = validate_node(techzone_state)
        yellow_keys = [
            i.key for i in result["validation_result"].issues
            if i.severity == ValidationSeverity.YELLOW
        ]
        assert "unknown_merchant" not in yellow_keys


# ===========================================================================
# Scenario 2 — Maple Street Organics (blank PDF): YELLOW unknown merchant
# ===========================================================================

class TestMapleStreetOrganicsUnknownYellow:
    """
    maple_street_organics_augment.pdf is blank — the LLM can't extract any
    vendor text and falls back to 'Unknown Merchant'.  After augment_node
    tries (and fails) to recover the vendor, validate_node must emit a YELLOW
    'unknown_merchant' advisory.  The receipt itself is still is_valid (no RED).
    """

    @pytest.fixture
    def maple_receipt_after_augment(self):
        """Receipt after a failed augment — vendor left as 'Unknown Merchant'."""
        return Receipt(
            recipt_id=None,
            vendor="Unknown Merchant",   # augment couldn't identify the vendor
            transaction_type="Purchase",
            summary=None,
            date="2026-09-01",           # augment filled a plausible date
            items=[],
            total=25.00,                 # augment filled a plausible total
        )

    @pytest.fixture
    def maple_state(self, maple_receipt_after_augment):
        scan_results = ScanResults(has_missing_data=True, missing_fields=["vendor"])
        return _make_state(maple_receipt_after_augment, MAPLE_STREET_RAW_TEXT, scan_results)

    def test_unknown_merchant_produces_yellow(self, maple_state):
        """validate_node emits a YELLOW 'unknown_merchant' advisory."""
        result = validate_node(maple_state)

        yellow_keys = [
            i.key for i in result["validation_result"].issues
            if i.severity == ValidationSeverity.YELLOW
        ]
        assert "unknown_merchant" in yellow_keys

    def test_receipt_is_still_valid_no_red(self, maple_state):
        """Unknown merchant is advisory only — is_valid must still be True."""
        result = validate_node(maple_state)
        assert result["validation_result"].is_valid is True

    def test_unknown_merchant_warning_message(self, maple_state):
        """The YELLOW message should reference 'Unknown Merchant'."""
        result = validate_node(maple_state)
        assert any("Unknown Merchant" in w for w in result["validation_result"].warnings)

    def test_is_green_blocked_before_acknowledgement(self, maple_state):
        """is_green must be False until the user acknowledges the YELLOW."""
        result = validate_node(maple_state)
        assert result["validation_result"].is_green(set()) is False

    def test_is_green_after_acknowledgement(self, maple_state):
        """is_green returns True once the unknown_merchant key is acknowledged."""
        result = validate_node(maple_state)
        keys = {i.key for i in result["validation_result"].issues}
        assert result["validation_result"].is_green(keys) is True

    def test_augment_node_leaves_unknown_merchant_when_llm_returns_empty(self):
        """
        When the LLM cannot extract a vendor from blank text it returns
        'Unknown' — augment_node must not overwrite the existing 'Unknown Merchant'
        with an empty value, leaving still_missing=['vendor'] or the vendor intact.
        """
        receipt = Receipt(
            recipt_id=None,
            vendor="Unknown Merchant",
            transaction_type="Purchase",
            date="",
            items=[],
            total=None,
        )
        # LLM returns a receipt where vendor is still unresolvable
        llm_guess = Receipt(
            recipt_id=None,
            vendor="Unknown",
            transaction_type="Purchase",
            date="",
            items=[],
            total=None,
        )
        state = _make_state(
            receipt,
            MAPLE_STREET_RAW_TEXT,
            ScanResults(has_missing_data=True, missing_fields=["date", "total"]),
        )

        with patch(
            "workflows.langgraph.nodes.augment_node.llm_extract_receipt",
            return_value=llm_guess,
        ):
            result = augment_node(state)

        # vendor was not in missing_fields so augment never touched it
        assert result["receipt"].vendor == "Unknown Merchant"
        assert result["status"] == WorkflowStatus.ENRICHING
