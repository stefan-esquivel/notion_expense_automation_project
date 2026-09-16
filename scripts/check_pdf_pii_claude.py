#!/usr/bin/env python3
"""LLM-based PII review for tracked PDFs, using the local Claude Code CLI.

Complements check_pdf_pii.py's regex heuristics with an actual reader: catches
things regex can't (names, context-dependent PII) and won't false-positive on
Luhn-valid order numbers. Runs at pre-push only — it's much slower and costs
real money per call (~$0.02-0.05 and a couple seconds per PDF, using your
existing `claude` CLI login, no API key needed), so it's a deeper second
opinion right before things leave your machine, not a per-commit gate.

Shares scripts/pii_scan_allowlist.txt with check_pdf_pii.py: a file already
reviewed and accepted there is skipped here too (same hash key), since a
human already looked at it.
"""
import json
import subprocess
import sys

from check_pdf_pii import (
    ALLOWLIST_PATH,
    REPO_ROOT,
    extract_pdf_text,
    git_staged_pdfs,
    git_tracked_pdfs,
    load_allowlist,
)
import hashlib

CLAUDE_TIMEOUT_SECONDS = 60

REVIEW_SYSTEM_PROMPT = (
    "You are a PII detection classifier. You review plaintext extracted from "
    "receipt PDFs and report whether it contains personally identifiable "
    "information belonging to an individual (not a merchant). Respond with "
    "ONLY a single JSON object, no other text, no markdown fences."
)

REVIEW_PROMPT_TEMPLATE = """Review the following text extracted from a receipt PDF. \
Flag personally identifiable information belonging to an individual customer: \
full name, home address, email, phone number, SSN/SIN, full or partially-masked \
card number, or any other identifying detail. Do NOT flag a merchant's own \
public business name/address/support phone number, product names, prices, or \
order/confirmation numbers on their own (those aren't PII by themselves).

Respond with ONLY this JSON shape, nothing else:
{{"has_pii": true|false, "findings": [{{"category": "<short category>", "detail": "<short description, do NOT repeat the actual sensitive value>"}}]}}

--- RECEIPT TEXT START ---
{text}
--- RECEIPT TEXT END ---
"""


def ask_claude(text: str) -> dict:
    prompt = REVIEW_PROMPT_TEMPLATE.format(text=text[:8000])
    result = subprocess.run(
        [
            "claude", "-p", prompt,
            "--output-format", "json",
            "--allowedTools", "",
            "--system-prompt", REVIEW_SYSTEM_PROMPT,
        ],
        capture_output=True, text=True, timeout=CLAUDE_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI exited {result.returncode}: {result.stderr[:500]}")

    envelope = json.loads(result.stdout)
    return json.loads(envelope["result"])


def main() -> int:
    paths = sorted(set(git_tracked_pdfs()) | set(git_staged_pdfs()))
    if not paths:
        return 0

    allowlist = load_allowlist()
    had_findings = False

    for rel_path in paths:
        abs_path = REPO_ROOT / rel_path
        if not abs_path.exists():
            continue

        content = abs_path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if f"{rel_path}:{digest}" in allowlist:
            continue

        try:
            text = extract_pdf_text(abs_path)
        except Exception as e:
            print(f"[check_pdf_pii_claude] WARNING: could not extract text from {rel_path}: {e}")
            continue

        if not text.strip():
            continue

        try:
            verdict = ask_claude(text)
        except Exception as e:
            had_findings = True
            print(f"[check_pdf_pii_claude] ERROR reviewing {rel_path}: {e}")
            print("[check_pdf_pii_claude] Treating a failed review as a failure — investigate before pushing.")
            continue

        if verdict.get("has_pii"):
            had_findings = True
            print(f"\n[check_pdf_pii_claude] Claude flagged possible PII in {rel_path}:")
            for finding in verdict.get("findings", []):
                print(f"    {finding.get('category', '?')}: {finding.get('detail', '')}")
            print(f"    sha256: {digest}")

    if had_findings:
        print(
            "\n[check_pdf_pii_claude] Review the matches above. If they're false positives or "
            "intentionally-synthetic fixture data, allowlist by appending "
            f"'<path>:<sha256>' to {ALLOWLIST_PATH.relative_to(REPO_ROOT)} "
            "(same file check_pdf_pii.py uses)."
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
