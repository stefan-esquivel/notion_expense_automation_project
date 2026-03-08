"""PDF text extraction and parsing module."""
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import pdfplumber
from dateutil import parser as date_parser


class PDFExtractor:
    """Extract and parse information from receipt PDFs."""
    
    def __init__(self):
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
        """Extract the total amount from receipt text."""
        # Look for common patterns: $XX.XX, CA$XX.XX, Total: $XX.XX
        patterns = [
            r'(?:total|amount|grand total)[\s:]*(?:CA)?\$?\s*(\d+[,\d]*\.?\d{2})',
            r'(?:CA)?\$\s*(\d+[,\d]*\.\d{2})',
            r'(\d+[,\d]*\.\d{2})\s*(?:CAD|CA\$)',
        ]
        
        amounts = []
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                amount_str = match.group(1).replace(',', '')
                try:
                    amounts.append(float(amount_str))
                except ValueError:
                    continue
        
        # Return the largest amount found (likely the total)
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
    
    def extract_items_description(self, text: str, merchant_type: str) -> str:
        """Extract a description of items purchased based on merchant type."""
        text_lower = text.lower()
        
        # Common food items
        food_keywords = [
            'chicken', 'shrimp', 'salmon', 'beef', 'pork',
            'teriyaki', 'mediterranean', 'chipotle', 'greek',
            'soup', 'stir fry', 'krupnik', 'basics',
            'eggs', 'onion', 'fiber', 'hummus', 'tomato'
        ]
        
        # Amazon items
        amazon_keywords = [
            'scale', 'tray', 'bulbs', 'soda', 'club soda'
        ]
        
        found_items = []
        
        if merchant_type == 'walmart':
            for keyword in food_keywords:
                if keyword in text_lower:
                    found_items.append(keyword.title())
        elif merchant_type == 'amazon':
            for keyword in amazon_keywords:
                if keyword in text_lower:
                    found_items.append(keyword.title())
        
        if found_items:
            return ' '.join(found_items[:3])  # Limit to 3 items
        
        return ''
    
    def parse_receipt(self, pdf_path: Path) -> Dict[str, Any]:
        """
        Parse a receipt PDF and extract all relevant information.
        Returns a dictionary with merchant, amount, date, and description.
        """
        text = self.extract_text(pdf_path)
        
        merchant_type, merchant_name = self.detect_merchant(text)
        amount = self.extract_amount(text)
        date = self.extract_date(text)
        items_desc = self.extract_items_description(text, merchant_type)
        
        # Build full description
        if items_desc:
            full_description = f"{merchant_name} ({items_desc})"
        else:
            full_description = merchant_name
        
        return {
            'merchant_type': merchant_type,
            'merchant_name': merchant_name,
            'description': full_description,
            'amount': amount,
            'date': date,
            'raw_text': text[:500],  # First 500 chars for debugging
            'pdf_filename': pdf_path.name
        }

