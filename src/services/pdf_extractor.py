"""PDF text extraction and parsing module."""
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import pdfplumber
from dateutil import parser as date_parser

from domain.models.grocery import GroceryItem
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
                    return ('walmart', 'Walmart Order')
                elif merchant_type == 'amazon':
                    return ('amazon', 'Amazon Order')
                elif merchant_type == 'electrical':
                    return ('electrical', 'Electrical Bill')
                elif merchant_type == 'rent':
                    return ('rent', 'Rent')
                elif merchant_type == 'netflix':
                    return ('netflix', 'Netflix')
                elif merchant_type == 'youtube':
                    return ('youtube', 'Youtube Premium')
                elif merchant_type == 'parking':
                    return ('parking', 'Parking')
                elif merchant_type == 'longo':
                    return ('longo', "Longo's Groceries")
                elif merchant_type == 'tv':
                    return ('tv', 'TV Payment')
        
        return ('unknown', 'Unknown Merchant')
    
    def extract_amount(self, text: str) -> Optional[float]:
        """Extract the total amount from receipt text.

        Strategy:
        1. Look for an amount on a line explicitly labelled 'Total' / 'Grand Total' /
           'Amount', skipping any line that also contains 'hold' or 'temporary'
           (e.g. Walmart's 'Temporary hold' lines).
        2. Fall back to the largest amount found in the document if no clean
           labelled total is present.
        """
        # --- Pass 1: labelled total on a non-hold line ---
        # Use \b so that 'Subtotal' does NOT match — only a standalone 'Total' / 'Grand Total' / 'Amount' word.
        labelled_pattern = re.compile(
            r'\b(?:grand total|total|amount)\b[\s:]*(?:CA)?\$?\s*(\d+[,\d]*\.?\d{2})',
            re.IGNORECASE,
        )
        for line in text.splitlines():
            # Skip lines that are temporary holds or discounts
            if re.search(r'(temporary|hold)', line, re.IGNORECASE):
                continue
            match = labelled_pattern.search(line)
            if match:
                try:
                    return float(match.group(1).replace(',', ''))
                except ValueError:
                    continue

        # --- Pass 2: fallback — collect all amounts and return the largest ---
        fallback_patterns = [
            r'(?:total|amount|grand total)[\s:]*(?:CA)?\$?\s*(\d+[,\d]*\.?\d{2})',
            r'(?:CA)?\$\s*(\d+[,\d]*\.\d{2})',
            r'(\d+[,\d]*\.\d{2})\s*(?:CAD|CA\$)',
        ]
        amounts = []
        for pattern in fallback_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    amounts.append(float(match.group(1).replace(',', '')))
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
    
    def extract_items(self, text: str) -> List[GroceryItem]:
        """
        Extract individual items from receipt text.
        
        Uses LLM if use_llm_for_items is True, otherwise returns empty list.
        
        Args:
            text: Raw receipt text
            
        Returns:
            List of GroceryItem objects
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
            
            # Convert to GroceryItem objects
            grocery_items = []
            for item_data in items_data:
                try:
                    grocery_item = GroceryItem(
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
    
    def parse_receipt(self, pdf_path: Path) -> Dict[str, Any]:
        """
        Parse a receipt PDF and extract all relevant information.
        Returns a dictionary with merchant, amount, date, and items.
        """
        text = self.extract_text(pdf_path)
        
        merchant_type, merchant_name = self.detect_merchant(text)
        amount = self.extract_amount(text)
        date = self.extract_date(text)
        
        # Extract items (uses LLM if enabled)
        items = self.extract_items(text)
        
        # Build description from items if available
        if items:
            item_names = [item.name for item in items[:3]]
            items_desc = ', '.join(item_names)
            full_description = f"{merchant_name} ({items_desc})"
        else:
            items_desc = ""
            full_description = merchant_name

        # Log full description for debugging
        logger.debug(f"Full description: {full_description}")
        
        """
        TODO: Add support for order_id extraction
        walmart example: 600000081236542
        amazon example: 701-3765924-2833010

        we should not imply merchant_type
        """
        return {
            'order_id': None,
            'merchant_name': merchant_name,
            'summary': items_desc,
            'items': items,  # Now returns List[GroceryItem] instead of list of strings
            'amount': amount,
            'date': date,
            'raw_text': text[:500],  # First 500 chars for debugging
            'pdf_filename': pdf_path.name
        }

