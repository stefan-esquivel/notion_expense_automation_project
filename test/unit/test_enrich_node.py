"""Unit tests for enrich_node.py"""

import pytest
from unittest.mock import patch
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from workflows.langgraph.nodes.enrich_node import (
    enrich_node,
    _confidence_band,
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM_LOW,
)
from workflows.langgraph.state import ReceiptWorkflowState
from domain.enums import WorkflowStatus, Sources
from domain.models.workflow import WorkflowInput
from domain.models.recipts import Receipt, ReceiptItem
from domain.models.enrichment import EnrichedReceipt
from llm.receipt_extractor import FALLBACK_CONFIDENCE


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_state(receipt=None, scan_results=None, augment_results=None):
    """Build a minimal valid ReceiptWorkflowState."""
    return ReceiptWorkflowState(
        status=WorkflowStatus.EXTRACTING,
        workflow_input=WorkflowInput(
            source=Sources.LOCAL_FOLDER,
            file_path="/path/to/receipt.pdf",
            raw_text="Sample text",
        ),
        receipt=receipt,
        scan_results=scan_results,
        augment_results=augment_results,
        enriched_receipt=None,
        validation_result=None,
        acknowledged_warnings=set(),
        review_data=None,
        expense_summary=None,
        results=None,
        failure_reason=None,
    )


@pytest.fixture
def valid_receipt():
    return Receipt(
        recipt_id="ORD-12345",
        vendor="Walmart",
        transaction_type="Order",
        summary="Groceries",
        date="2026-05-08",
        items=[
            ReceiptItem(name="Milk", price=4.99),
            ReceiptItem(name="Bread", price=3.50),
        ],
        total=11.99,
    )


@pytest.fixture
def valid_state(valid_receipt):
    return _make_state(receipt=valid_receipt)


@pytest.fixture
def sample_enriched_receipt():
    return EnrichedReceipt(
        merchant_category="grocery",
        confidence_score=0.95,
        notes="High confidence categorization",
    )


@pytest.fixture
def mock_llm_enrich():
    with patch("workflows.langgraph.nodes.enrich_node.llm_enrich_receipt") as mock:
        yield mock


@pytest.fixture
def mock_keyword_enrich():
    with patch("workflows.langgraph.nodes.enrich_node.keyword_enrich_receipt") as mock:
        yield mock


# ===========================================================================
# Original tests (unchanged)
# ===========================================================================

class TestEnrichNodeCore:
    """Core enrich_node behaviour — original test suite."""

    def test_enrich_node_success(self, valid_state, mock_llm_enrich, sample_enriched_receipt):
        mock_llm_enrich.return_value = sample_enriched_receipt
        result = enrich_node(valid_state)

        assert result["status"] == WorkflowStatus.ENRICHING
        assert result["enriched_receipt"] is not None
        assert result["enriched_receipt"].merchant_category == "grocery"
        assert result["enriched_receipt"].confidence_score == 0.95
        assert result["enriched_receipt"].notes == "High confidence categorization"
        assert result["failure_reason"] is None
        mock_llm_enrich.assert_called_once_with(valid_state["receipt"])

    def test_enrich_node_updates_status(self, valid_state, mock_llm_enrich, sample_enriched_receipt):
        mock_llm_enrich.return_value = sample_enriched_receipt
        assert valid_state["status"] == WorkflowStatus.EXTRACTING
        result = enrich_node(valid_state)
        assert result["status"] == WorkflowStatus.ENRICHING

    def test_enrich_node_no_receipt(self, mock_llm_enrich):
        state = _make_state(receipt=None)
        result = enrich_node(state)

        assert result["status"] == WorkflowStatus.FAILED
        assert "No receipt data found" in result["failure_reason"]
        mock_llm_enrich.assert_not_called()

    def test_enrich_node_with_notes(self, valid_state, mock_llm_enrich):
        enriched = EnrichedReceipt(
            merchant_category="utility",
            confidence_score=0.88,
            notes="Electrical bill detected from merchant name pattern",
        )
        mock_llm_enrich.return_value = enriched
        result = enrich_node(valid_state)
        assert "Electrical bill" in result["enriched_receipt"].notes

    def test_enrich_node_without_notes(self, valid_state, mock_llm_enrich):
        mock_llm_enrich.return_value = EnrichedReceipt(
            merchant_category="grocery",
            confidence_score=0.95,
            notes=None,
        )
        result = enrich_node(valid_state)
        assert result["enriched_receipt"].notes is None

    def test_enrich_node_logs_enrichment_info(self, valid_state, mock_llm_enrich, sample_enriched_receipt):
        mock_llm_enrich.return_value = sample_enriched_receipt
        with patch("workflows.langgraph.nodes.enrich_node.logger") as mock_logger:
            enrich_node(valid_state)
            assert mock_logger.info.call_count >= 2
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any("Enriching receipt" in c for c in log_calls)
            assert any("Categorized as" in c for c in log_calls)

    def test_enrich_node_logs_notes_when_present(self, valid_state, mock_llm_enrich):
        mock_llm_enrich.return_value = EnrichedReceipt(
            merchant_category="subscription",
            confidence_score=0.92,
            notes="Netflix subscription detected",
        )
        with patch("workflows.langgraph.nodes.enrich_node.logger") as mock_logger:
            enrich_node(valid_state)
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any("Notes:" in c for c in log_calls)

    def test_enrich_node_different_categories(self, valid_state, mock_llm_enrich):
        for category in ["grocery", "utility", "subscription", "entertainment", "transportation", "healthcare"]:
            mock_llm_enrich.return_value = EnrichedReceipt(
                merchant_category=category,
                confidence_score=0.9,
                notes=f"Categorized as {category}",
            )
            result = enrich_node(valid_state)
            assert result["enriched_receipt"].merchant_category == category

    def test_enrich_node_preserves_receipt_data(self, valid_state, mock_llm_enrich, sample_enriched_receipt):
        mock_llm_enrich.return_value = sample_enriched_receipt
        original_receipt = valid_state["receipt"]
        result = enrich_node(valid_state)
        assert result["receipt"] == original_receipt
        assert result["receipt"].vendor == "Walmart"
        assert result["receipt"].total == 11.99

    def test_enrich_node_high_confidence_threshold(self, valid_state, mock_llm_enrich):
        mock_llm_enrich.return_value = EnrichedReceipt(
            merchant_category="grocery",
            confidence_score=0.99,
            notes="Very clear categorization",
        )
        result = enrich_node(valid_state)
        assert result["enriched_receipt"].confidence_score >= 0.95

    def test_enrich_node_edge_case_zero_confidence(self, valid_state, mock_llm_enrich):
        mock_llm_enrich.return_value = EnrichedReceipt(
            merchant_category="other",
            confidence_score=0.0,
            notes="Unable to categorize",
        )
        result = enrich_node(valid_state)
        assert result["status"] == WorkflowStatus.ENRICHING
        assert result["enriched_receipt"].confidence_score == 0.0


