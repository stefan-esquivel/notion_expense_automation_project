# Test Fixtures

This directory contains test fixtures organized by type for the expense automation project.

## Directory Structure

```
test/fixtures/
├── pdfs/           # PDF receipt files for testing PDF extraction
├── json/           # JSON mock data and sample responses
├── text/           # Text-based sample data
└── README.md       # This file
```

## PDF Fixtures

Located in `pdfs/`:

- `2026-03-04_Walmart_Order_Meatballs_$80.59.pdf` - Walmart receipt with date 2026-03-04
- `2026-03-07_Amazon_Order_Baking_Sheets_$49.60.pdf` - Amazon receipt with date 2026-03-07
- `techzone_future_date_red.pdf` - TechZone Electronics order dated 2030-06-15 (future date → RED flag)
- `maple_street_organics_augment.pdf` - Blank/unreadable PDF (no text → Unknown Merchant → YELLOW advisory)
- `walmart_order_details.pdf` - Walmart.ca online order from Sep 2026 (valid receipt, no flags)
- `2026-09-19_Longos_Groceries_English_Cucumbers_Dill_Weed_Grape_Tomatoes_$59.90.pdf` - PII-scrubbed
  Longo's receipt that contains a loyalty-rewards section with `Total spent $103.01`. Used as a
  regression fixture for issue #47 (loyalty total must not override the transaction total $59.90).
  Generated from `text/longos_loyalty_receipt.txt`.

These PDFs are used to test:
- Date extraction (YYYY-MM-DD format)
- Merchant detection
- Amount parsing
- Item description extraction
- Validation flag outcomes (RED future-date, YELLOW unknown-merchant)

## JSON Fixtures

Located in `json/`:

- `mock_notion_response.json` - Mock Notion API responses for testing
- `sample_receipt_data.json` - Sample structured receipt data

## Text Fixtures

Located in `text/`:

- `sample_receipt.txt` - Plain text receipt sample
- `longos_loyalty_receipt.txt` - PII-scrubbed source text for the Longo's loyalty receipt fixture.
  All personal information (name, e-mail, phone number, card digits, auth codes) has been replaced
  with generic placeholders. The PDF fixture above was generated directly from this file.

## Usage in Tests

Import fixtures using relative paths from test files:

```python
from pathlib import Path

# For unit tests
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
PDF_FIXTURES = FIXTURES_DIR / "pdfs"
JSON_FIXTURES = FIXTURES_DIR / "json"

# Example
walmart_pdf = PDF_FIXTURES / "2026-03-04_Walmart_Order_Meatballs_$80.59.pdf"