
from uuid import UUID
from typing import List
from pydantic import BaseModel, Field
from src.domain.models.grocery import GroceryItem


class Receipt(BaseModel):
    """Raw receipt data extracted from PDF.
    
    This model represents the initial extraction phase before any AI processing
    or normalization. Data may be messy and require cleaning/validation.
    """
    
    recipt_id: UUID = Field(
        description="Unique identifier for this receipt"
    )
    
    vendor: str = Field(
        description="Raw vendor/merchant name as extracted from PDF (may be messy, e.g., 'WALMART SUPERCENTER #1234')",
        min_length=1
    )
    
    date: str = Field(
        description="Raw date string from receipt (format may vary, e.g., '2026-03-15', 'Mar 15, 2026', '03/15/2026')"
    )
    
    items: List[GroceryItem] = Field(
        default_factory=list,
        description="List of individual items purchased (empty for non-itemized receipts)"
    )
    
    total: float = Field(
        description="Total amount paid on the receipt",
        gt=0,
        examples=[92.01, 49.60, 150.00]
    )
