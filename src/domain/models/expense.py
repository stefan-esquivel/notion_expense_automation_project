from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from pathlib import Path

class ExpenseSummary(BaseModel):
    """Final expense data ready for Notion submission"""
    merchant_description: str
    date: datetime
    amount: float
    paid_by: str
    receipt_file_path: Optional[Path] = None
    receipt_filename: Optional[str] = None
    
    # Optional: Split information if needed
    splits: Optional[List['SplitDetail']] = None

class SplitDetail(BaseModel):
    """Split detail for expense sharing"""
    person: str
    share_percent: float
    title: str  # Generated split title
