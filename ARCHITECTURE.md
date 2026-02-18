# System Architecture

## Overview

The Notion Expense Automation system is a Python-based application that automates the process of tracking expenses from PDF receipts to Notion database entries.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INTERACTION                          │
│                                                                   │
│  1. Place PDF receipts in receipts/input/                       │
│  2. Run: python src/main.py                                      │
│  3. Review and confirm extracted data                            │
│  4. Select who paid                                              │
│  5. Confirm split details                                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         MAIN APPLICATION                         │
│                         (src/main.py)                            │
│                                                                   │
│  • Orchestrates entire workflow                                  │
│  • Validates configuration                                       │
│  • Tests Notion connection                                       │
│  • Processes each receipt sequentially                           │
│  • Handles errors and logging                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────┴─────────────────────┐
        │                                             │
        ▼                                             ▼
┌──────────────────┐                      ┌──────────────────────┐
│  PDF EXTRACTOR   │                      │   USER INTERFACE     │
│ (pdf_extractor)  │                      │      (ui.py)         │
│                  │                      │                      │
│ • Extract text   │                      │ • Display info       │
│ • Detect merchant│                      │ • Edit prompts       │
│ • Parse amount   │                      │ • Payer selection    │
│ • Parse date     │                      │ • Split confirmation │
│ • Categorize     │                      │ • Final preview      │
└──────────────────┘                      └──────────────────────┘
        │                                             │
        └─────────────────────┬─────────────────────┘
                              ▼
                    ┌──────────────────┐
                    │  FILE ORGANIZER  │
                    │ (file_organizer) │
                    │                  │
                    │ • Generate name  │
                    │ • Create folders │
                    │ • Move files     │
                    │ • Month structure│
                    └──────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │  NOTION CLIENT   │
                    │ (notion_client)  │
                    │                  │
                    │ • Create expense │
                    │ • Create split   │
                    │ • Link entries   │
                    │ • Generate titles│
                    └──────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         NOTION API                               │
│                                                                   │
│  ┌──────────────────┐              ┌──────────────────────┐    │
│  │  Expense Table   │◄─────────────┤ Split Details Table  │    │
│  │                  │   Relation    │                      │    │
│  │ • Merchant       │               │ • Title              │    │
│  │ • Date           │               │ • Person (owes)      │    │
│  │ • Amount         │               │ • Share Amount       │    │
│  │ • Paid By        │               │ • Date               │    │
│  │ • Receipt        │               │ • Balances (link)    │    │
│  └──────────────────┘               └──────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FILE SYSTEM OUTPUT                          │
│                                                                   │
│  receipts/processed/                                             │
│  ├── 2026-01/                                                    │
│  │   ├── 2026-01-18_Walmart_Order_Shrimp_$97.08.pdf            │
│  │   ├── 2026-01-19_Amazon_Order_Scale_$32.53.pdf              │
│  │   └── 2026-01-25_Electrical_Bill_$131.36.pdf                │
│  └── 2026-02/                                                    │
│      ├── 2026-02-01_Walmart_Food_Order_Basics_$44.58.pdf       │
│      └── 2026-02-09_Parking_$300.00.pdf                         │
│                                                                   │
│  logs/                                                           │
│  └── expense_automation_20260214.log                            │
└─────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Configuration Module (`src/config.py`)
**Purpose**: Centralized configuration management

**Responsibilities**:
- Load environment variables from `.env`
- Validate required configuration
- Provide configuration constants to other modules
- Create necessary directories

**Key Configuration**:
- Notion API credentials
- Database IDs
- User names
- Folder paths
- Split percentage

### 2. PDF Extractor (`src/pdf_extractor.py`)
**Purpose**: Extract and parse information from PDF receipts

**Responsibilities**:
- Extract text from PDF files using pdfplumber
- Detect merchant type using regex patterns
- Parse monetary amounts
- Extract dates in various formats
- Identify item descriptions
- Generate descriptive names

**Supported Merchants**:
- Walmart (groceries, delivery)
- Amazon (online orders)
- Utilities (electrical, hydro)
- Rent, Netflix, YouTube, Parking, TV, Longo's

### 3. File Organizer (`src/file_organizer.py`)
**Purpose**: Organize and rename receipt files

**Responsibilities**:
- Generate descriptive filenames
- Create monthly folder structure
- Move files from input to processed
- Handle duplicate filenames
- Sanitize filenames for filesystem

**Naming Pattern**:
```
YYYY-MM-DD_Merchant_Description_$Amount.pdf
```

### 4. Notion Client (`src/notion_client.py`)
**Purpose**: Interface with Notion API

