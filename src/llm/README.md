# LLM Tools Organization

This directory contains all LLM-related functionality for receipt processing.

## Structure

```
src/llm/
├── __init__.py              # Package initialization
├── prompts.py               # All prompt templates (SINGLE SOURCE OF TRUTH)
├── client.py                # OpenAI API wrapper (low-level)
├── receipt_extractor.py     # High-level extraction functions
└── README.md                # This file
```

## Files Overview

### `prompts.py` - Prompt Templates
**Purpose**: Store all LLM prompts in one place for easy maintenance and versioning.

Contains:
- `EXTRACT_RECEIPT_SYSTEM/USER` - Full extraction from raw text
- `VALIDATE_RECEIPT_SYSTEM/USER` - Validate/correct existing extraction
- `ENRICH_RECEIPT_SYSTEM/USER` - Categorize and add metadata
- `PARSE_DATE_SYSTEM/USER` - Parse ambiguous date formats

**Why separate file?**
- Easy to update prompts without touching code
- Version control for prompt changes
- Can A/B test different prompts
- Clear separation of concerns

### `client.py` - OpenAI Client Wrapper
**Purpose**: Low-level API calls to OpenAI with error handling.

Key class: `ReceiptLLMClient`

Methods:
- `extract_receipt(raw_text)` - Extract structured data
- `validate_receipt(raw_text, merchant, date, amount)` - Validate data
- `enrich_receipt(merchant, date, amount, items)` - Add metadata
- `parse_date(date_text, context)` - Parse dates

**Features**:
- JSON mode for structured output
- Configurable model (default: gpt-4o-mini)
- Temperature control
- Error handling

### `receipt_extractor.py` - High-Level Functions
**Purpose**: Business logic functions that use the client and return domain models.

Functions:
- `llm_extract_receipt(raw_text)` → `Receipt`
- `llm_validate_receipt(receipt, raw_text)` → `Receipt`
- `llm_enrich_receipt(receipt)` → `EnrichedReceipt`
- `llm_parse_date(date_text, context)` → `datetime`

**Why separate from client?**
- Client is generic (returns dicts)
- Extractor converts to domain models (Receipt, EnrichedReceipt)
- Easier to test and mock
- Clear API for workflow nodes

## Usage in Workflow Nodes

### Example: Extract Node with Hybrid Approach

```python
from src.llm.receipt_extractor import llm_extract_receipt, llm_validate_receipt
from src.pdf_extractor import PDFExtractor

def extract_node(state: ReceiptWorkflowState) -> ReceiptWorkflowState:
    """Extract with hybrid approach."""
    
    # Step 1: Rule-based extraction
    extractor = PDFExtractor()
    raw_text = extractor.extract_text(file_path)
    
    # Try rule-based first
    receipt = extractor.parse_receipt(file_path)
    confidence = calculate_confidence(receipt)
    
    # Step 2: Use LLM if needed
    if confidence < 0.6:
        # Low confidence - full LLM extraction
        receipt = llm_extract_receipt(raw_text)
    elif confidence < 0.85:
        # Medium confidence - LLM validation
        receipt = llm_validate_receipt(receipt, raw_text)
    
    state["receipt"] = receipt
    return state
```

### Example: Enrich Node

```python
from src.llm.receipt_extractor import llm_enrich_receipt

def enrich_node(state: ReceiptWorkflowState) -> ReceiptWorkflowState:
    """Enrich with LLM categorization."""
    
    receipt = state["receipt"]
    
    # Use LLM to categorize and add metadata
    enriched = llm_enrich_receipt(receipt)
    
    state["enriched_receipt"] = enriched
    return state
```

## Configuration

Set your OpenAI API key:

```bash
export OPENAI_API_KEY="sk-..."
```

Or in `.env`:
```
OPENAI_API_KEY=sk-...
```

## Cost Optimization

**Model**: `gpt-4o-mini` (default)
- ~$0.15 per 1M input tokens
- ~$0.60 per 1M output tokens
- Typical receipt: ~500 tokens input, ~100 tokens output
- **Cost per receipt: ~$0.0001** (very cheap!)

**Strategies**:
1. Use rule-based extraction first (free)
2. Only call LLM for low-confidence cases (~20-30% of receipts)
3. Cache common merchants/patterns
4. Batch process if possible

## Testing

```python
# Test extraction
from src.llm.receipt_extractor import llm_extract_receipt

raw_text = "WALMART\nTotal: $92.01\nDate: 2026-03-15"
receipt = llm_extract_receipt(raw_text)
print(receipt.vendor, receipt.total, receipt.date)
```

## Prompt Engineering Tips

When updating prompts in `prompts.py`:

1. **Be specific**: "Return JSON with these exact fields..."
2. **Give examples**: Show the desired output format
3. **Handle edge cases**: "If date is ambiguous, use MM/DD/YYYY..."
4. **Use JSON mode**: Set `response_format={"type": "json_object"}`
5. **Test iteratively**: Try prompts on real receipts and refine

## Future Enhancements

- [ ] Add prompt versioning (v1, v2, etc.)
- [ ] Add caching for common merchants
- [ ] Add batch processing support
- [ ] Add cost tracking/logging
- [ ] Add fallback to cheaper models
- [ ] Add prompt A/B testing framework