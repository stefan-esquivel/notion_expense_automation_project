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
│  ┌──────────────────┐   Relation   ┌──────────────────────┐    │
│  │  Expense Table   │◄─────────────┤  Split Details Table │    │
│  │                  │              │                      │    │
│  │ • Merchant       │              │ • Title              │    │
│  │ • Date           │              │ • Person (owes)      │    │
│  │ • Amount         │              │ • Share Amount       │    │
│  │ • Paid By        │              │ • Share Percent      │    │
│  │ • Receipt        │              └──────────┬───────────┘    │
│  └──────────────────┘                         │ Relation        │
│                                               ▼                  │
│                                  ┌──────────────────────┐       │
│                                  │   Balances Table     │       │
│                                  │  (single page/row)   │       │
│                                  │                      │       │
│                                  │ • Running totals     │       │
│                                  │ • Linked splits      │       │
│                                  └──────────────────────┘       │
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

## LangGraph Workflow Architecture

### Overview

The system now uses **LangGraph** for orchestrating the receipt processing workflow. LangGraph provides a state machine-based approach with clear node transitions, error handling, and human-in-the-loop capabilities.

### Workflow State Machine

```
┌─────────────────────────────────────────────────────────────────┐
│                    LANGGRAPH WORKFLOW                            │
│                                                                   │
│  START                                                            │
│    │                                                              │
│    ▼                                                              │
│  ┌──────────────┐                                                │
│  │ INGEST NODE  │  Validates input, extracts raw text from PDF  │
│  └──────┬───────┘                                                │
│         │                                                         │
│         ▼                                                         │
│  ┌──────────────┐                                                │
│  │ EXTRACT NODE │  Parses PDF data into structured Receipt      │
│  └──────┬───────┘                                                │
│         │                                                         │
│         ▼                                                         │
│  ┌──────────────┐                                                │
│  │ ENRICH NODE  │  Uses LLM to categorize and enhance data      │
│  └──────┬───────┘                                                │
│         │                                                         │
│         ▼                                                         │
│  ┌──────────────┐                                                │
│  │VALIDATE NODE │  Validates data quality and completeness      │
│  └──────┬───────┘                                                │
│         │                                                         │
│         ▼                                                         │
│  ┌──────────────┐                                                │
│  │ REVIEW NODE  │  Human-in-the-loop: review and approve        │
│  └──────┬───────┘                                                │
│         │                                                         │
│         ▼                                                         │
│  ┌──────────────┐                                                │
│  │ COMMIT NODE  │  Submits to Notion API and organizes file     │
│  └──────┬───────┘                                                │
│         │                                                         │
│         ▼                                                         │
│       END                                                         │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Workflow Nodes

#### 1. Ingest Node ([`ingest_node.py`](src/workflows/langgraph/nodes/ingest_node.py))
**Purpose**: Entry point that validates input and extracts raw text

**Responsibilities**:
- Validates [`WorkflowInput`](src/domain/models/workflow.py:11) (file path, source)
- Checks file existence
- Extracts raw text from PDF using [`PDFExtractor`](src/services/pdf_extractor.py)
- Updates state status to `INGESTING`

**Input**: [`ReceiptWorkflowState`](src/workflows/langgraph/state.py:11) with `workflow_input`
**Output**: State with `raw_text` populated
**Error Handling**: Sets status to `FAILED` with `failure_reason`

#### 2. Extract Node ([`extract_node.py`](src/workflows/langgraph/nodes/extract_node.py))
**Purpose**: Parses PDF data into structured format

**Responsibilities**:
- Uses [`PDFExtractor.parse_receipt()`](src/services/pdf_extractor.py) with LLM enabled
- Converts extracted data to [`Receipt`](src/domain/models/recipts.py:8) model
- Extracts merchant, date, amount, items
- Updates state status to `EXTRACTING`

**Input**: State with `workflow_input.file_path`
**Output**: State with [`receipt`](src/workflows/langgraph/state.py:29) populated
**Error Handling**: Catches extraction errors, sets `FAILED` status

#### 3. Enrich Node ([`enrich_node.py`](src/workflows/langgraph/nodes/enrich_node.py))
**Purpose**: Uses LLM to categorize and enhance receipt data

**Responsibilities**:
- Calls [`llm_enrich_receipt()`](src/llm/receipt_extractor.py) to categorize merchant
- Generates confidence scores
- Adds contextual notes
- Updates state status to `ENRICHING`

**Input**: State with `receipt`
**Output**: State with [`enriched_receipt`](src/workflows/langgraph/state.py:33) ([`EnrichedReceipt`](src/domain/models/enrichment.py))
**Error Handling**: Catches LLM errors, sets `FAILED` status

#### 4. Validate Node ([`validate_node.py`](src/workflows/langgraph/nodes/validate_node.py))
**Purpose**: Validates data quality and completeness

**Responsibilities**:
- Checks required fields (merchant, date, amount)
- Validates amount format (positive, reasonable)
- Validates date format (ISO, not future)
- Verifies total calculation vs items
- Calculates confidence score
- Updates state status to `VALIDATING`

**Input**: State with `receipt` and optionally `enriched_receipt`
**Output**: State with [`validation_result`](src/workflows/langgraph/state.py:36) ([`ValidationResult`](src/domain/models/workflow.py:124))
**Validation Result Contains**:
- `is_valid`: Boolean
- `errors`: List of critical issues
- `warnings`: List of non-critical issues
- `requires_review`: Always `True` (prototyping mode)
- `confidence_score`: 0.0-1.0

#### 5. Review Node ([`review_node.py`](src/workflows/langgraph/nodes/review_node.py))
**Purpose**: Human-in-the-loop for reviewing and correcting data

**Responsibilities**:
- Displays receipt data using [`ExpenseUI`](src/services/ui.py)
- Allows user to edit amount, merchant, date
- Prompts user to select who paid
- Confirms split details (50/50, custom, or no split)
- Generates split titles and receipt filename
- Creates [`ExpenseSummary`](src/domain/models/expense.py:7) for Notion
- Updates state status to `REVIEWING`

**Input**: State with `receipt` and `validation_result`
**Output**: State with [`review_data`](src/workflows/langgraph/state.py:39) and [`expense_summary`](src/workflows/langgraph/state.py:42)
**User Interactions**:
1. Review and edit extracted data
2. Select payer (you or partner)
3. Confirm split percentage
4. Preview final data
5. Confirm submission

**Error Handling**: 
- `KeyboardInterrupt` → User cancelled
- `ValueError` → Validation error
- Sets `FAILED` status with reason

#### 6. Commit Node ([`commit_node.py`](src/workflows/langgraph/nodes/commit_node.py))
**Purpose**: Submits data to Notion and organizes file

**Responsibilities**:
- Validates Notion configuration
- Creates expense entry via [`NotionExpenseClient.create_expense_entry()`](src/services/notion_api.py)
- Creates split entries via [`NotionExpenseClient.create_split_entry()`](src/services/notion_api.py)
- Organizes file using [`FileOrganizer.organize_file()`](src/services/file_organizer.py)
- Updates state status to `SUBMITTING` then `COMPLETED`

**Input**: State with `expense_summary`
**Output**: State with [`results`](src/workflows/langgraph/state.py:45) ([`WorkflowResults`](src/domain/models/workflow.py:88))
**Results Contains**:
- `notion_expense_id`: Created expense page ID
- `notion_split_ids`: List of created split page IDs
- `archive_path`: Where file was moved
- `timestamp`: When workflow completed

**Error Handling**: Catches Notion API errors, sets `FAILED` status

### Workflow State ([`state.py`](src/workflows/langgraph/state.py))

The [`ReceiptWorkflowState`](src/workflows/langgraph/state.py:11) TypedDict tracks data through the workflow:

```python
class ReceiptWorkflowState(TypedDict):
    # Status tracking
    status: WorkflowStatus  # PENDING, INGESTING, EXTRACTING, etc.
    
    # Input
    workflow_input: Optional[WorkflowInput]  # Source and file path
    
    # Extraction phase
    receipt: Optional[Receipt]  # Raw extracted data
    
    # Enrichment phase
    enriched_receipt: Optional[EnrichedReceipt]  # AI-enhanced data
    
    # Validation phase
    validation_result: Optional[ValidationResult]  # Quality checks
    
    # Review phase
    review_data: Optional[ReviewData]  # User corrections
    
    # Output phase
    expense_summary: Optional[ExpenseSummary]  # Notion-ready data
    
    # Results
    results: Optional[WorkflowResults]  # Final outcomes
    failure_reason: Optional[str]  # Error message if failed
