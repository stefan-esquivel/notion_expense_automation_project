# Domain Models - Data Flow Architecture

## Overview

This directory contains the domain models that represent data at different stages of the receipt processing workflow.

## Data Flow

```
┌─────────────┐
│   PDF File  │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│  PHASE 1: EXTRACTION (Raw Data)                         │
│  ────────────────────────────────────                   │
│  Goal: Extract exactly what's on the receipt            │
│  Model: Receipt                                         │
│  ────────────────────────────────────                   │
│  • recipt_id: UUID                                      │
│  • vendor: str (raw: "WALMART SUPERCENTER #1234")       │
│  • date: str (raw: "03/17/2026")                        │
│  • items: List[GroceryItem]                             │
│  • total: float                                         │
└──────┬──────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│  PHASE 2: ENRICHMENT (AI Processing) ⭐ SUMMARIZE HERE  │
│  ────────────────────────────────────────               │
│  Goal: Normalize, categorize, and summarize             │
│  Model: EnrichedReceipt                                 │
│  ────────────────────────────────────────               │
│  • normalized_merchant: "Walmart"                       │
│  • merchant_category: "grocery"                         │
│  • parsed_date: datetime(2026, 3, 17)                   │
│  • grocery_summary: "Shrimp, Vegetables, Dairy" ⭐      │
│  • recipe_candidate: "Stir Fry" ⭐                      │
│  • confidence_score: 0.95                               │
└──────┬──────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│  PHASE 3: OUTPUT (Notion-Ready)                         │
│  ────────────────────────────────────                   │
│  Goal: Format for Notion API submission                 │
│  Model: ExpenseSummary                                  │
│  ────────────────────────────────────                   │
│  • merchant_description: "Walmart"                      │
│  • date: datetime                                       │
│  • amount: 80.59                                        │
│  • paid_by: "You"                                       │
│  • receipt_file_path: Path                              │
│  • splits: List[SplitDetail]                            │
└──────┬──────────────────────────────────────────────────┘
       │
       ▼
┌─────────────┐
│ Notion API  │
└─────────────┘
```

## Model Descriptions

### 1. `Receipt` (recipts.py)
**Purpose**: Raw extracted data from PDF  
**When**: Immediately after PDF text extraction  
**Characteristics**:
- Deterministic (same PDF = same Receipt)
- No interpretation or processing
- Preserves original formatting

### 2. `EnrichedReceipt` (enrichment.py) ⭐
**Purpose**: AI-processed and normalized data  
**When**: After LLM processing  
**Characteristics**:
- **This is where summarization happens!**
- Merchant name normalization
- Date parsing
- Categorization
- Grocery item summarization
- Recipe suggestions

### 3. `ExpenseSummary` (expense.py)
**Purpose**: Final data ready for Notion submission  
**When**: After user review and approval  
**Characteristics**:
- Maps directly to Notion API parameters
- Includes split information
- Contains file paths for upload

## Why This Structure?

### ✅ Separation of Concerns
- **Extraction**: "What did the PDF say?"
- **Enrichment**: "What does it mean?"
- **Output**: "How do we store it?"

### ✅ Testability
Each phase can be tested independently:
```python
# Test extraction
receipt = extract_from_pdf(pdf_path)
assert receipt.vendor == "WALMART SUPERCENTER #1234"

# Test enrichment
enriched = enrich_receipt(receipt)
assert enriched.normalized_merchant == "Walmart"
assert enriched.grocery_summary is not None

# Test output formatting
summary = create_expense_summary(enriched, paid_by="You")
assert summary.merchant_description == "Walmart"
```

### ✅ Clear Data Flow
The workflow state clearly shows progression:
```python
state["receipt"]           # Raw data
state["enriched_receipt"]  # Processed data (with summaries!)
state["expense_summary"]   # Notion-ready data
```

## Key Decision: Summarization in Enrichment

**Why summarize during enrichment, not extraction?**

1. **Extraction should be deterministic**: Same input → same output
2. **Summarization requires intelligence**: LLM interpretation, context
3. **Enrichment is the AI phase**: Where we add value beyond raw data
4. **Separation of concerns**: Extract facts, enrich with insights

## Example Usage

```python
# Phase 1: Extract
receipt = extract_receipt_from_pdf("walmart.pdf")
# receipt.vendor = "WALMART SUPERCENTER #1234"
# receipt.items = [GroceryItem(name="Shrimp", price=15.99), ...]

# Phase 2: Enrich (SUMMARIZE HERE!)
enriched = enrich_receipt_with_llm(receipt)
# enriched.normalized_merchant = "Walmart"
# enriched.grocery_summary = "Shrimp, Vegetables, Dairy"  ⭐
# enriched.recipe_candidate = "Stir Fry"  ⭐

# Phase 3: Output
expense = create_expense_summary(
    enriched=enriched,
    paid_by="You",
    file_path=Path("walmart.pdf")
)
# Ready for Notion API!