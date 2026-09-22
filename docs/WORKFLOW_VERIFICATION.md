# Issue 26 workflow verification

Verified on 2026-09-22, macOS, Python 3.13.2, using the existing `.venv`.

## Revision and branch correction

Baseline: `13442f04c9bd1ed57f2ba4f9c435cdba488ff1cc`, the local branch 19 tip.
Branch 26 originally pointed to `4938161` (also main), with 22 commits unique to
19 and three unique to 26. Those three were PR #40's merge, its revert `9db8662`,
and PR #41's merge of that revert. An in-progress rebase was replaying the revert
onto branch 19, causing architecture deletions/conflicts.

The original tip was preserved as `backup/26-before-base-correction` and the
conflicted worktree/index/rebase metadata were saved outside the repository.
Skipping the sole replayed revert completed the rebase with branch 26 exactly at
`13442f0`. The remote branch was not changed.

Final verification uses that baseline plus the issue-26 working-tree changes.
Production executable behavior is unchanged; the only source edit corrects stale
enrichment routing comments/docstrings. Verification ran before committing these tests and documentation.
The source/test content digest below identifies the tested working tree independently
of a future commit ID.

## Commands and results

From the repository root:

```sh
# Baseline, before issue-26 edits:
.venv/bin/python -m pytest test/unit/ test/integration/ --cov=src --cov-report=term-missing --cov-report=json:/tmp/issue26-baseline-coverage.json
# Final working tree:
.venv/bin/python -m pytest test/unit/ test/integration/ --cov=src --cov-report=term-missing --cov-report=json:/tmp/issue26-final-coverage.json
.venv/bin/python -m pip check
git diff --check
```

| Metric | Baseline | Final |
| --- | --- | --- |
| Tests | 429 passed | 441 passed |
| Duration | 5.59 s | 6.22 s |
| Overall line coverage | 1614/2059, 78.39% | 1623/2059, 78.82% |
| Workflow node line coverage | 577/605, 95.37% | 582/605, 96.20% |
| Graph module line coverage | 55/76, 72.37% | 56/76, 73.68% |

This measures line coverage, not branch coverage. No blanket percentage gate was
applied. Dependency consistency and whitespace checks passed. Local coverage JSON
and logs are under `/tmp/issue26-{baseline,final}-{coverage.json,tests.log}`.

## Behavior map and gap decisions

Existing tests were inspected before additions. The matrix records reuse as well
as targeted new coverage; no duplicate test directory or fixture set was added.

| Behavior | Evidence in `test/` | Issue-26 action |
| --- | --- | --- |
| Amazon, Walmart and Longo's PDFs through the real graph | `integration/test_pdf_to_notion.py::test_pdf_through_entire_graph` | Added explicit high-confidence review/confirmation and persisted GREEN assertions |
| Failure termination at every precommit graph stage | `unit/test_graph_routing.py::test_failed_node_terminates_without_running_downstream` | Added eight parameterized compiled-graph cases, including scan failure and revalidation |
| Ingestion and extraction failure | `integration/test_pdf_to_notion.py`, `unit/test_extract_node.py` | Added corrupt-PDF ingestion failure with no review/write and source retained; existing extraction failure retained |
| Missing field routing | `unit/test_scan_node.py`, `unit/test_augment_node.py` | Added real graph/parser test with supplied synthetic missing-date text, mocked augmentation and verified Notion date |
| Missing LLM credentials | `unit/test_enrich_node.py`, `unit/test_validate_node.py` | Added full PDF graph fallback with empty items, keyword confidence 0.5 and acknowledged advisory |
| Corrections and revalidation loop | `integration/test_review_workflow.py` | Reused corrected payload, invalid-edit loop, revalidation failure and warning/override tests |
| Cancellation and declined confirmation | `integration/test_review_workflow.py::test_rejected_review_never_commits` | Reused cancel, decline and reject-warning cases |
| Duplicate short-circuit | `integration/test_pdf_to_notion.py` | Reused renamed PDF and moved-back archive cases; no parsing/review/new pages |
| Partial submission and ambiguous creation | `integration/test_commit_recovery.py`, `integration/test_submission_journal.py` | Reused split/link failures, rate limiting, uncertain writes, changed payload and process-lock tests |
| Archive-only recovery and collisions | `integration/test_commit_recovery.py` | Reused archive retry, interrupted move and conflicting destination tests |
| Full graph after archive failure | `integration/test_pdf_to_notion.py::test_archive_failure_is_duplicate_on_full_graph_retry` | Added assertion that retry skips completed Notion writes, retains input and does not retry archive |
| CLI duplicate reporting | `unit/test_duplicate_reporting.py` | Reused separate duplicate outcome/count tests |

The PDF graph fixture now sets a synthetic OpenAI key explicitly so its mocked
item call does not depend on the developer's credentials. The missing-key test
removes it deliberately. Notion/LLM calls are mocked, journals and archives use
temporary paths, and no new PDF fixtures were added.

No runtime defect was found by this verification. The full-graph archive skip is
existing intentional behavior, now tested and documented rather than changed.
The initial run of the new augmentation test exposed an omitted required field
in the test's Receipt model; that test fixture was corrected before the final run.

## Documentation checks

README, architecture, workflow and LLM guides now describe the implemented paths,
state, configuration, mandatory review/revalidation and fallback behavior. The
migration guide preserves the journal and explains legacy/manual record limits.
Recovery details link to the existing submission recovery guide.

Executed the documented `PYTHONPATH=src` imports and state-building example without
invoking the live CLI. Parsed the draw.io XML and compared its directed edge set
to `build_graph().get_graph().edges`: exact match, including duplicate/failure
exits and the persisted revalidation loop. Checked relative Markdown links in
all edited/new guides against the filesystem and reviewed CLI commands against
`main.py`, `config.py` and `run.sh`.

## Limits and deferred work

- Overall coverage includes unused OAuth code (0%) and helper/demo paths. Remaining
  graph lines are its sample `main()` runner. LLM modules are 44% covered; these
  mocked tests do not establish model output quality or live provider availability.
- Some interactive UI, configuration environment-loading and archive mutation
  guards remain uncovered. The tested contracts above, rather than exhaustive
  path coverage, define this verification scope.
- The existing environment passed `pip check`; a clean dependency installation
  and Windows support were not verified. The journal requires `fcntl`.
- No live Notion/API calls or production e2e tests were run. Live QA remains #57.
- Journal deduplication covers this local history and PDF identity only; central
  uniqueness remains #55. Triggers remain deferred under #25; broad cleanup and
  dependency upgrades remain #27.

Source/test SHA-256: `f319d5bcfc744e34930f857f5232dc6447e9359e9389079912f28b27d94a7555`. Computed over sorted `src/**/*.py`,
`test/unit/test_*.py` and `test/integration/test_*.py`, feeding each relative path,
a NUL, file bytes and a NUL into SHA-256.
