from datetime import datetime

import pytest

from src.domain.models.expense import ExpenseSummary


@pytest.mark.unit
@pytest.mark.parametrize('filename, expected', [
    (None, None),
    ('receipt.pdf', 'receipt.pdf'),
    ('x' * 96 + '.pdf', 'x' * 96 + '.pdf'),
    ('x' * 116 + '.pdf', 'x' * 96 + '.pdf'),
    ('x' * 120, 'x' * 100),
    ('é' * 116 + '.pdf', 'é' * 96 + '.pdf'),
])
def test_receipt_filename_fits_notion_limit(filename, expected):
    expense = ExpenseSummary(
        merchant_description='Electrical Bill', date=datetime(2026, 9, 23),
        amount=84.39, paid_by='Alice', receipt_filename=filename,
    )
    assert expense.receipt_filename == expected
    restored = ExpenseSummary.model_validate_json(expense.model_dump_json())
    assert restored.receipt_filename == expected


@pytest.mark.unit
def test_filename_limit_is_declared_in_schema():
    field_schema = ExpenseSummary.model_json_schema()['properties']['receipt_filename']
    string_schema = next(option for option in field_schema['anyOf'] if option['type'] == 'string')
    assert string_schema['maxLength'] == 100
