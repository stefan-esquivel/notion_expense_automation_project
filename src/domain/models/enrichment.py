from pydantic import BaseModel, Field
from typing import Optional


class EnrichedReceipt(BaseModel):
    """Merchant category, confidence and notes from LLM or keyword enrichment."""

    merchant_category: str = Field(
        description="Category of merchant: 'grocery', 'utility', 'subscription', 'retail', etc."
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
