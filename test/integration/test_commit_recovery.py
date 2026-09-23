"""Real journal/client/archiving recovery with only Notion I/O mocked."""
import importlib
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest
from notion_client.errors import APIResponseError, RequestTimeoutError

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from config import Config
from domain.enums import WorkflowStatus
from domain.models.expense import ExpenseSummary, SplitDetail
from workflows.langgraph.nodes.commit_node import commit_node

notion = importlib.import_module('services.notion_api')
pytestmark = pytest.mark.integration


def api_error(status):
    return APIResponseError(httpx.Response(status, headers={'Retry-After': '0'}),
                            'synthetic failure', 'rate_limited' if status == 429 else 'internal_server_error')


@pytest.fixture
def submission(tmp_path, monkeypatch):
    for key, value in {'SUBMISSION_JOURNAL_PATH': tmp_path / 'journal.sqlite3',
                       'PROCESSED_FOLDER': tmp_path / 'processed', 'ENVIRONMENT': 'qa',
                       'QA_SKIP_COMMIT': False, 'NOTION_API_TOKEN': 'synthetic',
                       'EXPENSE_TABLE_DATABASE_ID': 'e' * 32,
                       'SPLIT_DETAILS_DATABASE_ID': 's' * 32, 'BALANCES_PAGE_ID': 'b' * 32,
                       'YOUR_NAME': 'Alex', 'PARTNER_NAME': 'Sam',
                       'YOUR_USER_ID': 'a' * 32, 'PARTNER_USER_ID': 'b' * 32}.items():
        monkeypatch.setattr(Config, key, value, raising=False)
    monkeypatch.setattr(Config, 'validate', Mock())
    api = Mock()
    api.pages.create.side_effect = [{'id': '1' * 32}, {'id': '2' * 32}]
    api.pages.retrieve.return_value = {'properties': {Config.EXPENSE_RELATION_PROPERTY: {'relation': []}}}
    monkeypatch.setattr(notion, 'Client', Mock(return_value=api))
    monkeypatch.setattr(notion.NotionExpenseClient, '_upload_file_to_notion', Mock(return_value=None))
    source = tmp_path / 'receipt.pdf'
    source.write_bytes(b'synthetic receipt')
    summary = ExpenseSummary(merchant_description='Shop (Tools)', date=datetime(2020, 1, 2),
                             amount=10, paid_by='Alex', receipt_file_path=source,
                             splits=[SplitDetail(person='Sam', share_percent=50, title="Sam's Shop Split (Tools)")])
    return summary, api


def run(summary):
    # Fresh state simulates a process restart; identity must come from disk.
    return commit_node({'expense_summary': summary, 'failure_reason': None})


def test_same_file_renamed_reuses_expense(submission, tmp_path):
    summary, api = submission
    duplicate = tmp_path / 'renamed.pdf'
    duplicate.write_bytes(summary.receipt_file_path.read_bytes())
    first = run(summary)
    second = run(summary.model_copy(update={'receipt_file_path': duplicate}))
    assert first['status'] == second['status'] == WorkflowStatus.COMPLETED
    assert first['results'].notion_expense_id == second['results'].notion_expense_id
    assert api.pages.create.call_count == 2  # one expense and one split


def test_link_failure_does_not_recreate_split(submission):
    summary, api = submission
    api.pages.update.side_effect = [api_error(400), {}]
    assert run(summary)['status'] == WorkflowStatus.FAILED
    assert run(summary)['status'] == WorkflowStatus.COMPLETED
    assert api.pages.create.call_count == 2


def test_second_split_failure_preserves_first(submission):
    summary, api = submission
    summary.splits.append(SplitDetail(person='Alex', share_percent=50, title="Alex's split"))
    api.pages.create.side_effect = [{'id': '1' * 32}, {'id': '2' * 32}, api_error(400), {'id': '3' * 32}]
    assert run(summary)['status'] == WorkflowStatus.FAILED
    result = run(summary)
    assert result['results'].notion_split_ids == ['2' * 32, '3' * 32]
    assert api.pages.create.call_count == 4


@pytest.mark.parametrize('failure', [RequestTimeoutError(), api_error(503)])
def test_ambiguous_creation_is_not_retried_on_restart(submission, failure):
    summary, api = submission
    api.pages.create.side_effect = failure
    assert run(summary)['status'] == WorkflowStatus.FAILED
    result = run(summary)
    assert result['status'] == WorkflowStatus.FAILED
    assert 'uncertain' in result['failure_reason'].lower()
    assert api.pages.create.call_count == 1


def test_changed_payload_requires_reconciliation(submission):
    summary, api = submission
    api.pages.update.side_effect = api_error(400)
    run(summary)
    summary.amount = 20
    result = run(summary)
    assert result['status'] == WorkflowStatus.FAILED
    assert 'changed' in result['failure_reason'].lower()
    assert api.pages.create.call_count == 2