# ===========================================================================
# Confidence-band helper tests
# ===========================================================================

class TestConfidenceBand:
    """Unit tests for the _confidence_band helper."""

    def test_high_band_at_threshold(self):
        assert _confidence_band(CONFIDENCE_HIGH) == "high"

    def test_high_band_above_threshold(self):
        assert _confidence_band(1.0) == "high"
        assert _confidence_band(0.90) == "high"

    def test_medium_band_at_lower_threshold(self):
        assert _confidence_band(CONFIDENCE_MEDIUM_LOW) == "medium"

    def test_medium_band_in_range(self):
        assert _confidence_band(0.75) == "medium"
        assert _confidence_band(0.84) == "medium"

    def test_low_band_below_medium(self):
        assert _confidence_band(0.59) == "low"
        assert _confidence_band(0.0) == "low"
        assert _confidence_band(0.30) == "low"

    def test_boundary_just_below_high(self):
        # 0.849 is still "medium"
        assert _confidence_band(0.849) == "medium"

    def test_boundary_just_below_medium(self):
        # 0.599 is still "low"
        assert _confidence_band(0.599) == "low"


# ===========================================================================
# Fallback strategy tests
# ===========================================================================

class TestEnrichNodeFallback:
    """Tests for the keyword-matching fallback path."""

    def test_llm_failure_triggers_fallback(self, valid_state, mock_llm_enrich, mock_keyword_enrich):
        """When LLM raises, keyword_enrich_receipt is called instead."""
        mock_llm_enrich.side_effect = Exception("LLM API error")
        mock_keyword_enrich.return_value = EnrichedReceipt(
            merchant_category="grocery",
            confidence_score=FALLBACK_CONFIDENCE,
            notes="keyword-matching fallback (LLM unavailable)",
        )

        result = enrich_node(valid_state)

        mock_keyword_enrich.assert_called_once_with(valid_state["receipt"])
        assert result["enriched_receipt"] is not None
        assert result["enriched_receipt"].confidence_score == FALLBACK_CONFIDENCE

    def test_fallback_does_not_fail_workflow(self, valid_state, mock_llm_enrich, mock_keyword_enrich):
        """Fallback path must NOT set status=FAILED."""
        mock_llm_enrich.side_effect = RuntimeError("timeout")
        mock_keyword_enrich.return_value = EnrichedReceipt(
            merchant_category="other",
            confidence_score=FALLBACK_CONFIDENCE,
            notes="keyword fallback",
        )

        result = enrich_node(valid_state)

        assert result["status"] == WorkflowStatus.ENRICHING
        assert result["failure_reason"] is None

    def test_fallback_confidence_is_0_5(self, valid_state, mock_llm_enrich, mock_keyword_enrich):
        """Fallback must produce exactly FALLBACK_CONFIDENCE (0.5)."""
        mock_llm_enrich.side_effect = Exception("network error")
        mock_keyword_enrich.return_value = EnrichedReceipt(
            merchant_category="retail",
            confidence_score=FALLBACK_CONFIDENCE,
            notes="keyword fallback",
        )

        result = enrich_node(valid_state)

        assert result["enriched_receipt"].confidence_score == 0.5

    def test_fallback_logs_warning(self, valid_state, mock_llm_enrich, mock_keyword_enrich):
        """A warning should be logged when the LLM fails."""
        mock_llm_enrich.side_effect = Exception("LLM down")
        mock_keyword_enrich.return_value = EnrichedReceipt(
            merchant_category="other",
            confidence_score=FALLBACK_CONFIDENCE,
            notes="keyword fallback",
        )

        with patch("workflows.langgraph.nodes.enrich_node.logger") as mock_logger:
            enrich_node(valid_state)
            warning_calls = [str(c) for c in mock_logger.warning.call_args_list]
            assert any("LLM enrichment failed" in c for c in warning_calls)
            assert any("keyword matching" in c for c in warning_calls)

    def test_fallback_enriched_receipt_stored_in_state(self, valid_state, mock_llm_enrich, mock_keyword_enrich):
        """Fallback result is stored in state["enriched_receipt"]."""
        mock_llm_enrich.side_effect = Exception("error")
        fallback_result = EnrichedReceipt(
            merchant_category="grocery",
            confidence_score=FALLBACK_CONFIDENCE,
            notes="keyword fallback",
        )
        mock_keyword_enrich.return_value = fallback_result

        result = enrich_node(valid_state)

        assert result["enriched_receipt"] is fallback_result


