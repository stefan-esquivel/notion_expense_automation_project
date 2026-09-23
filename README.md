# Notion Expense Automation

Process text-based PDF receipts through a LangGraph workflow, review the extracted
values, and create linked Notion expenses and splits. Successful submissions are
archived locally; a durable journal supports retries and duplicate detection.

## Installation

Use Python 3.11+ on macOS/Linux (the submission journal uses `fcntl` for locking).
Release preparation is verified on Python 3.13.2. Run commands from the repository root.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

Configure these values in `.env`:

| Variable | Purpose |
| --- | --- |
| `NOTION_API_TOKEN` | Integration token with access to the expense, split and balances resources |
| `EXPENSE_TABLE_DATABASE_ID` | Expense database ID |
| `SPLIT_DETAILS_DATABASE_ID` | Split database ID |
| `BALANCES_PAGE_ID` | The balances row/page ID, not its database ID |
| `YOUR_NAME`, `PARTNER_NAME` | Payer/person aliases |
| `YOUR_USER_ID`, `PARTNER_USER_ID` | Corresponding Notion person IDs |
| `YOUR_EMOJI`, `PARTNER_EMOJI` | Optional icons |
| `OPENAI_API_KEY` | Enables item extraction, augmentation and enrichment |
| `INPUT_FOLDER` | Defaults to `receipts/input` |
| `PROCESSED_FOLDER` | Defaults to `receipts/processed` |
| `DEFAULT_SPLIT_PERCENTAGE` | Defaults to `50.0` |

Connect the Notion integration to the relevant databases. The schema must match
`src/services/notion_api.py`, including the expense-to-split relation named
`Split Details Table`; this application does not create the schema.

`APP_ENV=qa` selects `.env.qa`; `APP_ENV=prod` selects `.env.prod`. Unset, `dev`,
and other values load `.env` and use the internal environment name `local`.
Missing QA/production files fall back to `.env` with a warning. Exported variables
are not overwritten by dotenv. Use separate QA database IDs for live QA work.

## Run

Place lowercase `*.pdf` files directly in the input directory, then run:

```sh
python src/main.py
# With a configured .env.qa:
APP_ENV=qa python src/main.py
```

The CLI validates configuration and checks Notion connectivity, then processes
files sequentially. Every receipt proceeding to submission is reviewed, even
with high confidence. Review handles corrections, warnings, payer, splits and
final confirmation. Edited values are revalidated before commit; unresolved
issues return to review. Declining or cancelling ends that receipt as failed.

`QA_SKIP_COMMIT=true` skips journal duplicate lookup, Notion writes and file moves.
It is not an offline mode: CLI startup still checks Notion, and LLM calls can
still occur. Automated unit/integration tests mock these external services.

After Notion writes and links succeed, the file moves to
`receipts/processed/YYYY/MMM/vendor/` (for example `2026/Mar/walmart_order/`).
Logs are written under `logs/`. See the [workflow guide](src/workflows/langgraph/WORKFLOW_GUIDE.md)
for routing and the [LLM guide](src/llm/README.md) for data sent to OpenAI and fallback behavior.

## Duplicates and recovery

Preserve `.submission-state/journal.sqlite3` between runs and upgrades. Completed
Notion submissions with the same PDF bytes, environment and target database IDs
are skipped before parsing, LLM calls or review. Duplicate input files remain in
place. Historical/manual Notion entries and differently encoded PDFs are not
automatically detected.

Partial submissions reuse recorded writes. Ambiguous creation outcomes require
manual reconciliation. If Notion succeeded but archiving failed, a full CLI retry
reports a duplicate; recover the local archive separately. Follow
[submission recovery](docs/SUBMISSION_RECOVERY.md), including its local locking
and multi-machine limitations. Do not delete the journal to force a retry.

## Project layout

```text
src/
  main.py                         CLI and batch orchestration
  config.py                       dotenv selection and configuration
  logger.py                       logging
  domain/                         enums and Pydantic models
  services/                       PDF parsing, Notion, UI, files and journal
  llm/                            OpenAI client, prompts and model conversion
  workflows/langgraph/            compiled graph, state and nodes
scripts/reconcile_submission.py   manual journal reconciliation
receipts/input/                   incoming PDFs
receipts/processed/               archived PDFs
.submission-state/                persistent local submission journal
test/                           unit, integration, e2e and fixture data
```

## Verification

```sh
python -m pip install -r requirements-dev.txt
python -m pytest test/unit/ test/integration/
python -m pytest test/unit/ test/integration/ --cov=src --cov-report=term-missing
```

See [issue 26 verification](docs/WORKFLOW_VERIFICATION.md) for the tested baseline,
coverage, behavior map and remaining limitations. See [release verification](docs/RELEASE_VERIFICATION.md)
for clean-install checks and dependency compatibility, and [changelog](CHANGELOG.md)
for the pending 2.0.0 release. Live Notion verification is
separate (issue 57); never run e2e against production.

## Troubleshooting

- No files: check `INPUT_FOLDER`; scanning is nonrecursive and uses `*.pdf`.
- Connection failure: check tokens, IDs, schema and integration connections.
- Missing/nonpositive amount or image-only PDF: extraction fails before review;
  provide a readable text PDF. OCR is not implemented.
- Missing date: scan/augment attempts recovery, then review handles unresolved values.
- Missing OpenAI key or service failure: item extraction returns an empty list,
  augmentation may leave missing fields, and enrichment uses keyword fallback.
  Review remains required.

For upgrades, use the [migration guide](docs/MIGRATION_GUIDE.md). For implementation
details, see [architecture](ARCHITECTURE.md). Keep credentials and personal receipts
out of version control; receipt text may be sent to OpenAI and approved data to Notion.