```

### Data Models

#### Input Models
- [`WorkflowInput`](src/domain/models/workflow.py:11): Initial input (source, file_path, raw_text)
- [`Sources`](src/domain/enums.py): Enum for input sources (LOCAL_FOLDER, GMAIL)

#### Processing Models
- [`Receipt`](src/domain/models/recipts.py:8): Raw extracted data (vendor, date, items, total)
- [`ReceiptItem`](src/domain/models/grocery.py:5): Individual line item (name, price, category)
- [`EnrichedReceipt`](src/domain/models/enrichment.py): AI-enhanced data (category, confidence, notes)

#### Validation Models
- [`ValidationResult`](src/domain/models/workflow.py:124): Validation outcome (is_valid, errors, warnings, confidence_score)

#### Review Models
- [`ReviewData`](src/domain/models/workflow.py:37): User corrections (paid_by, overrides, approval)

#### Output Models
- [`ExpenseSummary`](src/domain/models/expense.py:7): Final Notion-ready data
- [`SplitDetail`](src/domain/models/expense.py:53): Split information (person, share_percent, title)
- [`WorkflowResults`](src/domain/models/workflow.py:88): Final outcomes (Notion IDs, archive path)

### Status Flow

The [`WorkflowStatus`](src/domain/enums.py) enum tracks workflow progress:

```
PENDING → INGESTING → EXTRACTING → ENRICHING → VALIDATING → 
REVIEWING → SUBMITTING → COMPLETED
                                                    ↓
                                                 FAILED
