"""
Unit tests for pdf_extractor.py
Tests PDF parsing logic with mocked file operations.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from pathlib import Path
from src.services.pdf_extractor import PDFExtractor


@pytest.fixture
def extractor():
    """Create a PDFExtractor instance for testing."""
    return PDFExtractor()


@pytest.fixture
def fixtures_dir():
    """Get the fixtures directory path."""
    return Path(__file__).parent.parent / "fixtures"


@pytest.mark.unit
class TestPDFExtractor:
    """Test PDF extraction functionality"""
    
    def test_extract_text_from_pdf_success(self, extractor, fixtures_dir):
        """Test successful text extraction from PDF"""
        pdf_path = fixtures_dir / "pdfs" / "2026-03-04_Walmart_Order_Meatballs_$80.59.pdf"
        text = extractor.extract_text(pdf_path)
        
        assert text is not None
        assert len(text) > 0
        assert "Walmart" in text or "walmart" in text.lower()
    
    def test_extract_text_from_invalid_pdf(self, extractor, tmp_path):
        """Test handling of invalid PDF file"""
        invalid_pdf = tmp_path / "invalid.pdf"
        invalid_pdf.write_text("This is not a valid PDF")
        
        with pytest.raises(Exception) as exc_info:
            extractor.extract_text(invalid_pdf)
        assert "Failed to extract text from PDF" in str(exc_info.value)
    
    def test_parse_receipt_data(self, extractor, fixtures_dir):
        """Test parsing receipt data from extracted text"""
        pdf_path = fixtures_dir / "pdfs" / "2026-03-04_Walmart_Order_Meatballs_$80.59.pdf"
        result = extractor.parse_receipt(pdf_path)
        
        assert result is not None
        assert 'merchant_name' in result
        assert 'amount' in result
        assert 'date' in result
        assert 'summary' in result
        assert 'items' in result
    
    def test_extract_date_yyyy_mm_dd_format(self, extractor):
        """Test date extraction from YYYY-MM-DD format"""
        text = "Order details - Walmart.ca 2026-03-04, 9:16 PM"
        date = extractor.extract_date(text)
        
        assert date is not None
        assert date.year == 2026
        assert date.month == 3
        assert date.day == 4
    
    def test_extract_date_month_name_format(self, extractor):
        """Test date extraction from month name format"""
        text = "Receipt Date: Mar 04, 2026"
        date = extractor.extract_date(text)
        
        assert date is not None
        assert date.year == 2026
        assert date.month == 3
        assert date.day == 4
    
    def test_extract_date_with_slash_separator(self, extractor):
        """Test date extraction with slash separator"""
        text = "Date: 2026/03/07"
        date = extractor.extract_date(text)
        
        assert date is not None
        assert date.year == 2026
        assert date.month == 3
        assert date.day == 7
    
    def test_extract_date_rejects_invalid_year(self, extractor):
        """Test that dates with invalid years are rejected"""
        # Test year too far in the past
        text = "Date: 1999-01-01"
        date = extractor.extract_date(text)
        assert date is None
        
        # Test year too far in the future
        text = "Date: 2050-01-01"
        date = extractor.extract_date(text)
        assert date is None
    
    def test_extract_date_no_match(self, extractor):
        """Test date extraction when no date is found"""
        text = "This text has no date in it"
        date = extractor.extract_date(text)
        
        assert date is None
    
    def test_extract_amount_from_text(self, extractor):
        """Test amount extraction from receipt text"""
        text = "Subtotal $72.68\nTaxes $4.32\nTotal $80.59"
        amount = extractor.extract_amount(text)
        
        assert amount is not None
        assert amount == 80.59
    
    def test_extract_amount_with_ca_prefix(self, extractor):
        """Test amount extraction with CA$ prefix"""
        text = "Total: CA$49.60"
        amount = extractor.extract_amount(text)
        
        assert amount is not None
        assert amount == 49.60
    
    def test_extract_amount_with_comma(self, extractor):
        """Test amount extraction with comma separator"""
        text = "Grand Total: $1,234.56"
        amount = extractor.extract_amount(text)
        
        assert amount is not None
        assert amount == 1234.56
    
    def test_extract_amount_no_match(self, extractor):
        """Test amount extraction when no amount is found"""
        text = "This text has no amount"
        amount = extractor.extract_amount(text)
        
        assert amount is None

    def test_extract_amount_walmart_with_temporary_hold(self, extractor):
        """Bug #33: Walmart receipts with a 'Temporary hold' must return the real total."""
        text = (
            "Subtotal $62.38\n"
            "Taxes $3.03\n"
            "Total $65.41\n"
            "Temporary hold $68.29\n"
            "Temporary hold\n"
            "$68.29\n"
        )
        amount = extractor.extract_amount(text)

        assert amount == 65.41, f"Expected 65.41 (real total) but got {amount}"

    def test_extract_amount_hold_higher_than_total_still_returns_total(self, extractor):
        """Bug #33: Temporary hold value higher than total must not win."""
        text = "Total $100.00\nTemporary hold $110.00"
        amount = extractor.extract_amount(text)

        assert amount == 100.00

    def test_extract_amount_no_hold_still_works(self, extractor):
        """Regression: normal receipts without a hold still extract correctly."""
        text = "Subtotal $72.68\nTaxes $4.32\nTotal $80.59"
        amount = extractor.extract_amount(text)

        assert amount == 80.59
    
    def test_detect_merchant_walmart(self, extractor):
        """Test Walmart merchant detection"""
        text = "Order details - Walmart.ca"
        merchant_type, merchant_name = extractor.detect_merchant(text)
        
        assert merchant_type == 'walmart'
        assert merchant_name == 'Walmart Order'
    
    def test_detect_merchant_amazon(self, extractor):
        """Test Amazon merchant detection"""
        text = "Amazon.com Order Receipt"
        merchant_type, merchant_name = extractor.detect_merchant(text)
        
        assert merchant_type == 'amazon'
        assert merchant_name == 'Amazon Order'
    
    def test_detect_merchant_unknown(self, extractor):
        """Test unknown merchant detection"""
        text = "Some Random Store Receipt"
        merchant_type, merchant_name = extractor.detect_merchant(text)
        
        assert merchant_type == 'unknown'
        assert merchant_name == 'Unknown Merchant'
    
    def test_extract_items_description_walmart(self, extractor):
        """Test item description extraction for Walmart"""
        text = "Chicken Breast\nBeef Ground\nSalmon Fillet"
        items = extractor.extract_items(text)
        
        # When LLM is disabled (default), should return empty list
        assert isinstance(items, list)
        assert len(items) == 0
    
    def test_extract_items_with_llm_enabled(self):
        """Test extracting items when LLM is enabled"""
        from unittest.mock import Mock, patch
        
        extractor = PDFExtractor(use_llm_for_items=True)
        text = "Amazon Order\nBaking Sheet Set $25.00\nKitchen Towels $10.00"
        
        # Mock the LLM client
        with patch.object(extractor, 'llm_client', None):
            with patch('src.services.pdf_extractor.ReceiptLLMClient') as mock_llm_class:
                mock_llm = Mock()
                mock_llm.extract_items.return_value = {
                    "items": [
                        {"name": "Baking Sheet Set", "price": 25.00, "category": "Kitchen"},
                        {"name": "Kitchen Towels", "price": 10.00, "category": "Kitchen"}
                    ]
                }
                mock_llm_class.return_value = mock_llm
                
                items = extractor.extract_items(text)
                
                assert isinstance(items, list)
                assert len(items) == 2
    
    def test_extract_items_llm_failure(self):
        """Test extracting items when LLM fails"""
        from unittest.mock import Mock, patch
        
        extractor = PDFExtractor(use_llm_for_items=True)
        text = "Some text"
        
        with patch.object(extractor, 'llm_client', None):
            with patch('src.services.pdf_extractor.ReceiptLLMClient') as mock_llm_class:
                mock_llm = Mock()
                mock_llm.extract_items.side_effect = Exception("LLM error")
                mock_llm_class.return_value = mock_llm
                
                items = extractor.extract_items(text)
                
                # Should return empty list on error
                assert isinstance(items, list)
                assert len(items) == 0
    
    def test_parse_receipt_walmart_pdf(self, extractor, fixtures_dir):
        """Test parsing complete Walmart receipt PDF"""
        pdf_path = fixtures_dir / "pdfs" / "2026-03-04_Walmart_Order_Meatballs_$80.59.pdf"
        result = extractor.parse_receipt(pdf_path)
        
        assert result['merchant_name'] == 'Walmart Order'
        assert result['amount'] == 80.59
        assert result['date'] is not None
        assert result['date'].year == 2026
        assert result['date'].month == 3
        assert result['date'].day == 4
        assert result['pdf_filename'] == "2026-03-04_Walmart_Order_Meatballs_$80.59.pdf"
        assert 'summary' in result
        assert 'items' in result
    
    def test_parse_receipt_amazon_pdf(self, extractor, fixtures_dir):
        """Test parsing complete Amazon receipt PDF"""
        pdf_path = fixtures_dir / "pdfs" / "2026-03-07_Amazon_Order_Baking_Sheets_$49.60.pdf"
        result = extractor.parse_receipt(pdf_path)
        
        assert result['merchant_name'] == 'Amazon Order'
        assert result['amount'] == 49.60
        assert result['date'] is not None
        assert result['date'].year == 2026
        assert result['date'].month == 3
        assert result['date'].day == 7
        assert result['pdf_filename'] == "2026-03-07_Amazon_Order_Baking_Sheets_$49.60.pdf"
        assert 'summary' in result
        assert 'items' in result
    
    def test_date_extraction_bug_fix(self, extractor):
        """Test that the date extraction bug is fixed (issue #1)"""
        # This was the bug: 2026-03-04 was being parsed as 2004-03-26
        text = "Order date: 2026-03-04"
        date = extractor.extract_date(text)
        
        assert date is not None
        assert date.year == 2026, f"Expected year 2026, got {date.year}"
        assert date.month == 3, f"Expected month 3, got {date.month}"
        assert date.day == 4, f"Expected day 4, got {date.day}"
        
        # Test another date to ensure consistency
        text2 = "Order date: 2026-03-07"
        date2 = extractor.extract_date(text2)
        
        assert date2 is not None
        assert date2.year == 2026
        assert date2.month == 3
        assert date2.day == 7


