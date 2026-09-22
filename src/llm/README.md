# Receipt LLM integration

`client.py` wraps the OpenAI SDK, `prompts.py` holds prompts, and
`receipt_extractor.py` converts responses into domain models and supplies keyword
fallback. The implemented client uses Chat Completions with JSON responses and
default model `gpt-4o-mini`. A caller can pass a model to `ReceiptLLMClient`; there
is no CLI provider selector or model environment setting.

## Setup and use

Install the root `requirements.txt` and set `OPENAI_API_KEY` in the selected dotenv
file or process environment. Configuration is loaded through `src/config.py`.
The constructor raises ValueError when no key is available; workflow callers
handle this according to the operation below. Other providers are not implemented.

With `PYTHONPATH=src`, imports are `from llm.client import ReceiptLLMClient` and
`from llm.receipt_extractor import llm_enrich_receipt`. Normal execution is
`python src/main.py` from the root, which selects the workflow automatically.

## Calls and fallback

| Workflow operation | LLM use | Failure behavior |
| --- | --- | --- |
| Extract | `extract_items` receives raw PDF text | Empty item list; deterministic amount/date/merchant parsing remains |
| Augment | `llm_extract_receipt` attempts missing fields from raw text | Unfilled fields remain for validation/review |
| Enrich | `llm_enrich_receipt` receives merchant, date and items | Keyword category with confidence 0.5; unknown matches use `other` |
| Validate/revalidate | Suspicious-confidence check when eligible | No LLM-specific issue; low-enrichment-confidence advisory still applies when appropriate |

Enrichment skips vendor `Unknown`. The graph does not choose extraction versus
validation via confidence bands. High confidence never bypasses human review.
`llm_validate_receipt` and `llm_parse_date` exist as helpers but are not nodes in
the current graph. Item summary text uses the first three names, not an LLM
summary or grouped category totals.

The wrapper attempts eligible connection/timeout/rate-limit/server failures up to
three times with exponential waits; the SDK may also retry internally. Other
client errors and invalid JSON propagate to the caller's fallback. No persistent
LLM cache, batching or automatic provider switching is implemented.

Raw receipt text and metadata may leave the machine for OpenAI. Notion submission
is a separate operation. `QA_SKIP_COMMIT` does not disable LLM calls. Do not assume
a fixed call count or cost per receipt: augmentation and revalidation can add calls.

## Verification

Run `python -m pytest test/unit/ test/integration/` from the root. The suite mocks
LLM responses and failures; it does not establish live model quality or availability.
The [verification report](../../docs/WORKFLOW_VERIFICATION.md) records coverage,
including the missing-key fallback through the graph. See the
[workflow guide](../workflows/langgraph/WORKFLOW_GUIDE.md) for routing.