```

### Error Handling Strategy

1. **Node-Level**: Each node catches exceptions and sets `FAILED` status
2. **State Preservation**: Failed state includes `failure_reason` for debugging
3. **Graceful Degradation**: Validation warnings don't block workflow
4. **User Control**: Review node allows user to cancel or fix issues

### Testing

Comprehensive unit tests with **88% coverage**:
- [`test_ingest_node.py`](test/unit/test_ingest_node.py): 8 tests
- [`test_extract_node.py`](test/unit/test_extract_node.py): 13 tests  
- [`test_validate_node.py`](test/unit/test_validate_node.py): 24 tests
- [`test_enrich_node.py`](test/unit/test_enrich_node.py): 15 tests
- [`test_review_node.py`](test/unit/test_review_node.py): 25 tests
- [`test_commit_node.py`](test/unit/test_commit_node.py): 14 tests

See [`TEST_COVERAGE_NODES.md`](test/unit/TEST_COVERAGE_NODES.md) for detailed coverage report.

### Benefits of LangGraph Architecture

1. **Clear Separation of Concerns**: Each node has a single responsibility
2. **Testability**: Nodes are pure functions that can be tested in isolation
3. **State Management**: Centralized state makes data flow explicit
4. **Error Recovery**: Failed workflows can be inspected and potentially resumed
5. **Extensibility**: New nodes can be added without modifying existing ones
6. **Human-in-the-Loop**: Review node provides natural checkpoint for user input
7. **Observability**: Status tracking provides clear visibility into workflow progress


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
- Database IDs (`EXPENSE_TABLE_DATABASE_ID`, `SPLIT_DETAILS_DATABASE_ID`, `BALANCES_DATABASE_ID`)
- Balances page ID (`BALANCES_PAGE_ID`) — the single row in the Balances table
- User name aliases (`YOUR_NAME`, `PARTNER_NAME`) — must match Notion field values exactly
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

### 4. Notion Client (`src/notion_api.py`)
**Purpose**: Interface with Notion API

**Responsibilities**:
- Create expense table entries
- Create split details entries
- Link pages via relations using the generic `_link_pages(source, target, property_name)` method
- Link split entries to their parent expense entry (`"Split Details Table"` relation)
- Link split entries to the single Balances page (`"Split Details Table"` relation on the balance page)
- Generate split titles following naming patterns
- Test API connection
- Handle API errors

**Key Design — `_link_pages()`**:
- Generic method: takes `source_page_id`, `target_page_id`, and `table_name` (the relation property name)
- Fetches existing relations first to avoid overwriting them (append-safe)
- Deduplicates before updating
- Used for both expense→split and balance→split links

**Split Title Patterns** (uses name aliases from `YOUR_NAME` / `PARTNER_NAME`):
- Food: `"[Alias]'s Walmart Food Split (Item)"`
- Bills: `"[Alias]'s Electrical Bill Split (Month)"`
- Subscriptions: `"[Alias]'s Netflix Payment (Month)"`

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

### Scenario: YOU pay $100 at Walmart

**Input**:
- Amount: $100.00
- Paid By: `YOU` (your alias from `YOUR_NAME`)

**Processing**:
- Calculate split: $100.00 × 50% = $50.00
- Non-payer: `PARTNER` (your alias from `PARTNER_NAME`)

**Output**:
1. **Expense Entry**:
   - Merchant: "Walmart Order"
   - Amount: CA$100.00
   - Paid By: `YOU`
   - Linked to: Split entry (via `"Split Details Table"` relation)

2. **Split Entry** (ONE entry only):
   - Title: "`PARTNER`'s Walmart Food Split"
   - Person: `PARTNER`
   - Share Amount: CA$50.00
   - Meaning: `PARTNER` owes `YOU` $50.00
   - Linked to: Expense entry AND Balances page

3. **Balances Page** (single row, updated):
   - New split entry appended to `"Split Details Table"` relation

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