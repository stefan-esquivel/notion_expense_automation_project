"""Durability and process-level exclusion for the local submission journal."""
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from services.submission_journal import SubmissionJournal

pytestmark = pytest.mark.integration


def test_process_lock_blocks_second_writer_and_releases(tmp_path):
    path = tmp_path / 'journal.sqlite3'
    script = '''
import sys
from pathlib import Path
from services.submission_journal import SubmissionJournal
with SubmissionJournal(Path(sys.argv[1])):
    print('acquired')
'''
    env = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[2] / 'src')}
    with SubmissionJournal(path):
        other = subprocess.run([sys.executable, '-c', script, str(path)], env=env, capture_output=True, text=True)
        assert other.returncode != 0
        assert 'Another submission is running' in other.stderr
    other = subprocess.run([sys.executable, '-c', script, str(path)], env=env, capture_output=True, text=True)
    assert other.returncode == 0
    assert 'acquired' in other.stdout


def test_interrupted_create_is_uncertain_after_reopening(tmp_path):
    path = tmp_path / 'journal.sqlite3'
    with SubmissionJournal(path) as journal:
        key = journal.prepare('qa', 'receipt-hash', {'amount': 12})
        with pytest.raises(KeyboardInterrupt):
            journal.run(key, 'expense', Mock(side_effect=KeyboardInterrupt), creates_page=True)
    with SubmissionJournal(path) as journal:
        call = Mock()
        with pytest.raises(RuntimeError, match='uncertain'):
            journal.run(key, 'expense', call, creates_page=True)
        call.assert_not_called()


def test_completed_operation_reused_after_reopening(tmp_path):
    path = tmp_path / 'journal.sqlite3'
    with SubmissionJournal(path) as journal:
        key = journal.prepare('qa', 'receipt-hash', {'amount': 12})
        journal.run(key, 'expense', lambda: '1' * 32, creates_page=True)
    with SubmissionJournal(path) as journal:
        call = Mock()
        assert journal.run(key, 'expense', call, creates_page=True) == '1' * 32
        call.assert_not_called()


def test_reconciliation_reuses_verified_id(tmp_path):
    with SubmissionJournal(tmp_path / 'journal.sqlite3') as journal:
        key = journal.prepare('qa', 'hash', {})
        with pytest.raises(RuntimeError, match='uncertain'):
            journal.run(key, 'expense', Mock(side_effect=TimeoutError()), creates_page=True)
        journal.reconcile(key, 'expense', page_id='1' * 32)
        call = Mock()
        assert journal.run(key, 'expense', call, creates_page=True).replace('-', '') == '1' * 32
        call.assert_not_called()
        with pytest.raises(ValueError, match='Only uncertain'):
            journal.reconcile(key, 'expense', confirmed_not_created=True)


def test_reconciliation_requires_explicit_outcome_and_valid_id(tmp_path):
    with SubmissionJournal(tmp_path / 'journal.sqlite3') as journal:
        key = journal.prepare('qa', 'hash', {})
        with pytest.raises(RuntimeError):
            journal.run(key, 'expense', Mock(side_effect=TimeoutError()), creates_page=True)
        with pytest.raises(ValueError):
            journal.reconcile(key, 'expense')
        with pytest.raises(ValueError):
            journal.reconcile(key, 'expense', page_id='bad-id')
        journal.reconcile(key, 'expense', confirmed_not_created=True)
        call = Mock(return_value='2' * 32)
        assert journal.run(key, 'expense', call, creates_page=True) == '2' * 32
        call.assert_called_once()


def test_preflight_does_not_create_a_database(tmp_path):
    path = tmp_path / 'absent' / 'journal.sqlite3'
    assert SubmissionJournal(path).find_completed('qa', 'hash') is None
    assert not path.parent.exists()


def test_preflight_separates_scopes_and_ignores_archive_location(tmp_path):
    from services.submission_journal import file_sha256, submission_scope
    path = tmp_path / 'journal.sqlite3'
    archived = tmp_path / 'archived.pdf'
    archived.write_bytes(b'synthetic receipt')
    receipt_hash = file_sha256(archived)
    scope = submission_scope('qa', 'a' * 32, 'b' * 32)
    with SubmissionJournal(path) as journal:
        key = journal.prepare(scope, receipt_hash, {'splits': []})
        journal.run(key, 'expense', lambda: '1' * 32, creates_page=True)
        # A local archive failure does not undo a completed Notion submission.
        assert journal.find_completed(scope, receipt_hash) == '1' * 32
        journal.archive_destination(key, lambda: archived)
    before = path.read_bytes()
    journal = SubmissionJournal(path)
    assert journal.find_completed(scope, receipt_hash) == '1' * 32
    assert journal.find_completed(submission_scope('prod', 'a' * 32, 'b' * 32), receipt_hash) is None
    assert journal.find_completed(submission_scope('qa', 'c' * 32, 'b' * 32), receipt_hash) is None
    assert path.read_bytes() == before  # Preflight uses a read-only connection.
    archived.unlink()
    assert journal.find_completed(scope, receipt_hash) == '1' * 32


def test_payload_can_change_before_any_request(tmp_path):
    path = tmp_path / 'journal.sqlite3'
    with SubmissionJournal(path) as journal:
        key = journal.prepare('qa', 'hash', {'amount': 12})
    with SubmissionJournal(path) as journal:
        assert journal.prepare('qa', 'hash', {'amount': 15}) == key
        assert journal.inspect(key)['payload'] == {'amount': 15}


def test_corrected_payload_allowed_after_confirmed_non_creation(tmp_path):
    with SubmissionJournal(tmp_path / 'journal.sqlite3') as journal:
        key = journal.prepare('qa', 'hash', {'amount': 12})
        with pytest.raises(RuntimeError, match='uncertain'):
            journal.run(key, 'expense', Mock(side_effect=TimeoutError()), creates_page=True)
        journal.reconcile(key, 'expense', confirmed_not_created=True)
        assert journal.prepare('qa', 'hash', {'amount': 15}) == key
        assert journal.inspect(key)['payload'] == {'amount': 15}


@pytest.mark.parametrize('name,status', [
    ('expense', 'completed'), ('expense', 'uncertain'),
    ('split:0', 'pending'), ('link:0', 'pending'),
])
def test_payload_change_preserves_existing_progress(tmp_path, name, status):
    with SubmissionJournal(tmp_path / 'journal.sqlite3') as journal:
        key = journal.prepare('qa', 'hash', {'amount': 12})
        journal._record(key, name, status)
        before = journal.inspect(key)
        with pytest.raises(RuntimeError, match='approved data changed'):
            journal.prepare('qa', 'hash', {'amount': 15})
        assert journal.inspect(key) == before
