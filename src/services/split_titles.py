"""Shared title generation for review previews and Notion submissions."""
import re
from datetime import datetime

# Module-level: templates have no client/instance dependency. Preserve legacy
# precedence; tuple keywords also preserve non-contiguous 'Amazon ... Order'.
_MERCHANT_TEMPLATES = {
    ('walmart',): "{person}'s Walmart Food Split{details}",
    ('amazon', 'order'): "{person}'s Amazon Order Split{details}",
    ('amazon',): "{person}'s Amazon Split{details}",
    ('electrical',): "{person}'s Electrical Bill Split ({month})",
    ('electric',): "{person}'s Electrical Bill Split ({month})",
    ('rent',): "{person}'s Rent Split ({month})",
    ('netflix',): "{person}'s Netflix Payment ({month})",
    ('youtube',): "{person}'s YT Premium Split ({month})",
    ('yt',): "{person}'s YT Premium Split ({month})",
    ('parking',): "{person}'s Parking Share ({month})",
    ('longo',): "{person}'s Longo's Groceries Share",
    ('tv',): "{person}'s TV Payment ({month})",
}


def generate_split_title(person_name: str, merchant_name: str,
                         description: str, date: datetime) -> str:
    month = date.strftime('%b')
    merchant_lower = merchant_name.lower()
    match = re.search(r'\(([^)]*)\)', description)
    details = f' ({match.group(1)})' if match and match.group(1) else ''
    for keywords, template in _MERCHANT_TEMPLATES.items():
        if all(keyword in merchant_lower for keyword in keywords):
            return template.format(person=person_name, month=month, details=details)
    return f"{person_name}'s {merchant_name} Split{details}"
