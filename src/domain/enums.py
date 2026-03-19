"""Domain enums for the expense automation system."""

from enum import Enum


class Sources(Enum):
    """Where the receipt came from."""
    LOCAL_FOLDER = "local_folder"
    GMAIL = "gmail"


class WorkflowStatus(Enum):
    """Current status/phase of the receipt processing workflow.
    
    This enum tracks which stage the workflow is currently in.
    Add this as a field in your ReceiptWorkflowState to track progress.
    
    Usage in state:
        state["status"] = WorkflowStatus.EXTRACTING
    """
    PENDING = "pending"          # Initial state, not started
    INGESTING = "ingesting"      # Ingest data from PDF
    EXTRACTING = "extracting"    # Extracting data from PDF
    ENRICHING = "enriching"      # AI processing and summarization
    VALIDATING = "validating"    # Checking data quality
    REVIEWING = "reviewing"      # Waiting for human review
    SUBMITTING = "submitting"    # Sending to Notion API
    ARCHIVING = "archiving"      # Moving file to processed folder
    COMPLETED = "completed"      # Successfully finished
    FAILED = "failed"            # Error occurred


class MerchantCategory(Enum):
    """Categories of merchants for expense classification."""
    GROCERY = "grocery"
    UTILITY = "utility"
    SUBSCRIPTION = "subscription"
    RETAIL = "retail"
    RESTAURANT = "restaurant"
    TRANSPORTATION = "transportation"
    ENTERTAINMENT = "entertainment"
    HEALTHCARE = "healthcare"
    OTHER = "other"