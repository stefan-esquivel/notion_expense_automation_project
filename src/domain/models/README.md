# Receipt workflow models

Models describe the data carried by the implemented LangGraph workflow.

| Module | Model and purpose |
| --- | --- |
| `recipts.py` | `Receipt`: vendor, transaction type, raw date, optional receipt ID/summary, item list and positive total |
| `receipt_item.py` | `ReceiptItem`: item name, price and optional category |
| `enrichment.py` | `EnrichedReceipt`: merchant category, confidence score and optional notes |
| `workflow.py` | Input, extraction, scan, augmentation, validation, review and commit results |
| `expense.py` | `ExpenseSummary` and `SplitDetail`: approved Notion payload data |

The existing `recipts.py` spelling is preserved for import compatibility.
The unused duplicate `grocery.py` model was removed in the 2.0 cleanup; import
`ReceiptItem` from `domain.models.receipt_item`.

Extraction creates a `Receipt`; scan/augmentation checks missing values.
Enrichment supplies category/confidence, and validation produces issues for review.
Review corrections are revalidated before the approved `ExpenseSummary` reaches
commit. Confidence is advisory and never grants permission to submit.

`EnrichedReceipt` does not define normalized-merchant, parsed-date, recipe or grouped
grocery-summary fields. Item summaries use the extracted items; those planned
fields are not implemented features.

See the [workflow guide](../../workflows/langgraph/WORKFLOW_GUIDE.md) and
[architecture](../../../ARCHITECTURE.md) for the graph and persistence boundaries.
