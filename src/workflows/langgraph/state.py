from typing import TypedDict, Optional, List
from datetime import datetime

from src.domain.enums import Sources, WorkflowStatus, MerchantCategory
from src.domain.models.recipts import Receipt
from src.domain.models.enrichment import EnrichedReceipt
from src.domain.models.expense import ExpenseSummary


class ReceiptWorkflowState(TypedDict):
    """LangGraph state for receipt processing workflow.
    
    Data flows through three main phases:
    1. Extraction: Raw data from PDF → Receipt
    2. Enrichment: AI processing → EnrichedReceipt (includes summarization)
    3. Output: Notion-ready data → ExpenseSummary
    """
    
    # ===== STATUS TRACKING =====
    status: WorkflowStatus  # Current phase of the workflow
    
    # ===== INPUT =====
    source: Sources  # 'local_folder' | 'gmail'
    file_path: str
    raw_text: str
    
    # ===== EXTRACTION (Raw Data) =====
    receipt: Optional[Receipt]  # Raw extracted data from PDF
    
    # ===== ENRICHMENT (Processed Data) =====
    # This is where summarization happens!
    enriched_receipt: Optional[EnrichedReceipt]  # Normalized, categorized, summarized
    
    # ===== VALIDATION =====
    validation_errors: List[str]
    requires_review: bool
    
    # ===== REVIEW =====
    human_edits: Optional[dict]  # User corrections during review
    review_approved: bool
    
    # ===== OUTPUT (Notion-Ready) =====
    expense_summary: Optional[ExpenseSummary]  # Final data for Notion API
    
    # ===== RESULTS =====
    notion_expense_id: Optional[str]
    notion_split_ids: Optional[List[str]]
    archive_path: Optional[str]
    failure_reason: Optional[str]