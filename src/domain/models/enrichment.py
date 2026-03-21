from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class EnrichedReceipt(BaseModel):
    """Enriched receipt data after AI processing and normalization.
    
    This model represents the receipt after:
    - Merchant name normalization
    - Date parsing
    - Categorization
    - Summarization (grocery items, recipe suggestions)
    """
    
    # Normalized merchant information
    normalized_merchant: str = Field(
        description="Standardized merchant name (e.g., 'Walmart' instead of 'WALMART SUPERCENTER #1234')"
    )
    merchant_category: str = Field(
        description="Category of merchant: 'grocery', 'utility', 'subscription', 'retail', etc."
    )
    
    # Parsed temporal data
    parsed_date: datetime = Field(
        description="Properly parsed datetime from receipt"
    )
    
    # AI-generated summaries (enrichment phase)
    grocery_summary: Optional[str] = Field(
        default=None,
        description="Human-readable summary of grocery items (e.g., 'Shrimp, Vegetables, Dairy')"
    )
    recipe_candidate: Optional[str] = Field(
        default=None,
        description="Suggested recipe based on items (e.g., 'Pasta Dinner', 'Stir Fry')"
    )
    
    # Confidence metrics
    confidence_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in the enrichment quality (0.0 to 1.0)"
    )
    
    # Optional metadata
    notes: Optional[str] = Field(
        default=None,
        description="Additional notes or context from enrichment"
    )