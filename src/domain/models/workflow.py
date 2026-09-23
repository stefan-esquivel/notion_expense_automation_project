"""Workflow-specific models for LangGraph state management."""

from pydantic import BaseModel, Field, computed_field
from typing import Optional, List, Dict, Set
from datetime import datetime
from pathlib import Path

from domain.enums import Sources, ValidationSeverity


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
        default="",
        description="Raw PDF text, populated during ingestion after the duplicate check"
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
        description="Notion page ID for the created expense entry (UUID format with or without hyphens)",
        min_length=32,
        max_length=36,
        examples=["27361377bcc3807b883be5176931dea4", "35961377-bcc3-8172-a93b-ef826e153c5a"]
    )
    
    notion_split_ids: List[str] = Field(
        default_factory=list,
        description="List of Notion page IDs for created split detail entries (UUID format)"
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
class ScanResults(BaseModel):
    """Results from the scan phase.

    Captures which required receipt fields are missing, used to decide
    whether the workflow needs to route through augment before enrichment.
    """

    has_missing_data: bool = Field(
        description="Whether any required field is missing from the receipt"
    )

    missing_fields: List[str] = Field(
        default_factory=list,
        description="Names of required Receipt fields that are missing or empty",
        examples=[["vendor", "date"], ["date"], []]
    )


class AugmentResults(BaseModel):
    """Results from the augment phase.

    Records which previously-missing receipt fields augment was able to
    auto-fill (and how), so the review step can show the user what to
    double-check, plus which required fields could not be filled.
    """

    filled_fields: Dict[str, str] = Field(
        default_factory=dict,
        description="Maps each auto-filled field name to the method used to fill it",
        examples=[{"date": "llm_extraction"}, {}]
    )

    still_missing: List[str] = Field(
        default_factory=list,
        description="Required fields augment could not fill; user must provide these during review",
        examples=[["date"], []]
    )


class ValidationIssue(BaseModel):
    """A single validation issue with a severity tier.

    severity:
        RED    – blocking; commit is gated until the user corrects the value.
        YELLOW – advisory; user must acknowledge before the loop exits.
    field:
        Optional name of the Receipt field this issue relates to (used by
        review_node to know which prompt to show the user).
    key:
        Stable identifier used to track per-issue acknowledgement across
        validate→review loop iterations (e.g. "high_amount", "old_date").
    """

    message: str = Field(description="Human-readable description of the issue")
    severity: ValidationSeverity = Field(description="RED (blocking) or YELLOW (advisory)")
    field: Optional[str] = Field(
        default=None,
        description="Receipt field this issue relates to, e.g. 'date', 'total'"
    )
    key: str = Field(description="Stable key for acknowledgement tracking")


class ValidationResult(BaseModel):
    """Results from the validation phase.

    issues holds every RED and YELLOW finding.  When issues is empty (or
    every YELLOW has been acknowledged and no RED remain) the receipt is
    GREEN and commit is unlocked.
    """

    issues: List[ValidationIssue] = Field(
        default_factory=list,
        description="All RED and YELLOW validation issues found"
    )

    confidence_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Overall confidence in the extracted and enriched data (0.0 to 1.0)"
    )

    # ------------------------------------------------------------------ #
    # Derived helpers                                                      #
    # ------------------------------------------------------------------ #

    @computed_field  # type: ignore[misc]
    @property
    def errors(self) -> List[str]:
        """RED issue messages (backwards-compat view)."""
        return [i.message for i in self.issues if i.severity == ValidationSeverity.RED]

    @computed_field  # type: ignore[misc]
    @property
    def warnings(self) -> List[str]:
        """YELLOW issue messages (backwards-compat view)."""
        return [i.message for i in self.issues if i.severity == ValidationSeverity.YELLOW]

    @computed_field  # type: ignore[misc]
    @property
    def is_valid(self) -> bool:
        """True when there are no RED issues."""
        return not any(i.severity == ValidationSeverity.RED for i in self.issues)

    @computed_field  # type: ignore[misc]
    @property
    def requires_review(self) -> bool:
        """True whenever there is at least one issue of any severity."""
        return len(self.issues) > 0

    def is_green(self, acknowledged: Set[str]) -> bool:
        """Return True when commit is safe to proceed.

        Commit is safe when every issue is either:
        - a YELLOW that the user has acknowledged, OR
        - a RED that the user has explicitly overridden (key is in *acknowledged*).
        """
        for issue in self.issues:
            if issue.key not in acknowledged:
                return False
        return True
