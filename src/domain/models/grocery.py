from pydantic import BaseModel, Field
from typing import Optional


class ReceiptItem(BaseModel):
    """Individual item from a receipt.
    
    Represents a single line item from a receipt, including
    the product name, price, and optional category classification.
    
    Design Note: This model intentionally does not include a quantity field.
    Each item on a receipt is treated as a separate line item with its own price,
    even if multiple units of the same product were purchased. This reflects how
    most receipts display items and simplifies price calculations.
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


# Backwards compatibility alias
GroceryItem = ReceiptItem
