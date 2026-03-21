from typing import TypedDict, Optional
from datetime import datetime

from src.domain.enums import WorkflowStatus
from src.domain.models.recipts import Receipt
from src.domain.models.enrichment import EnrichedReceipt
from src.domain.models.expense import ExpenseSummary
from src.domain.models.workflow import WorkflowInput, ReviewData, WorkflowResults, ValidationResult


class ReceiptWorkflowState(TypedDict):
    """LangGraph state for receipt processing workflow.
    
    Data flows through three main phases:
    1. Extraction: Raw data from PDF → Receipt
    2. Enrichment: AI processing → EnrichedReceipt (includes summarization)
    3. Output: Notion-ready data → ExpenseSummary
    
    All structured data uses Pydantic BaseModel for type safety and validation.
    """
    
    # ===== STATUS TRACKING =====
    status: WorkflowStatus  # Current phase of the workflow
    
    # ===== INPUT =====
    workflow_input: Optional[WorkflowInput]  # Structured input data (source, file_path, raw_text)
    
    # ===== EXTRACTION (Raw Data) =====
    receipt: Optional[Receipt]  # Raw extracted data from PDF
    
    # ===== ENRICHMENT (Processed Data) =====
    # This is where summarization happens!
    enriched_receipt: Optional[EnrichedReceipt]  # Normalized, categorized, summarized
    
    # ===== VALIDATION =====
    validation_result: Optional[ValidationResult]  # Structured validation results with errors, warnings, and confidence
    
    # ===== REVIEW =====
    review_data: Optional[ReviewData]  # Structured review data (paid_by, corrections, approval status, timestamp)
    
    # ===== OUTPUT (Notion-Ready) =====
    expense_summary: Optional[ExpenseSummary]  # Final data for Notion API
    
    # ===== RESULTS =====
    results: Optional[WorkflowResults]  # Structured results including Notion IDs, archive path, and timing
    failure_reason: Optional[str]  # Error message if workflow failed