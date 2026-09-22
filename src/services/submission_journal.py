"""Durable local submission progress. All writers must share this journal."""
import fcntl
import hashlib
import json
import sqlite3
from pathlib import Path

from services.notion_retry import definitely_rejected


def file_sha256(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def submission_scope(environment: str, expense_db_id: str, split_db_id: str) -> str:
    return json.dumps([environment, expense_db_id.replace('-', '').lower(),
                       split_db_id.replace('-', '').lower()])


class SubmissionJournal:
    """Serialize local submissions and commit each operation independently.

    The OS lock is released on process exit. SQLite transactions never span
    network calls; an unfinished create remains uncertain after a crash.
    """

    def __init__(self, path: Path):
        self.path = Path(path).resolve()

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = self.path.with_suffix('.lock').open('a')
        self.lock_path = self.path.with_suffix('.lock')
        self.lock_path.chmod(0o600)
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.lock.close()
            raise RuntimeError('Another submission is running; retry after it finishes') from None
        try:
            self.db = sqlite3.connect(self.path)
            self.path.chmod(0o600)
            self.db.row_factory = sqlite3.Row
            self.db.executescript('''
                CREATE TABLE IF NOT EXISTS submissions (
                    id TEXT PRIMARY KEY, scope TEXT NOT NULL, receipt_hash TEXT NOT NULL,
                    payload TEXT NOT NULL, source TEXT, archive_path TEXT,
                    UNIQUE(scope, receipt_hash)
                );
                CREATE TABLE IF NOT EXISTS operations (
                    submission_id TEXT NOT NULL, name TEXT NOT NULL,
                    status TEXT NOT NULL, result TEXT,
                    PRIMARY KEY(submission_id, name)
                );
            ''')
            return self
        except BaseException:
            if hasattr(self, 'db'):
                self.db.close()
            self.lock.close()
            raise

    def __exit__(self, *args):
        self.db.close()
        self.lock.close()

    def find_completed(self, scope: str, receipt_hash: str):
        """Read-only preflight: require all Notion writes to be completed.

        Local archiving is separate from submission. Moving or deleting the
        archived PDF must not cause a submitted receipt to enter review again.
        """
        if not self.path.is_file():
            return None
        db = sqlite3.connect(self.path.as_uri() + '?mode=ro')
        db.row_factory = sqlite3.Row
        try:
            row = db.execute('SELECT * FROM submissions WHERE scope=? AND receipt_hash=?',
                             (scope, receipt_hash)).fetchone()
            if not row:
                return None
            operations = {op['name']: op for op in db.execute(
                'SELECT * FROM operations WHERE submission_id=?', (row['id'],))}
            splits = json.loads(row['payload']).get('splits') or []
            required = ['expense'] + [name for i in range(len(splits)) for name in (f'split:{i}', f'link:{i}')]
            if any(name not in operations or operations[name]['status'] != 'completed' for name in required):
                return None
            return json.loads(operations['expense']['result'])
        finally:
            db.close()

    def receipt_hash_for_missing_source(self, scope: str, source: Path) -> str:
        rows = self.db.execute('SELECT * FROM submissions WHERE scope=? AND source=?',
                               (scope, str(source.resolve()))).fetchall()
        if len(rows) != 1:
            raise RuntimeError('Receipt is missing; cannot uniquely identify its submission')
        row = rows[0]
        destination = row['archive_path']
        if not destination or not Path(destination).is_file() or file_sha256(Path(destination)) != row['receipt_hash']:
            raise RuntimeError('Receipt is missing and its archived copy could not be verified')
        return row['receipt_hash']

    def prepare(self, scope: str, receipt_hash: str, payload: dict, source=None) -> str:
        submission_id = hashlib.sha256(f'{scope}\n{receipt_hash}'.encode()).hexdigest()
        encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        row = self.db.execute('SELECT payload FROM submissions WHERE id=?', (submission_id,)).fetchone()
        if row and row['payload'] != encoded:
            raise RuntimeError(f'Submission {submission_id}: approved data changed; reconcile before resubmitting')
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO submissions(id,scope,receipt_hash,payload,source) VALUES(?,?,?,?,?)',
                            (submission_id, scope, receipt_hash, encoded,
                             str(source.resolve()) if source else None))
        return submission_id

    def archive_destination(self, submission_id: str, choose):
        row = self.db.execute('SELECT archive_path FROM submissions WHERE id=?', (submission_id,)).fetchone()
        if row['archive_path']:
            return Path(row['archive_path'])
        destination = Path(choose()).resolve()
        with self.db:
            self.db.execute('UPDATE submissions SET archive_path=? WHERE id=?', (str(destination), submission_id))
        return destination

    def run(self, submission_id: str, name: str, call, *, creates_page=False):
        row = self.db.execute('SELECT * FROM operations WHERE submission_id=? AND name=?',
                              (submission_id, name)).fetchone()
        if row and row['status'] == 'completed':
            return json.loads(row['result'])
        if row and row['status'] == 'uncertain' and creates_page:
            raise RuntimeError(f'Submission {submission_id}, operation {name}: outcome uncertain; '
                               'reconcile the Notion page before retrying (see docs/SUBMISSION_RECOVERY.md)')
        self._record(submission_id, name, 'uncertain' if creates_page else 'pending')
        try:
            result = call()
        except Exception as error:
            if creates_page:
                if definitely_rejected(error):
                    self._record(submission_id, name, 'pending')
                else:
                    raise RuntimeError(f'Submission {submission_id}, operation {name}: outcome uncertain '
                                       f'({error}); reconcile before retrying '
                                       '(see docs/SUBMISSION_RECOVERY.md)') from error
            raise
        self._record(submission_id, name, 'completed', result)
        return result

    def inspect(self, submission_id: str) -> dict:
        row = self.db.execute('SELECT * FROM submissions WHERE id=?', (submission_id,)).fetchone()
        if not row:
            raise ValueError('Unknown submission ID')
        result = dict(row)
        result['payload'] = json.loads(result['payload'])
        result['operations'] = [dict(operation) for operation in self.db.execute(
            'SELECT name,status,result FROM operations WHERE submission_id=? ORDER BY name', (submission_id,))]
        return result

    def reconcile(self, submission_id: str, name: str, *, page_id=None, confirmed_not_created=False):
        """Resolve an uncertain create only after the operator verifies Notion.

        A missing search result alone is not proof that creation failed.
        This method does not contact Notion or validate page contents.
        """
        from uuid import UUID
        if bool(page_id) == bool(confirmed_not_created):
            raise ValueError('Provide a verified page ID or explicitly confirm no page was created')
        if page_id:
            page_id = str(UUID(page_id))
        row = self.db.execute('SELECT status FROM operations WHERE submission_id=? AND name=?',
                              (submission_id, name)).fetchone()
        if not row or row['status'] != 'uncertain':
            raise ValueError('Only uncertain creation operations can be reconciled')
        self._record(submission_id, name, 'completed' if page_id else 'pending', page_id)

    def _record(self, submission_id, name, status, result=None):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO operations VALUES(?,?,?,?)',
                            (submission_id, name, status, json.dumps(result)))
