"""Shared title generation for review previews and Notion submissions."""
from datetime import datetime


def generate_split_title(person_name: str, merchant_name: str,
                         description: str, date: datetime) -> str:
    """Use the reviewed expense title verbatim, followed by Split.

    Merchant and date remain in the signature for existing callers.
    """
    title = description.strip() or merchant_name.strip()
    return f"{person_name}'s {title} Split"
