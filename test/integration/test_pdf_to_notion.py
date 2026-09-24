"""Full graph using real PDF parsing, validation, journal and file organization."""
import importlib
import shutil
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from config import Config
from domain.enums import WorkflowStatus, Sources
from domain.models.enrichment import EnrichedReceipt
from domain.models.workflow import WorkflowInput
from services.ui import ExpenseUI
from workflows.langgraph.graph import build_graph, create_initial_state

pytestmark = pytest.mark.integration
FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures' / 'pdfs'


@pytest.fixture
def workflow(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, 'OPENAI_API_KEY', 'synthetic-test-key')
    for key, value in {'SUBMISSION_JOURNAL_PATH': tmp_path / 'journal.sqlite3',
                       'PROCESSED_FOLDER': tmp_path / 'processed', 'ENVIRONMENT': 'qa',
                       'QA_SKIP_COMMIT': False, 'NOTION_API_TOKEN': 'synthetic',
                       'EXPENSE_TABLE_DATABASE_ID': 'e' * 32,
                       'SPLIT_DETAILS_DATABASE_ID': 's' * 32, 'BALANCES_PAGE_ID': 'b' * 32,
                       'YOUR_NAME': 'Alex', 'PARTNER_NAME': 'Sam',
                       'YOUR_USER_ID': 'a' * 32, 'PARTNER_USER_ID': 'b' * 32}.items():
        monkeypatch.setattr(Config, key, value)
    monkeypatch.setattr(Config, 'validate', Mock())
    api = Mock()
    api.pages.create.side_effect = [{'id': '1' * 32}, {'id': '2' * 32}]
    api.pages.retrieve.return_value = {'properties': {Config.EXPENSE_RELATION_PROPERTY: {'relation': []}}}
    notion = importlib.import_module('services.notion_api')
    monkeypatch.setattr(notion, 'Client', Mock(return_value=api))
    monkeypatch.setattr(notion.NotionExpenseClient, '_upload_file_to_notion', Mock(return_value='upload-id'))
    # Mock external LLM responses, not pipeline nodes or PDF parsing.
    llm_client = importlib.import_module('services.pdf_extractor').ReceiptLLMClient
    monkeypatch.setattr(llm_client, 'extract_items', Mock(return_value={'items': []}))
    monkeypatch.setattr(importlib.import_module('workflows.langgraph.nodes.enrich_node'),
                        'llm_enrich_receipt', Mock(return_value=EnrichedReceipt(merchant_category='grocery', confidence_score=1)))
    monkeypatch.setattr(importlib.import_module('workflows.langgraph.nodes.augment_node'),
                        'llm_extract_receipt', Mock(return_value=None))
    ui = Mock(spec=ExpenseUI)
    ui.review_and_edit.side_effect = lambda info: info
    ui.select_payer.return_value = 'Alex'
    ui.confirm_split.return_value = (True, 50)
    ui.confirm_send_to_notion.return_value = True
    ui.prompt_acknowledge_yellow.return_value = True
    for node in ('ingest_node', 'review_node'):
        monkeypatch.setattr(importlib.import_module(f'workflows.langgraph.nodes.{node}'),
                            'ExpenseUI', Mock(return_value=ui))
    return api, ui


@pytest.mark.parametrize('filename,amount,title', [
    ('2026-03-07_Amazon_Order_Baking_Sheets_$49.60.pdf', 49.60, "Sam's Amazon Order Split"),
    ('2026-03-04_Walmart_Order_Meatballs_$80.59.pdf', 80.59, "Sam's Walmart Order Split"),
    ('2026-09-19_Longos_Groceries_English_Cucumbers_Dill_Weed_Grape_Tomatoes_$59.90.pdf', 59.90, "Sam's Longo's Expense Split"),
])
def test_pdf_through_entire_graph(workflow, tmp_path, filename, amount, title):
    api, ui = workflow
    source = tmp_path / 'input.pdf'
    shutil.copyfile(FIXTURES / filename, source)
    result = build_graph().invoke(create_initial_state(str(source)))
    assert result['status'] == WorkflowStatus.COMPLETED, result.get('failure_reason')
    expense, split = [call.kwargs['properties'] for call in api.pages.create.call_args_list]
    assert expense['Amount']['number'] == amount
    assert expense['Receipt (optional)']['files'][0]['file_upload']['id'] == 'upload-id'
    assert split['Title']['title'][0]['text']['content'].startswith(title)
    assert split['Share Percent']['number'] == 0.5
    assert result['results'].notion_expense_id == '1' * 32
    assert result['results'].notion_split_ids == ['2' * 32]
    assert result['results'].archive_path.is_file()
    assert not source.exists()
    ui.review_and_edit.assert_called_once()
    ui.confirm_send_to_notion.assert_called_once()
    assert result['validation_result'].is_green(result['acknowledged_warnings'])
    # Re-processing the archived PDF also traverses the real graph, without new pages.
    again = build_graph().invoke(create_initial_state(str(result['results'].archive_path)))
    assert again['status'] == WorkflowStatus.DUPLICATE, again.get('failure_reason')
    assert api.pages.create.call_count == 2


