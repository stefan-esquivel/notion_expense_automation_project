from pydantic import BaseModel

class GroceryItem(BaseModel):
    name: str
    price: float
    category: str | None = None