def test_archive_failure_retries_only_archive(submission, monkeypatch):
    summary, api = submission
    from services.file_organizer import FileOrganizer
    original = FileOrganizer.organize_file
    monkeypatch.setattr(FileOrganizer, 'organize_file', Mock(side_effect=OSError('disk unavailable')))
    assert run(summary)['status'] == WorkflowStatus.FAILED
    monkeypatch.setattr(FileOrganizer, 'organize_file', original)
    assert run(summary)['status'] == WorkflowStatus.COMPLETED
    assert api.pages.create.call_count == 2


def test_move_succeeded_before_failure_recovers(submission, monkeypatch):
    summary, api = submission
    from services.file_organizer import FileOrganizer
    original = FileOrganizer.organize_file
    def move_then_fail(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise OSError('process failed after moving')
    monkeypatch.setattr(FileOrganizer, 'organize_file', move_then_fail)
    assert run(summary)['status'] == WorkflowStatus.FAILED
    monkeypatch.setattr(FileOrganizer, 'organize_file', original)
    assert run(summary)['status'] == WorkflowStatus.COMPLETED
    assert api.pages.create.call_count == 2


def test_different_database_scope_allows_new_expense(submission, tmp_path, monkeypatch):
    summary, api = submission
    source = tmp_path / 'copy.pdf'
    source.write_bytes(summary.receipt_file_path.read_bytes())
    assert run(summary)['status'] == WorkflowStatus.COMPLETED
    monkeypatch.setattr(Config, 'EXPENSE_TABLE_DATABASE_ID', 'f' * 32)
    api.pages.create.side_effect = [{'id': '3' * 32}, {'id': '4' * 32}]
    assert run(summary.model_copy(update={'receipt_file_path': source}))['status'] == WorkflowStatus.COMPLETED
    assert api.pages.create.call_count == 4


def test_rate_limit_recovers_without_recreating_prior_operations(submission, monkeypatch):
    summary, api = submission
    monkeypatch.setattr('services.notion_retry.time.sleep', Mock())
    api.pages.create.side_effect = [api_error(429), {'id': '1' * 32}, api_error(429), {'id': '2' * 32}]
    assert run(summary)['status'] == WorkflowStatus.COMPLETED
    assert api.pages.create.call_count == 4
    assert run(summary)['status'] == WorkflowStatus.COMPLETED
    assert api.pages.create.call_count == 4


def test_exhausted_rate_limit_can_resume(submission, monkeypatch):
    summary, api = submission
    monkeypatch.setattr('services.notion_retry.time.sleep', Mock())
    api.pages.create.side_effect = api_error(429)
    assert run(summary)['status'] == WorkflowStatus.FAILED
    assert api.pages.create.call_count == 4
    api.pages.create.side_effect = [{'id': '1' * 32}, {'id': '2' * 32}]
    assert run(summary)['status'] == WorkflowStatus.COMPLETED
    assert api.pages.create.call_count == 6


def test_link_retry_reads_relations_again(submission, monkeypatch):
    summary, api = submission
    monkeypatch.setattr('services.notion_retry.time.sleep', Mock())
    api.pages.update.side_effect = [api_error(503), {}]
    api.pages.retrieve.side_effect = [
        {'properties': {Config.EXPENSE_RELATION_PROPERTY: {'relation': []}}},
        {'properties': {Config.EXPENSE_RELATION_PROPERTY: {'relation': [{'id': '2' * 32}]}}},
    ]
    assert run(summary)['status'] == WorkflowStatus.COMPLETED
    assert api.pages.create.call_count == 2
    assert api.pages.retrieve.call_count == 2
    assert api.pages.update.call_args.kwargs['properties'][Config.EXPENSE_RELATION_PROPERTY]['relation'] == [{'id': '2' * 32}]


def test_qa_skip_creates_no_journal_or_api_writes(submission, monkeypatch):
    summary, api = submission
    monkeypatch.setattr(Config, 'QA_SKIP_COMMIT', True)
    assert run(summary)['status'] == WorkflowStatus.COMPLETED
    api.pages.create.assert_not_called()
    assert not Config.SUBMISSION_JOURNAL_PATH.exists()
    assert summary.receipt_file_path.exists()


def test_archive_collision_never_overwrites_other_content(submission, monkeypatch):
    summary, api = submission
    from services.file_organizer import FileOrganizer
    original = FileOrganizer.organize_file
    def collide(self, **kwargs):
        kwargs['destination_path'].write_bytes(b'another receipt')
        return original(self, **kwargs)
    monkeypatch.setattr(FileOrganizer, 'organize_file', collide)
    assert run(summary)['status'] == WorkflowStatus.FAILED
    monkeypatch.setattr(FileOrganizer, 'organize_file', original)
    result = run(summary)
    assert result['status'] == WorkflowStatus.FAILED
    assert 'different content' in result['failure_reason']
    assert api.pages.create.call_count == 2
    assert summary.receipt_file_path.read_bytes() == b'synthetic receipt'


def test_balance_change_does_not_bypass_existing_identity(submission, monkeypatch):
    summary, api = submission
    api.pages.update.side_effect = api_error(400)
    run(summary)
    monkeypatch.setattr(Config, 'BALANCES_PAGE_ID', 'c' * 32)
    assert 'changed' in run(summary)['failure_reason']
    assert api.pages.create.call_count == 2