def test_invalid_pdf_stops_before_submission(workflow, tmp_path):
    api, ui = workflow
    source = tmp_path / 'broken.pdf'
    source.write_text('not a PDF')
    state = {'workflow_input': WorkflowInput(source=Sources.LOCAL_FOLDER, file_path=str(source), raw_text='invalid PDF'),
             'status': WorkflowStatus.PENDING}
    result = build_graph().invoke(state)
    assert result['status'] == WorkflowStatus.FAILED
    api.pages.create.assert_not_called()
    assert source.exists()


def test_corrupt_pdf_fails_during_ingestion(workflow, tmp_path):
    api, ui = workflow
    source = tmp_path / 'corrupt.pdf'
    source.write_bytes(b'not a PDF')
    result = build_graph().invoke(create_initial_state(str(source)))
    assert result['status'] == WorkflowStatus.FAILED
    assert 'Ingestion failed' in result['failure_reason']
    ui.review_and_edit.assert_not_called()
    api.pages.create.assert_not_called()
    assert source.exists()


def test_missing_date_routes_through_augment(workflow, tmp_path, monkeypatch):
    from domain.models.recipts import Receipt

    api, ui = workflow
    source = tmp_path / 'receipt.pdf'
    shutil.copyfile(FIXTURES / '2026-03-04_Walmart_Order_Meatballs_$80.59.pdf', source)
    state = create_initial_state(str(source))
    # Exercise real parsing with supplied synthetic text lacking a date.
    state['workflow_input'].raw_text = 'Walmart\nTotal: $80.59\n'
    augment = Mock(return_value=Receipt(vendor='Walmart', transaction_type='Order', date='2026-03-04', total=80.59))
    monkeypatch.setattr(importlib.import_module('workflows.langgraph.nodes.augment_node'),
                        'llm_extract_receipt', augment)
    result = build_graph().invoke(state)
    assert result['status'] == WorkflowStatus.COMPLETED
    assert result['scan_results'].missing_fields == ['date']
    assert result['augment_results'].filled_fields == {'date': 'llm_extraction'}
    assert result['augment_results'].still_missing == []
    augment.assert_called_once_with(state['workflow_input'].raw_text)
    ui.review_and_edit.assert_called_once()
    assert api.pages.create.call_args_list[0].kwargs['properties']['Date']['date']['start'] == '2026-03-04'


def test_unavailable_llm_falls_back_and_requires_acknowledgement(workflow, tmp_path, monkeypatch):
    from llm.receipt_extractor import llm_enrich_receipt

    api, ui = workflow
    source = tmp_path / 'receipt.pdf'
    shutil.copyfile(FIXTURES / '2026-03-04_Walmart_Order_Meatballs_$80.59.pdf', source)
    monkeypatch.setattr(Config, 'OPENAI_API_KEY', None)
    monkeypatch.setattr(importlib.import_module('workflows.langgraph.nodes.enrich_node'),
                        'llm_enrich_receipt', llm_enrich_receipt)
    result = build_graph().invoke(create_initial_state(str(source)))
    assert result['status'] == WorkflowStatus.COMPLETED
    assert result['receipt'].items == []
    assert result['enriched_receipt'].confidence_score == 0.5
    assert result['enriched_receipt'].merchant_category == 'grocery'
    assert 'low_enrichment_confidence' in result['acknowledged_warnings']
    ui.prompt_acknowledge_yellow.assert_called_once()
    assert api.pages.create.call_count == 2


