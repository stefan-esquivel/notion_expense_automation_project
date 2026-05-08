
from uuid import UUID
from typing import List, Optional
from pydantic import BaseModel, Field
from domain.models.grocery import ReceiptItem


class Receipt(BaseModel):
    """Raw receipt data extracted from PDF.
    
    This model represents the initial extraction phase before any AI processing
    or normalization. Data may be messy and require cleaning/validation.
    """
    '''
    may convert to uuid
    '''
    recipt_id: Optional[str] = Field(
        default=None,
        description="Unique identifier for this receipt (order ID from merchant, or None if not available)"
    )

    summary: Optional[str] = Field(
        default=None,
        description="Optional description of items purchased (eg. (tomatoes, bananas, etc.))"
    )
    
    vendor: str = Field(
        description="Raw vendor/merchant name as extracted from PDF (may be messy, e.g., 'WALMART SUPERCENTER #1234')",
        min_length=1
    )
    
    date: str = Field(
        description="Raw date string from receipt (format may vary, e.g., '2026-03-15', 'Mar 15, 2026', '03/15/2026')"
    )
    
    items: List[ReceiptItem] = Field(
        default_factory=list,
        description="List of individual items purchased (empty for non-itemized receipts)"
    )
    
    total: float = Field(
        description="Total amount paid on the receipt",
        gt=0,
        examples=[92.01, 49.60, 150.00]
    )
