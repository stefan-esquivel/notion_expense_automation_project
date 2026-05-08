"""High-level receipt extraction functions using LLM client."""

from typing import Dict, Any, Optional
from datetime import datetime

from llm.client import ReceiptLLMClient
from domain.models.recipts import Receipt
from domain.models.enrichment import EnrichedReceipt
from logger import get_logger

logger = get_logger(__name__)


def llm_extract_receipt(raw_text: str, client: Optional[ReceiptLLMClient] = None) -> Receipt:
    """
    Extract receipt data using LLM (full extraction).
    
    Use this when rule-based extraction has low confidence.
    
    Args:
        raw_text: Raw text from PDF
        client: Optional LLM client (creates new one if not provided)
    
    Returns:
        Receipt object with extracted data
    """
    if client is None:
        client = ReceiptLLMClient()
    
    # Call LLM for extraction
    extracted = client.extract_receipt(raw_text)
    
    # Convert to Receipt model
    from uuid import uuid4
    
    receipt = Receipt(
        recipt_id=str(uuid4()),  # Convert UUID to string
        vendor=extracted.get("merchant_name", "Unknown"),
        date=extracted.get("date", ""),
        items=extracted.get("items", []),
        total=float(extracted.get("total_amount", 0.0))
    )
    
    return receipt


def llm_validate_receipt(
    receipt: Receipt,
    raw_text: str,
    client: Optional[ReceiptLLMClient] = None
) -> Receipt:
    """
    Validate and correct receipt data using LLM.
    
    Use this when rule-based extraction has medium confidence.
    
    Args:
        receipt: Receipt with rule-based extraction
        raw_text: Original receipt text
        client: Optional LLM client
    
    Returns:
        Corrected Receipt object
    """
    if client is None:
        client = ReceiptLLMClient()
    
    # Call LLM for validation
    validated = client.validate_receipt(
        raw_text=raw_text,
        merchant=receipt.vendor,
        date=receipt.date,
        amount=receipt.total
    )
    
    # Update receipt with corrections
    receipt.vendor = validated.get("merchant_name", receipt.vendor)
    receipt.date = validated.get("date", receipt.date)
    receipt.total = float(validated.get("total_amount", receipt.total))
    
    # Log corrections if any
    corrections = validated.get("corrections_made", [])
    if corrections:
        logger.info(f"LLM corrections: {', '.join(corrections)}")
    
    return receipt


def llm_enrich_receipt(
    receipt: Receipt,
    client: Optional[ReceiptLLMClient] = None
) -> EnrichedReceipt:
    """
    Enrich receipt with categorization using LLM.
    
    Args:
        receipt: Receipt to enrich
        client: Optional LLM client
    
    Returns:
        EnrichedReceipt with merchant category and confidence score
    """
    if client is None:
        client = ReceiptLLMClient()
    
    # Call LLM for enrichment (merchant, date, and items for better categorization)
    enriched_data = client.enrich_receipt(
        merchant=receipt.vendor,
        date=receipt.date,
        items=receipt.items
    )
    
    # Convert to EnrichedReceipt model (simplified - just category now)
    enriched = EnrichedReceipt(
        merchant_category=enriched_data.get("category", "other"),
        confidence_score=enriched_data.get("confidence", 0.8),
        notes=enriched_data.get("notes")
    )
    
    return enriched


def llm_parse_date(
    date_text: str,
    context: str = "",
    client: Optional[ReceiptLLMClient] = None
) -> Optional[datetime]:
    """
    Parse ambiguous date using LLM.
    
    Args:
        date_text: Date string to parse
        context: Surrounding text for context
        client: Optional LLM client
    
    Returns:
        Parsed datetime or None if parsing fails
    """
    if client is None:
        client = ReceiptLLMClient()
    
    try:
        result = client.parse_date(date_text, context)
        parsed_date_str = result.get("parsed_date")
        
        if parsed_date_str:
            return datetime.fromisoformat(parsed_date_str)
        
        return None
        
    except Exception as e:
        logger.warning(f"LLM date parsing failed: {e}")
        return None