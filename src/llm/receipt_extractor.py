"""High-level receipt extraction functions using LLM client."""

import re
from typing import Optional
from datetime import datetime

from llm.client import ReceiptLLMClient
from domain.models.recipts import Receipt
from domain.models.enrichment import EnrichedReceipt
from logger import get_logger

logger = get_logger(__name__)


def llm_extract_receipt(raw_text: str, client: Optional[ReceiptLLMClient] = None) -> Receipt:
    """
    Extract receipt header data using LLM for augmentation.
    
    Use this to recover missing required fields. Items are extracted separately.
    
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
    
    total_val = extracted.get("total_amount")
    try:
        total = float(total_val) if total_val not in (None, "") else None
        if total is not None and total <= 0:
            total = None
    except (ValueError, TypeError):
        total = None

    receipt = Receipt(
        vendor=extracted.get("merchant_name", "Unknown"),
        transaction_type=extracted.get("transaction_type", "Purchase"),
        date=extracted.get("date", ""),
        total=total
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


# ---------------------------------------------------------------------------
# Keyword-based fallback (used when LLM is unavailable)
# ---------------------------------------------------------------------------

# Maps a regex pattern to a (merchant_category, transaction_type) tuple.
# Ordered most-specific → least-specific so the first match wins.
_KEYWORD_CATEGORY_MAP: list = [
    (r'amazon',                     "retail"),
    (r'walmart',                    "grocery"),
    (r'longo',                      "grocery"),
    (r'hydro|electric|electricity|power|utility', "utility"),
    (r'netflix',                    "subscription"),
    (r'youtube|yt\b',               "subscription"),
    (r'spotify',                    "subscription"),
    (r'parking',                    "transportation"),
    (r'rent\b',                     "other"),
    (r'restaurant|bistro|cafe|pizza|sushi|burger', "restaurant"),
    (r'pharmacy|shoppers|rexall',   "healthcare"),
]

# Confidence assigned when the fallback path is used
FALLBACK_CONFIDENCE = 0.5


def keyword_enrich_receipt(receipt: Receipt) -> EnrichedReceipt:
    """Enrich a receipt using keyword matching (no LLM required).

    Used as a fallback when the LLM call fails.  Always sets
    ``confidence_score`` to ``FALLBACK_CONFIDENCE`` (0.5) so downstream
    nodes know the categorisation is uncertain.

    Args:
        receipt: Receipt to categorise.

    Returns:
        EnrichedReceipt with keyword-matched category and confidence 0.5.
    """
    vendor_lower = receipt.vendor.lower()

    for pattern, category in _KEYWORD_CATEGORY_MAP:
        if re.search(pattern, vendor_lower):
            return EnrichedReceipt(
                merchant_category=category,
                confidence_score=FALLBACK_CONFIDENCE,
                notes="keyword-matching fallback (LLM unavailable)",
            )

    return EnrichedReceipt(
        merchant_category="other",
        confidence_score=FALLBACK_CONFIDENCE,
        notes="keyword-matching fallback — no pattern matched",
    )


def llm_suspicious_confidence_check(
    receipt: "Receipt",
    enriched: "Optional[EnrichedReceipt]",
    confidence_score: float,
    client: Optional[ReceiptLLMClient] = None,
) -> Optional["ValidationIssue"]:
    """Call the LLM to explain a low confidence score and return a YELLOW issue.

    Only fires when ``confidence_score`` is below the threshold AND the LLM
    identifies a specific reason not already covered by the named checkers.

    Args:
        receipt:          The extracted receipt.
        enriched:         The enriched receipt (may be None).
        confidence_score: The composite confidence score from validate_node.
        client:           Optional LLM client (creates one if not provided).

    Returns:
        A YELLOW ``ValidationIssue`` if the LLM found something suspicious,
        or ``None`` if nothing was flagged or the LLM call fails.
    """
    from domain.models.workflow import ValidationIssue
    from domain.enums import ValidationSeverity

    try:
        if client is None:
            client = ReceiptLLMClient()

        result = client.suspicious_confidence_check(
            merchant=receipt.vendor or "",
            date=receipt.date or "",
            amount=receipt.total,
            category=enriched.merchant_category if enriched else "unknown",
            items=receipt.items,
            notes=enriched.notes if enriched else None,
            confidence_score=confidence_score,
        )
    except Exception as exc:
        logger.warning(f"LLM suspicious-confidence check failed, skipping: {exc}")
        return None

    reasons = result.get("suspicious_reasons") or []
    summary = result.get("summary", "").strip()

    if not reasons or summary in ("", "No specific issues detected"):
        return None

    detail = "; ".join(reasons)
    message = f"Low confidence ({confidence_score:.0%}) — {summary} ({detail})"

    return ValidationIssue(
        message=message,
        severity=ValidationSeverity.YELLOW,
        field=None,
        key="suspicious_confidence",
    )


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
