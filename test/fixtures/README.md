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

These PDFs are used to test:
- Date extraction (YYYY-MM-DD format)
- Merchant detection
- Amount parsing
- Item description extraction

## JSON Fixtures

Located in `json/`:

- `mock_notion_response.json` - Mock Notion API responses for testing
- `sample_receipt_data.json` - Sample structured receipt data

## Text Fixtures

Located in `text/`:

- `sample_receipt.txt` - Plain text receipt sample

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