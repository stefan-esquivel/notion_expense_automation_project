
from uuid import UUID
from typing import List
from pydantic import BaseModel
from src.domain.models.grocery import GroceryItem


class Receipt(BaseModel):
    recipt_id: UUID
    vendor: str
    date: str
    items: List[GroceryItem]
    total: float
