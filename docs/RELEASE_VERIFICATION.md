# Issue 27 release preparation

Verified on 2026-09-23 with Python 3.13.2 on macOS. The implementation starts at
`a5c1107be71d2809f113233dee762b6b055a0a20`, which includes issue 26 via PR #58.
Version 2.0.0 is prepared, not yet published.

## Existing work and cleanup

The CLI already delegates to LangGraph, required Notion token/database/page checks
already exist in `Config.validate()`, and the review UI methods are still called.
Retained package `__init__.py` files and the existing `recipts.py` import spelling
avoid unnecessary compatibility changes. The OAuth client remains because
`scripts/notion_oauth_setup.py` uses it. Git history retains the old application;
an additional source archive is unnecessary.

Removed unused imports, obsolete commented-out model/parser code, debug statements,
and the unused duplicate `grocery.py` model. Supported item imports use
`domain.models.receipt_item`. Updated environment examples, ignored `.venv/`, and
corrected the domain-model guide. The main workflow diagram remains unchanged:
cleanup does not alter routing. Local Markdown link targets were checked.

Fresh-checkout testing found that module-level logging opened its file before
`Config.validate()` created `logs/`. A regression test failed with
`FileNotFoundError`; logging now creates the directory itself. Four pre-existing
tests also depended on local person settings; they now use synthetic configuration
or correctly accept absent optional values. CLI tests cover startup gates, input
scanning, success/failure reporting, interruptions and the entry point.

## Dependencies

`requirements.txt` pins direct runtime dependencies to the tested versions, and
`requirements-dev.txt` contains the actual test, lint and audit tools. Removed
unused PyPDF2, langchain and langchain-openai declarations; LangGraph still brings
its required langchain-core dependency. Added explicit httpx and requests because
application modules import them. Unused async/fixture, documentation-build,
formatter and interactive-debugger development dependencies were removed.

All direct runtime packages were resolved against current stable releases except
`notion-client==2.2.1`, deliberately retained. Testing 3.1.0 failed while constructing
API errors used by retry tests. Inspection of 2.7.0 also showed that its default
API version is `2025-09-03`, while 2.2.1 uses `2022-06-28`. Current page/database
operations use the older database-ID contract. Migrating those operations and
transport/error handling is separate work; do not upgrade the SDK blindly.
Notion documents the required changes in its
[API upgrade guide](https://developers.notion.com/guides/get-started/upgrade-guide-2025-09-03).
File uploads already set their own explicit API version independently.

Pins record tested direct versions, not a full transitive lock. Reinstallations
must rerun validation because transitive requirements can resolve differently.
The clean environment initially inherited pip 24.3.1 with advisory findings;
upgrading pip to 26.2.1 cleared the audit. Installation guidance now upgrades pip.

## Verification

A new empty virtual environment installed only the two requirements files.
A separate copy of tracked files plus the new tests had no `.env`, existing logs,
submission journal or developer virtual environment. External Notion/LLM calls
remained mocked; no personal receipts were used or new PDF fixtures added.

Commands (from the repository root, or the clean copy for isolated tests):

```sh
python3 -m venv /tmp/issue27-clean-venv
/tmp/issue27-clean-venv/bin/python -m pip install --upgrade pip
/tmp/issue27-clean-venv/bin/python -m pip install -r requirements.txt -r requirements-dev.txt
/tmp/issue27-clean-venv/bin/python -m pytest test/unit/ test/integration/ --cov=src --cov-report=json:/tmp/issue27-isolated-coverage.json -o log_cli=false
/tmp/issue27-clean-venv/bin/python -m pytest test/ -o log_cli=false
/tmp/issue27-clean-venv/bin/python -m pip check
/tmp/issue27-clean-venv/bin/python -m pip_audit --format=json --output=/tmp/issue27-final-audit.json
/tmp/issue27-clean-venv/bin/ruff check src scripts test --select F401,F811
git diff --check
```

For the full-suite command, all `NOTION_TEST_*` environment variables were removed
from the subprocess environment, so live tests skipped. No production API tests
were run.

| Check | Result |
| --- | --- |
| Original architecture baseline | 441 tests passed, 78.82% line coverage |
| Clean checkout, final unit/integration suite | 452 passed in 4.78 seconds |
| Final line coverage | 1640/2048 lines, 80.08% |
| Full suite, live credentials absent | 452 passed; 11 e2e tests skipped |
| Existing developer environment | 452 unit/integration tests passed |
| Dependency consistency | `pip check` passed |
| Vulnerability audit after pip upgrade | No known vulnerabilities found |
| Unused/redefined imports and whitespace | Passed |

Timings are observations from mocked tests, not a live performance benchmark.
Source/test identity is recorded below because verification precedes the commit.

## Remaining release work

- Review and merge the release PR, then tag the approved commit `v2.0.0`, replace
  the changelog's Unreleased label with the publication date and publish notes.
- Live QA remains tracked in #57. Mocked SDK tests do not establish live service
  compatibility or model quality. Other Python versions/operating systems were
  not exercised here.
- #2 is closed. #8 and #11 are implemented and regression-tested on this branch
  but remain open pending release integration; the release PR can close them.
- First-week monitoring, user feedback and roadmap updates happen after release.
  No results for those activities are claimed.
- Triggers remain deferred under #25; shared database uniqueness remains #55.
  These are not implemented features of 2.0.0.

Source/test SHA-256: `0f523f2a07f920c144ba10c60e01faa723c99a1aa34482e5b343c699b88e057d`. Computed over sorted `src/**/*.py`,
`test/unit/test_*.py` and `test/integration/test_*.py`, feeding each relative path,
a NUL, file bytes and a NUL into SHA-256.
