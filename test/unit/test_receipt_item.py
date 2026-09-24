import pytest
from pydantic import ValidationError

from src.domain.models.receipt_item import ReceiptItem
from src.domain.models.grocery import ReceiptItem as LegacyReceiptItem


@pytest.mark.unit
@pytest.mark.parametrize('model', [ReceiptItem, LegacyReceiptItem])
@pytest.mark.parametrize('price', [-13.61, -2.0, 0.0, 12.50])
def test_line_items_allow_credits_and_charges(model, price):
    assert model(name='Bill adjustment', price=price).price == price


@pytest.mark.unit
@pytest.mark.parametrize('model', [ReceiptItem, LegacyReceiptItem])
@pytest.mark.parametrize('price', [float('nan'), float('inf'), float('-inf')])
def test_line_items_require_finite_amounts(model, price):
    with pytest.raises(ValidationError):
        model(name='Invalid adjustment', price=price)


@pytest.mark.unit
def test_extraction_preserves_bill_discounts():
    from unittest.mock import Mock
    from src.services.pdf_extractor import PDFExtractor

    extractor = PDFExtractor(use_llm_for_items=True)
    extractor.llm_client = Mock()
    extractor.llm_client.extract_items.return_value = {'items': [
        {'name': 'Electricity', 'price': 100.0},
        {'name': 'Ontario Electricity Rebate', 'price': -13.61, 'category': 'other'},
        {'name': 'Ebilling Credit', 'price': -2.0, 'category': 'other'},
    ]}
    items = extractor.extract_items('Billing statement')
    assert [item.price for item in items] == [100.0, -13.61, -2.0]
    assert sum(item.price for item in items) == pytest.approx(84.39)