**Responsibilities**:
- Create expense table entries
- Create split details entries
- Link split entries to expense entries
- Generate split titles following naming patterns
- Test API connection
- Handle API errors

**Split Title Patterns**:
- Food: `"[Person]'s Walmart Food Split (Item)"`
- Bills: `"[Person]'s Electrical Bill Split (Month)"`
- Subscriptions: `"[Person]'s Netflix Payment (Month)"`

### 5. User Interface (`src/ui.py`)
**Purpose**: Handle all user interactions

**Responsibilities**:
- Display extracted information in tables
- Prompt for edits and confirmations
- Select who paid (you or partner)
- Confirm split amounts
- Show final preview before sending
- Display success/error messages
- Beautiful CLI using Rich library

**Interactive Features**:
- Editable fields (description, amount, date)
- Payer selection menu
- Split customization (50/50, custom, or no split)
- Final confirmation before Notion submission

### 6. Main Application (`src/main.py`)
**Purpose**: Orchestrate the entire workflow

**Workflow Steps**:
1. Validate configuration
2. Test Notion API connection
3. Scan input folder for PDFs
4. For each receipt:
   - Extract information
   - Review and edit
   - Select payer
   - Confirm split
   - Preview final data
   - Create Notion entries
   - Organize file
5. Display summary

## Data Flow

### Input
```
PDF Receipt → Text Extraction → Parsed Data
```

### Processing
```
Parsed Data → User Review → Confirmed Data → Notion Entries
```

### Output
```
1. Notion Expense Entry (with receipt filename)
2. Notion Split Entry (linked to expense)
3. Organized PDF file (in monthly folder)
4. Log entry (for audit trail)
```

## Split Logic

### Scenario: You pay $100 at Walmart

**Input**:
- Amount: $100.00
- Paid By: Stefan Esquivel

**Processing**:
- Calculate split: $100.00 × 50% = $50.00
- Non-payer: Lydu

**Output**:
1. **Expense Entry**:
   - Merchant: "Walmart Order"
   - Amount: CA$100.00
   - Paid By: Stefan Esquivel

2. **Split Entry** (ONE entry only):
   - Title: "Lydia's Walmart Food Split"
   - Person: Lydu
   - Share Amount: CA$50.00
   - Meaning: Lydu owes Stefan $50.00

## Error Handling

### Configuration Errors
- Missing `.env` file → Display setup instructions
- Invalid API token → Test connection fails
- Missing database IDs → Validation error

### Processing Errors
- PDF extraction fails → Log error, skip file
- Amount/date not found → Prompt user to enter manually
- Notion API error → Log error, don't move file

### Recovery
- All errors logged to `logs/` folder
- Failed receipts remain in input folder
- User can retry after fixing issues

## Security

### Sensitive Data
- `.env` file contains API tokens (gitignored)
- Never commit credentials to version control
- API token has limited scope (only connected databases)

### Data Privacy
- All processing happens locally
- Only sends data to Notion (your workspace)
- No third-party services involved

## Performance

### Scalability
- Processes receipts sequentially (one at a time)
- Suitable for personal use (dozens of receipts)
- Can process batch of receipts in one run

### Optimization
- PDF text extraction is fast (<1 second per file)
- Notion API calls are rate-limited by Notion
- Interactive prompts allow user to control pace

## Future Enhancements

Potential improvements:
1. OCR for image receipts (not just PDFs)
2. Email integration (auto-download attachments)
3. Machine learning for better categorization
4. Batch approval mode (review all, then submit)
5. Web interface instead of CLI
6. Mobile app integration
7. Receipt photo capture from phone

## Technology Stack

- **Language**: Python 3.8+
- **PDF Processing**: pdfplumber, PyPDF2
- **API Client**: notion-client
- **CLI Interface**: rich, inquirer
- **Date Parsing**: python-dateutil
- **Configuration**: python-dotenv
- **Logging**: Python logging module

## File Structure

```
notion_expense_automation_project/
├── src/                    # Source code
│   ├── __init__.py
│   ├── main.py            # Entry point
│   ├── config.py          # Configuration
│   ├── pdf_extractor.py   # PDF processing
│   ├── file_organizer.py  # File management
│   ├── notion_client.py   # Notion API
│   └── ui.py              # User interface
├── receipts/
│   ├── input/             # New receipts
│   └── processed/         # Organized receipts
├── logs/                  # Application logs
├── examples/              # Sample CSV exports
├── requirements.txt       # Dependencies
├── .env.example          # Config template
├── .env                  # Your config (gitignored)
├── .gitignore            # Git ignore rules
├── README.md             # User documentation
├── SETUP_GUIDE.md        # Setup instructions
├── ARCHITECTURE.md       # This file
└── run.sh                # Quick start script