def test_archive_failure_is_duplicate_on_full_graph_retry(workflow, tmp_path, monkeypatch):
    from services.file_organizer import FileOrganizer

    api, ui = workflow
    source = tmp_path / 'receipt.pdf'
    shutil.copyfile(FIXTURES / '2026-03-04_Walmart_Order_Meatballs_$80.59.pdf', source)
    archive = Mock(side_effect=OSError('synthetic disk failure'))
    monkeypatch.setattr(FileOrganizer, 'organize_file', archive)
    first = build_graph().invoke(create_initial_state(str(source)))
    assert first['status'] == WorkflowStatus.FAILED
    assert 'synthetic disk failure' in first['failure_reason']
    ui.reset_mock()
    again = build_graph().invoke(create_initial_state(str(source)))
    assert again['status'] == WorkflowStatus.DUPLICATE
    assert source.exists()
    ui.review_and_edit.assert_not_called()
    archive.assert_called_once()
    assert api.pages.create.call_count == 2


def test_duplicate_stops_before_pdf_parsing_or_review(workflow, tmp_path, monkeypatch):
    api, ui = workflow
    source = tmp_path / 'receipt.pdf'
    fixture = FIXTURES / '2026-03-04_Walmart_Order_Meatballs_$80.59.pdf'
    shutil.copyfile(fixture, source)
    first = build_graph().invoke(create_initial_state(str(source)))
    assert first['status'] == WorkflowStatus.COMPLETED
    duplicate = tmp_path / 'renamed.pdf'
    shutil.copyfile(fixture, duplicate)
    ui.reset_mock()
    parser = importlib.import_module('services.pdf_extractor').PDFExtractor
    extraction = Mock(side_effect=AssertionError('Duplicate must not be parsed'))
    monkeypatch.setattr(parser, 'extract_text', extraction)
    again = build_graph().invoke(create_initial_state(str(duplicate)))
    assert again['status'] == WorkflowStatus.DUPLICATE
    assert again['failure_reason'] is None
    extraction.assert_not_called()
    ui.review_and_edit.assert_not_called()
    assert api.pages.create.call_count == 2
    assert duplicate.exists()


def test_incomplete_submission_still_reaches_review(workflow, tmp_path):
    api, ui = workflow
    source = tmp_path / 'receipt.pdf'
    shutil.copyfile(FIXTURES / '2026-03-04_Walmart_Order_Meatballs_$80.59.pdf', source)
    # A linking failure leaves the expense and split created but incomplete.
    api.pages.update.side_effect = ValueError('synthetic linking failure')
    assert build_graph().invoke(create_initial_state(str(source)))['status'] == WorkflowStatus.FAILED
    api.pages.update.side_effect = None
    ui.reset_mock()
    result = build_graph().invoke(create_initial_state(str(source)))
    assert result['status'] == WorkflowStatus.COMPLETED
    ui.review_and_edit.assert_called_once()
    assert api.pages.create.call_count == 2


def test_moving_archived_receipt_back_to_input_still_skips(workflow, tmp_path, monkeypatch):
    api, ui = workflow
    source = tmp_path / 'receipt.pdf'
    shutil.copyfile(FIXTURES / '2026-03-04_Walmart_Order_Meatballs_$80.59.pdf', source)
    first = build_graph().invoke(create_initial_state(str(source)))
    assert first['status'] == WorkflowStatus.COMPLETED
    # Reproduce a user moving the processed receipt back for a duplicate test.
    first['results'].archive_path.rename(source)
    ui.reset_mock()
    parser = importlib.import_module('services.pdf_extractor').PDFExtractor
    extraction = Mock(side_effect=AssertionError('Already submitted PDF must not be parsed'))
    monkeypatch.setattr(parser, 'extract_text', extraction)
    again = build_graph().invoke(create_initial_state(str(source)))
    assert again['status'] == WorkflowStatus.DUPLICATE
    assert again['failure_reason'] is None
    extraction.assert_not_called()
    ui.review_and_edit.assert_not_called()
    assert api.pages.create.call_count == 2
    assert source.exists()
