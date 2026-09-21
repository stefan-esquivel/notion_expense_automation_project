"""
Integration tests for PDF extraction scenarios.

These tests run PDFExtractor.parse_receipt() against real PDF fixtures stored in
test/fixtures/pdfs/ — no mocks, no external API calls.  They are the right level
for verifying that the full text-extraction + parsing pipeline produces correct
results on known inputs.
"""
import pytest
from pathlib import Path
from src.services.pdf_extractor import PDFExtractor


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
PDF_FIXTURES = FIXTURES_DIR / "pdfs"


@pytest.fixture(scope="module")
def extractor():
    """Shared PDFExtractor instance for all tests in this module."""
    return PDFExtractor()


@pytest.mark.integration
class TestLongosLoyaltyReceiptExtraction:
    """
    Regression tests for issue #47.

    The Longo's receipt fixture contains a loyalty-rewards section that prints
    'Total spent  $103.01' — a cumulative weekly running total, not the
    transaction amount.  The correct transaction total is $59.90.

    Fixture: test/fixtures/pdfs/2026-09-19_Longos_Groceries_English_Cucumbers_Dill_Weed_Grape_Tomatoes_$59.90.pdf
    Source text (PII-scrubbed): test/fixtures/text/longos_loyalty_receipt.txt

    The fixture was generated from the scrubbed text file; all personal details
    (name, e-mail, phone, card digits, auth codes) have been replaced with
    generic placeholders.
    """

    FIXTURE_PDF = (
        PDF_FIXTURES
        / "2026-09-19_Longos_Groceries_English_Cucumbers_Dill_Weed_Grape_Tomatoes_$59.90.pdf"
    )

    def test_fixture_exists(self):
        """Confirm the fixture PDF is present so subsequent tests have a useful failure message."""
        assert self.FIXTURE_PDF.exists(), (
            f"Fixture PDF not found: {self.FIXTURE_PDF}\n"
            "Re-generate it by running the script in test/fixtures/text/longos_loyalty_receipt.txt"
        )

    def test_amount_is_transaction_total_not_loyalty_total(self, extractor):
        """
        extract_amount() must return the transaction Total ($59.90), not the
        loyalty-section 'Total spent' ($103.01).
        """
        result = extractor.parse_receipt(self.FIXTURE_PDF)
        assert result["amount"] == 59.90, (
            f"Expected transaction total 59.90, got {result['amount']}. "
            "The loyalty 'Total spent' line ($103.01) is leaking through."
        )

    def test_merchant_detected_as_longo(self, extractor):
        """Merchant and transaction type follow the workflow extractor contract."""
        result = extractor.parse_receipt(self.FIXTURE_PDF)
        assert result["transaction_type"] == "expense"
        assert result["merchant_name"] == "Longo's"

    def test_date_extracted_correctly(self, extractor):
        """Date must be parsed as 2026-09-19."""
        result = extractor.parse_receipt(self.FIXTURE_PDF)
        assert result["date"] is not None, "No date was extracted from the fixture"
        assert result["date"].year == 2026
        assert result["date"].month == 9
        assert result["date"].day == 19

    def test_loyalty_amount_not_present_in_result(self, extractor):
        """
        The loyalty 'Total spent' value ($103.01) must not appear anywhere as
        the extracted amount.
        """
        result = extractor.parse_receipt(self.FIXTURE_PDF)
        assert result["amount"] != 103.01, (
            "Extracted amount is 103.01, which is the loyalty running total — not the transaction total."
        )
