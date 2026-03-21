from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from pathlib import Path


class ExpenseSummary(BaseModel):
    """Final expense data ready for Notion submission.
    
    This model represents the complete, validated expense information
    that will be sent to the Notion API. All data should be clean,
    normalized, and ready for database insertion.
    """
    
    merchant_description: str = Field(
        description="Clean, human-readable merchant name and description (e.g., 'Walmart Order', 'Netflix Subscription')",
        min_length=1,
        examples=["Walmart Order", "Amazon Order - Baking Sheets", "Netflix Payment"]
    )
    
    date: datetime = Field(
        description="Parsed date of the expense transaction"
    )
    
    amount: float = Field(
        description="Total expense amount in dollars (CAD)",
        gt=0,
        examples=[92.01, 49.60, 15.99]
    )
    
    paid_by: str = Field(
        description="Name of the person who paid for this expense (must match YOUR_NAME or PARTNER_NAME from config)",
        min_length=1,
        examples=["Jon Doe", "Jane Doe"]
    )
    
    receipt_file_path: Optional[Path] = Field(
        default=None,
        description="Full path to the receipt PDF file on disk"
    )
    
    receipt_filename: Optional[str] = Field(
        default=None,
        description="Organized filename for the receipt (e.g., '2026-03-15_Walmart_Order_$92.01.pdf')"
    )
    
    splits: Optional[List['SplitDetail']] = Field(
        default=None,
        description="List of split details if expense is shared between people"
    )


class SplitDetail(BaseModel):
    """Split detail for expense sharing.
    
    Represents one person's share of a split expense. Used to create
    entries in the Split Details table in Notion.
    """
    
    person: str = Field(
        description="Name of the person who owes their share (must match YOUR_NAME or PARTNER_NAME)",
        min_length=1,
        examples=["Jon Doe", "Jane Doe"]
    )
    
    share_percent: float = Field(
        description="Percentage of the total expense this person owes (0-100)",
        ge=0,
        le=100,
        examples=[50.0, 60.0, 33.33]
    )
    
    title: str = Field(
        description="Generated split title for Notion (e.g., 'Jane's Walmart Food Split (Shrimp)')",
        min_length=1,
        examples=[
            "Jane's Walmart Food Split (Shrimp)",
            "Jon's Netflix Payment (Feb)",
            "Jane's Rent Split (Mar)"
        ]
    )
