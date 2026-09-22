# Submission recovery

The commit node uses `.submission-state/journal.sqlite3` to remember each expense
creation, split creation, and relation link. The directory is gitignored. Keep it
between runs and back it up: deleting it removes duplicate protection. It stores
approved expense data and Notion page IDs, not API tokens. The database and lock
files are restricted to the current user.

Receipt identity is the SHA-256 of the PDF bytes, scoped to the configured
application environment and target Notion expense/split database IDs. File names
and locations do not affect identity. Approved data, balance page, and user mappings are stored
separately. Changes to those values stop submission for reconciliation; they do
not create another expense. Reordering or changing splits also requires review.

## Normal recovery

At ingestion, the workflow checks the PDF hash against completed submissions in
this environment and the same target databases. A receipt whose expense, splits,
and links are recorded as completed is skipped before PDF parsing,
LLM calls, or review. The CLI reports “Already submitted — skipped” and counts it
separately from failures. The duplicate input file is left in place. This is a
read-only check and recognizes older journal records without a migration.

Moving or deleting the archived PDF does not undo its Notion submission. A
receipt moved back to input is still skipped. If all Notion writes succeeded but
local archiving failed, recover the local file separately; re-running the full
workflow will report it as already submitted.

Submissions with incomplete Notion writes continue through the workflow so
recovery is still possible. Run them again with the same approved data and configuration. Completed
writes are reused. An explicit rejected request can be attempted again. A failed
split link reuses the split's ID. The commit node also supports archive-only recovery without creating Notion
pages again when invoked directly with the original approved summary. The full
CLI workflow skips receipts already submitted to Notion, including archived PDFs.
The destination is saved before moving, and its hash is checked before adopting
it. A duplicate input copy is removed only after the archived copy is verified.
If an interrupted copy left different/partial content at that destination, the
workflow stops: inspect it and restore the original source before retrying.

For non-file callers, retain `state['submission_token']` and the approved summary
between attempts. A fresh non-file state is a new submission, because there is
no PDF hash to identify it. The normal CLI workflow uses PDF files.

A nonblocking OS lock permits one commit at a time across processes using the
same journal on this machine. It releases on process exit. If another submission
is active, retry after it finishes. This is a local macOS/Linux journal, not a
shared multi-machine coordinator. Keep all local writers on the same checkout/
journal; separate copies do not coordinate.

## Uncertain Notion creation

A timeout, an ambiguous server failure, or process termination during creation
can leave a page in Notion without a locally saved ID. The journal marks this
operation uncertain and blocks automatic recreation. Rate-limit/overload
rejections (429/529) use bounded backoff and `Retry-After`; other create failures
are not blindly retried. Reads and relation read/merge/update operations can
retry transient errors. Final errors are surfaced to the user.

The failure message includes a submission ID and operation (`expense`,
`split:0`, etc.). Inspect the saved data with:

```sh
.venv/bin/python scripts/reconcile_submission.py SUBMISSION_ID
```

Inspect Notion and verify the page's database, expense details, or split person,
percentage and associated expense against that saved data. Once the existing
page is confirmed, record its ID:

```sh
.venv/bin/python scripts/reconcile_submission.py SUBMISSION_ID \
  --operation split:0 --page-id VERIFIED_NOTION_PAGE_ID
```

Then rerun the receipt. The saved ID will be reused and any missing relation
will be linked. The command trusts your verification; it does not query Notion.

Only if you have established that the original request is no longer running and
created no page may you explicitly allow a new creation:

```sh
.venv/bin/python scripts/reconcile_submission.py SUBMISSION_ID \
  --operation expense --confirmed-not-created
```

An empty search result immediately after a timeout is not sufficient evidence.
If the outcome remains uncertain, leave it blocked. Do not delete the journal,
change the receipt bytes, or change database IDs to bypass this check.

When approved data has changed, restore the originally approved values to finish
the existing submission, then correct the existing Notion entry deliberately.
Automatic amendments and rollback of previously created pages are outside #24.

## Limits

This prevents this journal's retries from recreating known or uncertain writes;
it is not an exactly-once guarantee from Notion. It does not detect older/manual
Notion entries or differently encoded PDFs of the same purchase. Receipt uploads
remain best-effort as before; an orphaned upload is not treated as an expense.
Remote relation edits by independent writers are not coordinated by the local
lock. The future database investigation in issue #55 covers central uniqueness,
concurrent machines, and migration from Notion.
