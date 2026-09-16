#!/usr/bin/env python3
"""Heuristic PII scanner for tracked/staged PDFs.

Extracts text from every tracked PDF (plus anything currently staged) and
flags likely personal data: emails, phone numbers, street addresses, SSN/SIN
patterns, and full (Luhn-valid) credit card numbers. This is a heuristic
review aid, not a guarantee — it can both miss things (e.g. names, scanned
images with no text layer) and flag false positives (e.g. order numbers that
happen to pass Luhn). Findings should be reviewed by a human.

Reviewed findings can be accepted via ALLOWLIST_PATH, keyed by
"<path>:<sha256-of-file-content>" so any change to the file requires
re-review.
"""
import hashlib
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ALLOWLIST_PATH = REPO_ROOT / "scripts" / "pii_scan_allowlist.txt"

EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
PHONE_RE = re.compile(r"\b\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b")
SSN_SIN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b|\b\d{3}-\d{3}-\d{3}\b")
STREET_RE = re.compile(
    r"\b\d{1,5}[\w\s]{0,25}\b(street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|lane|ln|way|court|ct)\b",
    re.IGNORECASE,
)
CARD_CANDIDATE_RE = re.compile(r"(?:\d[ -]?){13,19}")


def luhn_valid(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def find_card_numbers(text: str):
    hits = []
    for m in CARD_CANDIDATE_RE.finditer(text):
        digits = re.sub(r"[ -]", "", m.group())
        if 13 <= len(digits) <= 19 and luhn_valid(digits):
            hits.append(digits[:4] + "..." + digits[-4:])
    return hits


def scan_text(text: str) -> dict:
    findings = {}
    if m := EMAIL_RE.findall(text):
        findings["email"] = m
    if m := PHONE_RE.findall(text):
        findings["phone_number"] = m
    if m := SSN_SIN_RE.findall(text):
        findings["ssn_or_sin"] = m
    if m := STREET_RE.findall(text):
        findings["street_address"] = m
    if cards := find_card_numbers(text):
        findings["credit_card_number"] = cards
    return findings


def extract_pdf_text(path: Path) -> str:
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def git_tracked_pdfs():
    out = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.pdf"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return [p for p in out.split("\0") if p]


def git_staged_pdfs():
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "-z", "--diff-filter=ACM", "--", "*.pdf"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return [p for p in out.split("\0") if p]


def load_allowlist() -> set:
    if not ALLOWLIST_PATH.exists():
        return set()
    return {
        line.strip()
        for line in ALLOWLIST_PATH.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }


def main() -> int:
    paths = sorted(set(git_tracked_pdfs()) | set(git_staged_pdfs()))
    if not paths:
        return 0

    allowlist = load_allowlist()
    had_findings = False

    for rel_path in paths:
        abs_path = REPO_ROOT / rel_path
        if not abs_path.exists():
            continue  # staged deletion

        content = abs_path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        key = f"{rel_path}:{digest}"
        if key in allowlist:
            continue

        try:
            text = extract_pdf_text(abs_path)
        except Exception as e:
            print(f"[check_pdf_pii] WARNING: could not extract text from {rel_path}: {e}")
            continue

        findings = scan_text(text)
        if findings:
            had_findings = True
            print(f"\n[check_pdf_pii] Possible PII in {rel_path}:")
            for category, matches in findings.items():
                shown = ", ".join(str(m) for m in matches[:5])
                print(f"    {category}: {shown}")
            print(f"    sha256: {digest}")

    if had_findings:
        print(
            "\n[check_pdf_pii] Review the matches above. If they're false positives or "
            "intentionally-synthetic fixture data, allowlist by appending "
            f"'<path>:<sha256>' to {ALLOWLIST_PATH.relative_to(REPO_ROOT)}."
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
