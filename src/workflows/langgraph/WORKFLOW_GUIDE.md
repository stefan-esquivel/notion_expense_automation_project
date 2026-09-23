# LangGraph workflow guide

The implementation is in [graph.py](graph.py), with a TypedDict in [state.py](state.py)
and Pydantic models in [domain/models](../../domain/models/).

## Entry point and state

Run `python src/main.py` from the repository root after configuration. For code
that builds a state without processing it, run with `PYTHONPATH=src`:

```python
from workflows.langgraph.graph import build_graph, create_initial_state
from domain.enums import WorkflowStatus

app = build_graph()
state = create_initial_state('receipts/input/receipt.pdf')
assert state['status'] == WorkflowStatus.PENDING
assert state['workflow_input'].file_path == 'receipts/input/receipt.pdf'
# app.invoke(state) performs interactive review and may write to Notion/move files.
```

Imports use `workflows`, `domain`, `services` and `llm` with `src` on the Python
path. Input fields belong to `state['workflow_input']`, not the state root.
`create_initial_state` initializes receipt/results to None and acknowledgements
to an empty set. `status` tracks the current phase; state holds all workflow data.

## Routing

`ingest → extract → scan → [augment if missing fields] → enrich → validate →
review → revalidate → commit → END`.

- Ingest checks for completed duplicates before PDF parsing, then supplies raw text.
- FAILED stops after ingest, extract, scan, augment, enrich, validate, review or
  revalidate. DUPLICATE stops at ingest.
- Validation always proceeds to review when it succeeds, including at high confidence.
- Review updates the receipt and approved summary. Revalidation runs the actual
  validate node again and persists the new result.
- Unresolved findings return to review. `ValidationResult.is_green(acknowledged)`
  allows commit only when every issue key is acknowledged or no issues remain.
  RED overrides are explicit user actions; YELLOW warnings require acknowledgement.
- Cancelled/declined review sets FAILED and never commits.
- Commit journals Notion operations and archives the file; no separate archive,
  failure or auto-commit nodes exist.

See the [architecture diagram](../../../ARCHITECTURE.md) for every edge.

## Extraction and review limits

Missing/nonpositive totals fail extraction before augmentation or review. Missing
dates can reach augmentation; failed LLM recovery leaves fields for review.
Image-only PDFs have no OCR path. Item summaries use the first three extracted
item names; grouped grocery totals are not implemented.

Review displays scan/augmentation results, handles validation findings, allows
edits, asks for payer/splits, and requests final confirmation. Payer/split selection
is reused across the revalidation loop. Confidence warnings do not make review
optional. `requires_review` is a derived model property, not the graph router.

## Recovery and testing

Preserve the local submission journal. Full graph retries skip completed Notion
submissions even when their archive step failed; direct commit recovery can reuse
the original approved summary for archive-only repair. Follow the
[recovery guide](../../../docs/SUBMISSION_RECOVERY.md) before reconciling uncertain writes.

From the root, run `python -m pytest test/unit/ test/integration/`. See the
[verification report](../../../docs/WORKFLOW_VERIFICATION.md) for coverage and behavior
mapping. Tests mock interactive UI, Notion and LLM calls; live QA is separate.
