# Changelog

## [2.0.0] - Unreleased

### Added

- LangGraph receipt processing with extraction, missing-field augmentation,
  validation, mandatory human review and revalidation before submission.
- Optional OpenAI item extraction and enrichment, with keyword/manual fallback.
- Durable local submission journal for duplicate detection, partial-write recovery
  and reconciliation of uncertain Notion writes.
- Workflow verification, migration and submission-recovery guides.

### Changed

- CLI delegates receipt processing to the workflow; services and domain models
  have dedicated directories.
- Split-title generation is shared by review previews and Notion submissions (#8).
- Direct dependencies are pinned to verified versions. Unused PyPDF2, langchain
  and langchain-openai declarations and unused development tools are removed.
- Obsolete commented code, unused imports and the unused duplicate grocery model
  are removed; `domain.models.receipt_item.ReceiptItem` is the supported item model.

### Fixed

- AI-assisted item descriptions (#2) and corrected merchant names in split titles
  after review (#11), completed in the architecture work.
- Fresh-checkout startup now creates the logging directory before opening logs.
- Mocked tests no longer require locally configured Notion person IDs/names.

### Upgrade notes

- Follow [migration guidance](docs/MIGRATION_GUIDE.md); preserve the complete
  `.submission-state/` directory. Historical/manual Notion records are not
  automatically deduplicated.
- Use Python 3.11+ on macOS/Linux. Configure Notion token, database/page IDs and
  people; an OpenAI key enables assistance but is optional.
- Automated folder/Gmail triggers are deferred. High confidence does not bypass
  human review. No parallel legacy workflow or migration feature flag is provided.
- Notion SDK 2.2.1 is retained for the existing database API contract; see
  [release verification](docs/RELEASE_VERIFICATION.md).

The release date and `v2.0.0` tag are pending publication.