# ===========================================================================
# keyword_enrich_receipt unit tests
# ===========================================================================

class TestKeywordEnrichReceipt:
    """Unit tests for the keyword-matching fallback function itself."""

    from llm.receipt_extractor import keyword_enrich_receipt as _fn

    def _make_receipt(self, vendor: str) -> Receipt:
        return Receipt(
            vendor=vendor,
            transaction_type="Purchase",
            date="2026-01-01",
            total=10.00,
        )

    def test_walmart_is_grocery(self):
        from llm.receipt_extractor import keyword_enrich_receipt
        r = self._make_receipt("Walmart Supercenter")
        result = keyword_enrich_receipt(r)
        assert result.merchant_category == "grocery"
        assert result.confidence_score == FALLBACK_CONFIDENCE

    def test_amazon_is_retail(self):
        from llm.receipt_extractor import keyword_enrich_receipt
        r = self._make_receipt("Amazon.ca")
        result = keyword_enrich_receipt(r)
        assert result.merchant_category == "retail"

    def test_longo_is_grocery(self):
        from llm.receipt_extractor import keyword_enrich_receipt
        r = self._make_receipt("Longo's")
        result = keyword_enrich_receipt(r)
        assert result.merchant_category == "grocery"

    def test_hydro_is_utility(self):
        from llm.receipt_extractor import keyword_enrich_receipt
        r = self._make_receipt("BC Hydro")
        result = keyword_enrich_receipt(r)
        assert result.merchant_category == "utility"

    def test_netflix_is_subscription(self):
        from llm.receipt_extractor import keyword_enrich_receipt
        r = self._make_receipt("Netflix")
        result = keyword_enrich_receipt(r)
        assert result.merchant_category == "subscription"

    def test_parking_is_transportation(self):
        from llm.receipt_extractor import keyword_enrich_receipt
        r = self._make_receipt("Impark Parking")
        result = keyword_enrich_receipt(r)
        assert result.merchant_category == "transportation"

    def test_unknown_merchant_returns_other(self):
        from llm.receipt_extractor import keyword_enrich_receipt
        r = self._make_receipt("ZzZz Unknown Shop")
        result = keyword_enrich_receipt(r)
        assert result.merchant_category == "other"
        assert result.confidence_score == FALLBACK_CONFIDENCE

    def test_all_fallback_results_have_fallback_confidence(self):
        from llm.receipt_extractor import keyword_enrich_receipt
        for vendor in ["Walmart", "Amazon", "Netflix", "Parking Lot", "Some Random Store"]:
            r = self._make_receipt(vendor)
            result = keyword_enrich_receipt(r)
            assert result.confidence_score == FALLBACK_CONFIDENCE, (
                f"Expected FALLBACK_CONFIDENCE for vendor={vendor!r}, "
                f"got {result.confidence_score}"
            )

    def test_case_insensitive_matching(self):
        from llm.receipt_extractor import keyword_enrich_receipt
        r = self._make_receipt("WALMART SUPERCENTER #1234")
        result = keyword_enrich_receipt(r)
        assert result.merchant_category == "grocery"

    def test_notes_mention_fallback(self):
        from llm.receipt_extractor import keyword_enrich_receipt
        r = self._make_receipt("Walmart")
        result = keyword_enrich_receipt(r)
        assert result.notes is not None
        assert "fallback" in result.notes.lower()
