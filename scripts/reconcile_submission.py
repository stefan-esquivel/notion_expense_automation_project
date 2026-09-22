"""Inspect local progress or record an operator-verified creation outcome."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from config import Config
from services.submission_journal import SubmissionJournal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('submission_id', help='Journal ID printed in the failure message')
    parser.add_argument('--journal', type=Path, default=Config.SUBMISSION_JOURNAL_PATH)
    parser.add_argument('--operation', help='Uncertain operation, e.g. expense or split:0')
    outcome = parser.add_mutually_exclusive_group()
    outcome.add_argument('--page-id', help='Existing page ID whose database and contents you verified in Notion')
    outcome.add_argument('--confirmed-not-created', action='store_true',
                         help='Allow creation again ONLY after verifying the original request created no page')
    args = parser.parse_args()
    if bool(args.operation) != bool(args.page_id or args.confirmed_not_created):
        parser.error('--operation requires --page-id or --confirmed-not-created, and vice versa')
    if not args.journal.is_file():
        parser.error('Journal does not exist')
    try:
        with SubmissionJournal(args.journal) as journal:
            if args.operation:
                journal.reconcile(args.submission_id, args.operation, page_id=args.page_id,
                                  confirmed_not_created=args.confirmed_not_created)
            print(json.dumps(journal.inspect(args.submission_id), indent=2))
    except (ValueError, RuntimeError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
