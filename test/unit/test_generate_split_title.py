"""Behavioral baseline for the #8/#24 title refactor."""
from datetime import datetime
from unittest.mock import patch

import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from src.services.notion_api import NotionExpenseClient

pytestmark = pytest.mark.unit


@pytest.fixture
def title():
    with patch('src.services.notion_api.Client'):
        client = NotionExpenseClient('synthetic', 'expenses', 'splits', 'balances')
    return lambda merchant, description='': client.generate_split_title(
        'Alex', merchant, description, datetime(2020, 1, 2))


@pytest.mark.parametrize('merchant,expected', [
    ('Amazon Order', 'Amazon Order Split'), ('Amazon', 'Amazon Split'),
    ('Electrical', 'Electrical Bill Split (Jan)'), ('Electric', 'Electrical Bill Split (Jan)'),
    ('Rent', 'Rent Split (Jan)'), ('Netflix', 'Netflix Payment (Jan)'),
    ('YouTube', 'YT Premium Split (Jan)'), ('YT', 'YT Premium Split (Jan)'),
    ('Parking', 'Parking Share (Jan)'), ("Longo's", "Longo's Groceries Share"),
    ('TV', 'TV Payment (Jan)'), ('Walmart', 'Walmart Food Split'),
    ('Festivities', 'Festivities Split'), ('Atv Parts', 'TV Payment (Jan)'),
    ('Amazon Online Order', 'Amazon Order Split'),
    ('Walmart Amazon Order', 'Walmart Food Split'),
    ('Electric Rent', 'Electrical Bill Split (Jan)'),
])
def test_keywords_and_precedence(title, merchant, expected):
    assert title(merchant) == f"Alex's {expected}"


@pytest.mark.parametrize('merchant,category', [
    ('Amazon', 'Amazon Split'), ('Amazon Order', 'Amazon Order Split'),
    ('Walmart', 'Walmart Food Split'), ('Shop', 'Shop Split'),
])
@pytest.mark.parametrize('description,suffix', [
    ('Paid (via app) (Jan)', ' (via app)'), ('Paid', ''), ('Paid ()', ''),
    ('Paid (Tools)', ' (Tools)'), ('Paid (', ''), ('Paid )', ''),
])
def test_description_details(title, merchant, category, description, suffix):
    assert title(merchant, description) == f"Alex's {category}{suffix}"


def test_misordered_parentheses_uses_first_valid_pair(title):
    assert title('Shop', 'Paid ) then (Tools)') == "Alex's Shop Split (Tools)"
