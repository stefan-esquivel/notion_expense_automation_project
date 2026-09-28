"""Fit receipt names without losing their identifying date and amount."""
import re
from pathlib import Path


def fit_receipt_filename(filename: str) -> str:
    if len(filename) <= 100 and len(filename.encode("utf-8")) <= 255:
        return filename
    suffix = Path(filename).suffix[:20]
    match = re.fullmatch(r'(\d{4}-\d{2}-\d{2}_)(.*)(_\$-?\d+\.\d{2}(?:_\d+)?)(\.[^.]+)', filename)
    if match:
        prefix, middle, amount, suffix = match.groups()
        ending = amount + suffix
    else:
        prefix, middle, ending = '', filename[:-len(suffix)] if suffix else filename, suffix
    middle = middle[:max(0, 100 - len(prefix) - len(ending))]
    # Unicode names must also fit the filesystem's 255-byte component limit.
    byte_budget = max(0, 255 - len((prefix + ending).encode('utf-8')))
    middle = middle.encode('utf-8')[:byte_budget].decode('utf-8', errors='ignore')
    return prefix + middle + ending
