from pydantic import BaseModel, Field
from typing import Optional


class GroceryItem(BaseModel):
    """Individual grocery item from a receipt.
    
    Represents a single line item from a grocery receipt, including
    the product name, price, and optional category classification.
    """
    
    name: str = Field(
        description="Product name as it appears on the receipt (e.g., 'ORGANIC BANANAS', 'MILK 2%')",
        min_length=1,
        examples=["Shrimp", "Organic Bananas", "Whole Milk 2%"]
    )
    
    price: float = Field(
        description="Price of this individual item in dollars",
        gt=0,
        examples=[5.99, 12.50, 3.29]
    )
    
    category: Optional[str] = Field(
        default=None,
        description="Product category for grouping (e.g., 'produce', 'dairy', 'meat', 'pantry')",
        examples=["produce", "dairy", "meat", "seafood", "bakery", "pantry"]
    )
