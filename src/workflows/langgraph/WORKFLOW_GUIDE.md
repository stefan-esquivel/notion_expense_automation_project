# LangGraph Workflow Guide

## Understanding Workflow State vs Workflow Status

### Workflow State (TypedDict)
The **entire data container** that flows through your LangGraph nodes:
```python
state: ReceiptWorkflowState = {
    "status": WorkflowStatus.PENDING,  # ← Status field
    "source": Sources.LOCAL_FOLDER,
    "file_path": "receipts/input/walmart.pdf",
    "receipt": None,
    "enriched_receipt": None,
    # ... all other fields
}
```

### Workflow Status (Enum)
A **single field** within the state that tracks the current phase:
```python
state["status"] = WorkflowStatus.EXTRACTING
```

## LangGraph Node Example

Here's how to use the status enum in your LangGraph nodes:

```python
from langgraph.graph import StateGraph
from src.workflows.langgraph.state import ReceiptWorkflowState
from src.domain.enums import WorkflowStatus

# Define your graph
workflow = StateGraph(ReceiptWorkflowState)

# Node 1: Extract data from PDF
def extract_node(state: ReceiptWorkflowState) -> ReceiptWorkflowState:
    """Extract raw data from PDF."""
    # Update status
    state["status"] = WorkflowStatus.EXTRACTING
    
    # Do extraction work
    receipt = extract_receipt_from_pdf(state["file_path"])
    state["receipt"] = receipt
    
    return state

# Node 2: Enrich with AI
def enrich_node(state: ReceiptWorkflowState) -> ReceiptWorkflowState:
    """Enrich receipt with AI processing and summarization."""
    # Update status
    state["status"] = WorkflowStatus.ENRICHING
    
    # Do enrichment work (THIS IS WHERE SUMMARIZATION HAPPENS!)
    enriched = enrich_receipt_with_llm(state["receipt"])
    state["enriched_receipt"] = enriched
    
    return state

# Node 3: Validate
def validate_node(state: ReceiptWorkflowState) -> ReceiptWorkflowState:
    """Validate the enriched data."""
    state["status"] = WorkflowStatus.VALIDATING
    
    errors = validate_receipt(state["enriched_receipt"])
    state["validation_errors"] = errors
    state["requires_review"] = len(errors) > 0
    
    return state

# Node 4: Review (if needed)
def review_node(state: ReceiptWorkflowState) -> ReceiptWorkflowState:
    """Human review if validation failed."""
    state["status"] = WorkflowStatus.REVIEWING
    
    # Show UI for human review
    edits = get_human_edits(state["enriched_receipt"])
    state["human_edits"] = edits
    state["review_approved"] = True
    
    return state

# Node 5: Submit to Notion
def submit_node(state: ReceiptWorkflowState) -> ReceiptWorkflowState:
    """Submit to Notion API."""
    state["status"] = WorkflowStatus.SUBMITTING
    
    # Create expense summary
    expense = create_expense_summary(state["enriched_receipt"])
    state["expense_summary"] = expense
    
    # Submit to Notion
    expense_id = notion_client.create_expense_entry(expense)
    state["notion_expense_id"] = expense_id
    
    return state

# Node 6: Archive
def archive_node(state: ReceiptWorkflowState) -> ReceiptWorkflowState:
    """Move file to processed folder."""
    state["status"] = WorkflowStatus.ARCHIVING
    
    archive_path = move_to_processed(state["file_path"])
    state["archive_path"] = archive_path
    
    return state

# Node 7: Complete
def complete_node(state: ReceiptWorkflowState) -> ReceiptWorkflowState:
    """Mark as completed."""
    state["status"] = WorkflowStatus.COMPLETED
    return state

# Build the graph
workflow.add_node("extract", extract_node)
workflow.add_node("enrich", enrich_node)
workflow.add_node("validate", validate_node)
workflow.add_node("review", review_node)
workflow.add_node("submit", submit_node)
workflow.add_node("archive", archive_node)
workflow.add_node("complete", complete_node)

# Add edges
workflow.set_entry_point("extract")
workflow.add_edge("extract", "enrich")
workflow.add_edge("enrich", "validate")

# Conditional edge: review if needed
workflow.add_conditional_edges(
    "validate",
    lambda state: "review" if state["requires_review"] else "submit"
)

workflow.add_edge("review", "submit")
workflow.add_edge("submit", "archive")
workflow.add_edge("archive", "complete")
workflow.set_finish_point("complete")

# Compile
app = workflow.compile()
```

## Status Tracking Benefits

### 1. **Monitoring**
```python
print(f"Current status: {state['status'].value}")
# Output: "Current status: enriching"
```

### 2. **Error Handling**
```python
try:
    state = enrich_node(state)
except Exception as e:
    state["status"] = WorkflowStatus.FAILED
    state["failure_reason"] = str(e)
```

### 3. **Progress UI**
```python
status_messages = {
    WorkflowStatus.EXTRACTING: "📄 Reading PDF...",
    WorkflowStatus.ENRICHING: "🤖 AI processing...",
    WorkflowStatus.VALIDATING: "✓ Validating data...",
    WorkflowStatus.REVIEWING: "👤 Waiting for review...",
    WorkflowStatus.SUBMITTING: "☁️ Sending to Notion...",
    WorkflowStatus.COMPLETED: "✅ Done!"
}

print(status_messages[state["status"]])
```

### 4. **Conditional Logic**
```python
def should_skip_review(state: ReceiptWorkflowState) -> bool:
    """Skip review if confidence is high and no errors."""
    return (
        not state["requires_review"] and
        state["enriched_receipt"].confidence_score > 0.9
    )
```

## Key Takeaway

- **`ReceiptWorkflowState`** = The entire data container (TypedDict)
- **`WorkflowStatus`** = One field in that container (Enum)
- **`status` field** = Tracks which phase you're in

The status enum helps you:
1. Track progress through the workflow
2. Handle errors appropriately
3. Show meaningful UI messages
4. Make conditional routing decisions