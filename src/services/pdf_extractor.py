"""PDF text extraction and parsing module."""
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import pdfplumber
from dateutil import parser as date_parser

from domain.models.receipt_item import ReceiptItem
from llm.client import ReceiptLLMClient
from logger import get_logger

logger = get_logger(__name__)


class PDFExtractor:
    """Extract and parse information from receipt PDFs."""
    
    def __init__(self, use_llm_for_items: bool = False):
        """
        Initialize PDF extractor.
        
        Args:
            use_llm_for_items: If True, use LLM to extract items. If False, use rule-based extraction.
        """
        self.use_llm_for_items = use_llm_for_items
        self.llm_client = None
        self.merchant_patterns = {
            'walmart': r'walmart',
            'amazon': r'amazon',
            'electrical': r'(hydro|electric|electricity|power|utility)',
            'rent': r'rent',
            'netflix': r'netflix',
            'youtube': r'youtube',
            'parking': r'parking',
            'longo': r"longo'?s",
            'tv': r'(television|tv|cable)',
        }
        
    def extract_text(self, pdf_path: Path) -> str:
        """Extract all text from a PDF file."""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                return text
        except Exception as e:
            raise Exception(f"Failed to extract text from PDF: {e}")
    
    def detect_merchant(self, text: str) -> tuple[str, str]:
        """
        Detect merchant type and name from text.
        Returns: (merchant_type, merchant_name)
        """
        text_lower = text.lower()
        
        for merchant_type, pattern in self.merchant_patterns.items():
            if re.search(pattern, text_lower):
                # Extract more specific merchant name
                if merchant_type == 'walmart':
                    return ('Order', 'Walmart')
                elif merchant_type == 'amazon':
                    return ('Order', 'Amazon')
                elif merchant_type == 'electrical':
                    return ('Charge', 'Electrical Bill')
                elif merchant_type == 'rent':
                    return ('Charge', 'Rent')
                elif merchant_type == 'netflix':
                    return ('Bill', 'Netflix')
                elif merchant_type == 'youtube':
                    return ('Bill', 'Youtube Premium')
                elif merchant_type == 'parking':
                    return ('parking', 'Parking')
                elif merchant_type == 'longo':
                    return ('expense', "Longo's")
        
        return ('unknown', 'Unknown Merchant')
    
    # Keywords that indicate a line should be excluded from total detection.
    # These appear on loyalty/rewards summaries or temporary hold lines that
    # must not be mistaken for the transaction total.
    _NOISE_KEYWORDS = ('hold', 'temporary', 'spent', 'savings', 'rewards', 'points')

    def extract_amount(self, text: str) -> Optional[float]:
        """Extract the total amount from receipt text.

        Strategy:
        1. Scan every line for one explicitly labelled "Total" (case-insensitive)
           that does NOT also contain a noise keyword (loyalty/hold lines).
           Return the first such amount found.
        2. Fall back to collecting all dollar amounts in the document and
           returning the largest one.
        """
        # --- Pass 1: look for a clean "Total" line ---
        total_line_pattern = re.compile(
            r'^[^\S\r\n]*total[^\S\r\n]*[\$:]?\s*(?:CA)?\$?\s*(\d+[,\d]*\.?\d{2})',
            re.IGNORECASE | re.MULTILINE,
        )
        for match in total_line_pattern.finditer(text):
            line = match.group(0)
            if not any(kw in line.lower() for kw in self._NOISE_KEYWORDS):
                amount_str = match.group(1).replace(',', '')
                try:
                    return float(amount_str)
                except ValueError:
                    continue

        # --- Pass 2: fall back to max of all amounts ---
        patterns = [
            r'(?:total|amount|grand total)[\s:]*(?:CA)?\$?\s*(\d+[,\d]*\.?\d{2})',
            r'(?:CA)?\$\s*(\d+[,\d]*\.\d{2})',
            r'(\d+[,\d]*\.\d{2})\s*(?:CAD|CA\$)',
        ]

        amounts = []
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                amount_str = match.group(1).replace(',', '')
                try:
                    amounts.append(float(amount_str))
                except ValueError:
                    continue

        return max(amounts) if amounts else None
    
    def extract_date(self, text: str) -> Optional[datetime]:
        """Extract date from receipt text."""
        # Look for date patterns - prioritize YYYY-MM-DD format
        date_patterns = [
            # YYYY-MM-DD or YYYY/MM/DD (ISO format - most unambiguous)
            # Use word boundaries to avoid matching partial dates
            # dayfirst=False is critical for YYYY-MM-DD format
            (r'\b(\d{4}[/-]\d{1,2}[/-]\d{1,2})\b', False, True),
            # Month name formats (e.g., Mar 04, 2026 or March 4, 2026)
            (r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})', False, True),
            # MM-DD-YYYY or DD-MM-YYYY (ambiguous - try yearfirst=True)
            # Only match if NOT preceded by a 4-digit year
            (r'(?<!\d)(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b', False, True),
        ]
        
        for pattern, dayfirst, yearfirst in date_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    date_str = match.group(1)
                    # Use yearfirst=True to prefer YYYY-MM-DD interpretation
                    parsed_date = date_parser.parse(date_str, dayfirst=dayfirst, yearfirst=yearfirst, fuzzy=True)
                    
                    # Sanity check: reject dates too far in the past or future
                    current_year = datetime.now().year
                    if parsed_date.year < 2000 or parsed_date.year > current_year + 10:
                        continue
                    
                    return parsed_date
                except (ValueError, TypeError):
                    continue
        
        return None
    
    # def extract_items_description(self, text: str, merchant_type: str) -> list:
    #     """Extract a description of items purchased based on merchant type."""
    #     text_lower = text.lower()
        
    #     # Common food items
    #     food_keywords = [
    #         'chicken', 'shrimp', 'salmon', 'beef', 'pork',
    #         'teriyaki', 'mediterranean', 'chipotle', 'greek',
    #         'soup', 'stir fry', 'krupnik', 'basics',
    #         'eggs', 'onion', 'fiber', 'hummus', 'tomato'
    #     ]
        
    #     # Amazon items
    #     amazon_keywords = [
    #         'scale', 'tray', 'bulbs', 'soda', 'club soda', 'baking sheet'
    #     ]
        
    #     found_items = []
        
    #     if merchant_type == 'walmart':
    #         for keyword in food_keywords:
    #             if keyword in text_lower:
    #                 found_items.append(keyword.title())
    #     elif merchant_type == 'amazon':
    #         for keyword in amazon_keywords:
    #             if keyword in text_lower:
    #                 found_items.append(keyword.title())
        
    #     return found_items
    
    @staticmethod
    def _build_summary(items: List[ReceiptItem]) -> str:
        """Return a comma-joined summary of the first three item names, or empty string."""
        if not items:
            return ""
        return ', '.join(item.name for item in items[:3])

    def extract_items(self, text: str) -> List[ReceiptItem]:
        """
        Extract individual items from receipt text.
        
        Uses LLM if use_llm_for_items is True, otherwise returns empty list.
        
        Args:
            text: Raw receipt text
            
        Returns:
            List of ReceiptItem objects
        """
        if not self.use_llm_for_items:
            return []
        
        try:
            # Initialize LLM client if needed
            if self.llm_client is None:
                self.llm_client = ReceiptLLMClient()
            
            # Call LLM to extract items
            result = self.llm_client.extract_items(text)
            items_data = result.get("items", [])
            
            # Convert to ReceiptItem objects
            grocery_items = []
            for item_data in items_data:
                try:
                    grocery_item = ReceiptItem(
                        name=item_data.get("name", "Unknown"),
                        price=float(item_data.get("price", 0.0)),
                        category=item_data.get("category")
                    )
                    grocery_items.append(grocery_item)
                except Exception as e:
                    logger.warning(f"Failed to parse item {item_data}: {e}")
                    continue
            
            return grocery_items
            
        except Exception as e:
            logger.warning(f"LLM item extraction failed: {e}")
            return []
    
    def parse_receipt(self, pdf_path: Path, raw_text: Optional[str] = None) -> Dict[str, Any]:
        """
        Parse a receipt PDF and extract all relevant information.
        Returns a dictionary with merchant, amount, date, and items.

        Args:
            pdf_path: Path to the receipt PDF (used for pdf_filename, and to
                extract text from if raw_text isn't already available)
            raw_text: Already-extracted text, if the caller has it. Skips a
                redundant re-extraction from disk when provided.
        """
        text = raw_text if raw_text is not None else self.extract_text(pdf_path)
        
        transaction_type, merchant_name = self.detect_merchant(text)
        amount = self.extract_amount(text)
        date = self.extract_date(text)
        
        # Extract items (uses LLM if enabled)
        items = self.extract_items(text)

        summary = self._build_summary(items)
        logger.debug(f"Full description: {merchant_name} {transaction_type} ({summary})" if summary else f"Full description: {merchant_name}")

        # TODO: Add support for order_id extraction
        # walmart example: 600000081236542
        # amazon example: 701-3765924-2833010
        # we should not imply merchant_type
        return {
            'order_id': None,
            'merchant_name': merchant_name,
            'transaction_type': transaction_type,
            'summary': summary,
            'items': items,
            'amount': amount,
            'date': date,
            'pdf_filename': pdf_path.name
        }

