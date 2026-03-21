"""Workflow-specific models for LangGraph state management."""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from pathlib import Path

from src.domain.enums import Sources


class WorkflowInput(BaseModel):
    """Input data for starting a receipt processing workflow.
    
    This model captures the initial input that triggers the workflow,
    including the source of the receipt and the file location.
    """
    
    source: Sources = Field(
        description="Source of the receipt: 'local_folder' or 'gmail'"
    )
    
    file_path: str = Field(
        description="Full path to the receipt PDF file",
        min_length=1,
        examples=[
            "receipts/input/walmart.pdf",
            "/Users/user/Downloads/amazon_receipt.pdf"
        ]
    )
    
    raw_text: str = Field(
        description="Raw text extracted from the PDF file",
        min_length=1
    )


class ReviewData(BaseModel):
    """Complete review phase data including user edits and approval status.
    
    This model captures all data from the human review step, including
    corrections, who paid, and whether the user approved the submission.
    """
    
    paid_by: str = Field(
        description="Name of person who paid for this expense (must match YOUR_NAME or PARTNER_NAME from config)",
        min_length=1,
        examples=["Jon Doe", "Jane Doe"]
    )
    
    amount_override: Optional[float] = Field(
        default=None,
        description="Corrected amount if PDF extraction was incorrect",
        gt=0,
        examples=[92.01, 49.60]
    )
    
    merchant_override: Optional[str] = Field(
        default=None,
        description="Corrected merchant name if extraction was incorrect",
        min_length=1,
        examples=["Walmart", "Amazon", "Netflix"]
    )
    
    date_override: Optional[datetime] = Field(
        default=None,
        description="Corrected date if extraction was incorrect"
    )
    
    notes: Optional[str] = Field(
        default=None,
        description="Additional notes or context from the user"
    )
    
    approved: bool = Field(
        description="Whether the user approved the expense for submission to Notion"
    )
    
    reviewed_at: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp when the review was completed"
    )


# Backwards compatibility alias
HumanEdits = ReviewData


class WorkflowResults(BaseModel):
    """Final results after successful workflow completion.
    
    This model captures all outputs from a successful workflow execution,
    including Notion API responses and file system operations.
    """
    
    notion_expense_id: str = Field(
        description="Notion page ID for the created expense entry (32-character hex string)",
        min_length=32,
        max_length=32,
        examples=["27361377bcc3807b883be5176931dea4"]
    )
    
    notion_split_ids: List[str] = Field(
        default_factory=list,
        description="List of Notion page IDs for created split detail entries"
    )
    
    archive_path: Path = Field(
        description="Full path where the receipt PDF was archived after processing"
    )
    
    processing_time_seconds: Optional[float] = Field(
        default=None,
        description="Total time taken to process this receipt (in seconds)",
        ge=0,
        examples=[2.5, 5.3, 10.8]
    )
    
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp when the workflow completed"
    )


class ValidationResult(BaseModel):
    """Results from the validation phase.
    
    Captures validation errors and determines if human review is required.
    """
    
    is_valid: bool = Field(
        description="Whether the data passed all validation checks"
    )
    
    errors: List[str] = Field(
        default_factory=list,
        description="List of validation error messages",
        examples=[
            ["Missing merchant name", "Invalid date format"],
            ["Amount is zero or negative"],
            []
        ]
    )
    
    warnings: List[str] = Field(
        default_factory=list,
        description="Non-critical warnings that don't block processing",
        examples=[
            ["Low confidence in merchant detection"],
            ["Unusual amount for this merchant"],
            []
        ]
    )
    
    requires_review: bool = Field(
        description="Whether human review is required before proceeding"
    )
    
    confidence_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Overall confidence in the extracted and enriched data (0.0 to 1.0)"
    )