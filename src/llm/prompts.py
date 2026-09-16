"""Prompt templates for LLM-based receipt extraction and validation."""

# ============================================================================
# EXTRACTION PROMPTS
# ============================================================================

EXTRACT_RECEIPT_SYSTEM = """You are a receipt data extraction expert. 
Extract structured information from receipt text with high accuracy.
Always return valid JSON matching the specified schema."""

EXTRACT_RECEIPT_USER = """Extract the following information from this receipt:

Receipt Text:
{raw_text}

Extract and return JSON with these fields:
- merchant_name: The store/vendor name (string)
- date: Transaction date in ISO format YYYY-MM-DD (string)
- total_amount: Total amount paid (number)
- currency: Currency code like "USD" or "CAD" (string, default "CAD")
- items: List of purchased items with name and price (array, can be empty)

Important:
- For dates, prefer YYYY-MM-DD format
- If you see multiple dates, choose the transaction/purchase date
- For amounts, use the final total (after tax)
- If information is unclear, use your best judgment
- Return valid JSON only, no markdown or explanation

Example output:
{{
  "merchant_name": "Walmart",
  "date": "2026-03-15",
  "total_amount": 92.01,
  "currency": "CAD",
  "items": []
}}"""

# ============================================================================
# VALIDATION PROMPTS
# ============================================================================

VALIDATE_RECEIPT_SYSTEM = """You are a data validation expert.
Review extracted receipt data and correct any errors.
Focus on fixing date formats, merchant names, and amounts."""

VALIDATE_RECEIPT_USER = """Review and correct this extracted receipt data:

Original Receipt Text:
{raw_text}

Extracted Data:
- Merchant: {merchant}
- Date: {date}
- Amount: ${amount}

Tasks:
1. Verify the merchant name is correct and properly formatted
2. Ensure the date is in YYYY-MM-DD format and matches the receipt
3. Confirm the amount matches the total on the receipt
4. Fix any errors you find

Return JSON with corrected data:
{{
  "merchant_name": "corrected merchant name",
  "date": "YYYY-MM-DD",
  "total_amount": 0.00,
  "corrections_made": ["list of what you fixed"],
  "confidence": 0.95
}}

If everything is correct, return the same data with empty corrections_made list."""

# ============================================================================
# ENRICHMENT PROMPTS
# ============================================================================

ENRICH_RECEIPT_SYSTEM = """You are a receipt categorization expert.
Analyze receipts and categorize them for expense tracking based on merchant and items purchased."""

ENRICH_RECEIPT_USER = """Analyze this receipt and provide categorization:

Receipt:
- Merchant: {merchant}
- Date: {date}
- Items: {items}

Provide:
1. Category (grocery, utility, subscription, retail, restaurant, transportation, entertainment, healthcare, other)
2. Confidence in categorization (0.0 to 1.0)

Use the items purchased to help determine the correct category. For example:
- Food items → grocery
- Electronics → retail
- Streaming services → subscription

Return JSON:
{{
  "category": "grocery",
  "confidence": 0.95,
  "notes": "Any additional observations"
}}"""

# ============================================================================
# DATE PARSING PROMPTS (Specialized)
# ============================================================================

PARSE_DATE_SYSTEM = """You are a date parsing expert.
Convert various date formats to ISO 8601 (YYYY-MM-DD) format."""

PARSE_DATE_USER = """Parse this date from a receipt:

Date text: "{date_text}"

Context (receipt excerpt):
{context}

Return JSON:
{{
  "parsed_date": "YYYY-MM-DD",
  "confidence": 0.95,
  "original_format": "format you detected"
}}

Handle formats like:
- Mar 15, 2026
- 03/15/2026
- 2026-03-15
- March 15th, 2026
- 15-Mar-2026

If ambiguous (like 03/04/2026), use context clues or default to MM/DD/YYYY for North American receipts."""

# ============================================================================
# ITEM EXTRACTION PROMPTS
# ============================================================================

EXTRACT_ITEMS_SYSTEM = """You are a receipt item extraction expert.
Extract individual line items from receipt text with their names, prices, and categories.
Return structured JSON data for each item found."""

EXTRACT_ITEMS_USER = """Extract all individual items from this receipt text:

Receipt Text:
{raw_text}

For each item found, extract:
- name: Product name a simplified version NO BRANDS JUST WHAT IT IS (string)
- price: Individual item price (number)
- category: Product category - one of: produce, dairy, meat, seafood, bakery, pantry, household, personal_care, beverages, frozen, deli, other (string)

Return JSON with an "items" array:
{{
  "items": [
    {{
      "name": "Organic Bananas",
      "price": 3.99,
      "category": "produce"
    }},
    {{
      "name": "Whole Milk 2%",
      "price": 4.29,
      "category": "dairy"
    }}
  ]
}}

Important:
- Only extract actual product line items, not subtotals, taxes, or totals
- Only extract what that item is no brands or long names
- If price is not clear for an item, estimate based on context or omit the item
- Use your best judgment for categorization
- Return empty array if no items can be extracted
- Return valid JSON only, no markdown or explanation"""