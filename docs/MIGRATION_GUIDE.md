# Upgrading to the LangGraph workflow

1. Stop active CLI processes. Back up configuration, receipt directories and the
   entire `.submission-state/` directory while no writer is active. Keep the backup
   private: the journal contains approved expense data and Notion IDs.
2. Use the architecture baseline from branch 19 for issue 26. The old issue-26
   branch was based on main and contained the revert of PR #40; replaying that
   revert removes architecture work. No historical Notion data migration is
   performed by this upgrade.
3. Use Python 3.11+ on macOS/Linux and install `requirements.txt` in a virtual
   environment. For tests also install `requirements-dev.txt`. No dependency
   upgrades are required by this documentation/test change.
4. Compare `.env.example` with your configuration without overwriting credentials.
   Keep token, expense/split database IDs, `BALANCES_PAGE_ID`, name aliases and
   Notion person IDs. Add `OPENAI_API_KEY` for LLM-assisted processing. Missing LLM
   credentials use the documented fallbacks, not another provider.
5. Preserve environment selection: `APP_ENV=qa` loads `.env.qa`, `prod` loads
   `.env.prod`; unset/`dev` loads `.env` under internal scope `local`. Missing
   QA/production files fall back to `.env`. Keep database IDs and environment
   stable when resuming existing submissions because they scope journal identity.
6. Run from the repository root with `python src/main.py`. The CLI already invokes
   LangGraph; there is no feature flag, legacy fallback or parallel execution path.
   `run.sh` is an alternative wrapper that specifically expects `venv/`, whereas
   the README uses `.venv/` and direct Python commands.
7. Service modules live in `src/services/`, models in `src/domain/`, LLM helpers in
   `src/llm/`, and graph/state/nodes in `src/workflows/langgraph/`. For programmatic
   use set `PYTHONPATH=src` and use `services.*`/`workflows.*` imports.
8. Keep `INPUT_FOLDER` and `PROCESSED_FOLDER` settings. New archives use
   `processed/YYYY/MMM/vendor/`; existing archives need not be renamed or moved.
   Preserve `.submission-state/journal.sqlite3` at the new checkout's project root
   if moving the checkout. Resume pending operations with their original source
   paths and approved values where possible; reconcile path/archive discrepancies
   using the recovery guide rather than deleting state.

Historical/manual Notion entries are not automatically covered by journal
identity. Re-encoded PDFs and separate journals can also evade duplicate detection.
Check such receipts against Notion before submitting. The journal is local to a
checkout; it is not a shared multi-machine uniqueness service.

Run `python -m pytest test/unit/ test/integration/` to verify the installation with
mocked external services. Live Notion QA is separate under issue 57 and must use
QA databases. `QA_SKIP_COMMIT=true` suppresses writes/moves, but startup still
checks Notion and LLM calls remain possible.

Read [submission recovery](SUBMISSION_RECOVERY.md) for uncertain writes, partial
submissions and archive-only recovery. Full CLI retries skip receipts once their
Notion operations are complete, even if archiving previously failed. Keep the
journal when rolling back code; a code rollback does not undo Notion writes.
