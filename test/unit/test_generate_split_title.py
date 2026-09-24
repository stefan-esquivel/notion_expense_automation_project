"""Expense and split titles share the same reviewed description."""
from datetime import datetime
from unittest.mock import patch
import pytest
from src.services.notion_api import NotionExpenseClient

pytestmark = pytest.mark.unit

@pytest.mark.parametrize('merchant,description,expected', [
    ("Longo's", "Longo's Expense (Coho Salmon)", "Lydia's Longo's Expense (Coho Salmon) Split"),
    ('Walmart', 'Walmart Order (Milk, Bread, Eggs)', "Lydia's Walmart Order (Milk, Bread, Eggs) Split"),
    ('Electrical Bill', 'Electrical Bill Charge', "Lydia's Electrical Bill Charge Split"),
    ('Shop', '', "Lydia's Shop Split"),
])
def test_reviewed_title_preserved(merchant, description, expected):
    with patch('src.services.notion_api.Client'):
        client = NotionExpenseClient('synthetic', 'expenses', 'splits', 'balances')
    assert client.generate_split_title('Lydia', merchant, description, datetime(2020, 1, 2)) == expected
