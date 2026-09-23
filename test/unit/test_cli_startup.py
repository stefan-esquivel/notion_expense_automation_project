"""Release checks for CLI startup gates and workflow result reporting."""
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
import main
from domain.enums import WorkflowStatus

pytestmark = pytest.mark.unit


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr(main, 'build_graph', Mock())
    monkeypatch.setattr(main, 'ExpenseUI', Mock())
    result = main.ExpenseAutomation()
    result.logger = Mock()
    return result


def test_invalid_configuration_stops_before_network_or_processing(app, monkeypatch):
    monkeypatch.setattr(main.Config, 'validate', Mock(side_effect=ValueError('missing token')))
    app._test_notion = Mock()
    app.scan_input_folder = Mock()
    app.run()
    app.ui.display_error.assert_called_once_with('Configuration error: missing token')
    app._test_notion.assert_not_called()
    app.scan_input_folder.assert_not_called()


def test_failed_connectivity_stops_before_processing(app, monkeypatch):
    monkeypatch.setattr(main.Config, 'validate', Mock())
    client = Mock()
    client.test_connection.return_value = False
    monkeypatch.setattr(main, 'NotionExpenseClient', Mock(return_value=client))
    app.scan_input_folder = Mock()
    app.run()
    client.test_connection.assert_called_once()
    app.ui.display_error.assert_called_once()
    app.scan_input_folder.assert_not_called()


def test_empty_input_does_not_invoke_workflow(app, monkeypatch, tmp_path):
    app._validate_config = Mock()
    app._test_notion = Mock(return_value=True)
    monkeypatch.setattr(main.Config, 'INPUT_FOLDER', tmp_path)
    app.run()
    app.workflow.invoke.assert_not_called()
    app.ui.display_error.assert_called_once_with(f'No PDF files found in {tmp_path}')


def test_scan_is_sorted_nonrecursive_and_pdf_only(app, monkeypatch, tmp_path):
    for name in ('z.pdf', 'a.pdf', 'notes.txt', 'UPPER.PDF'):
        (tmp_path / name).touch()
    (tmp_path / 'nested').mkdir()
    (tmp_path / 'nested' / 'receipt.pdf').touch()
    monkeypatch.setattr(main.Config, 'INPUT_FOLDER', tmp_path)
    assert app.scan_input_folder() == [tmp_path / 'a.pdf', tmp_path / 'z.pdf']


@pytest.mark.parametrize('result,success,message', [
    ({'status': WorkflowStatus.COMPLETED, 'results': Mock(archive_path='/archive/receipt.pdf', notion_expense_id='synthetic')}, True, '/archive/receipt.pdf'),
    ({'status': WorkflowStatus.COMPLETED}, False, 'Workflow completed but no results found'),
    ({'status': WorkflowStatus.FAILED, 'failure_reason': 'cancelled'}, False, 'Workflow failed: cancelled'),
])
def test_workflow_outcome_is_reported(app, result, success, message):
    app.workflow.invoke.return_value = result
    assert app.process_receipt(Path('receipt.pdf')) is success
    if success:
        app.ui.display_success.assert_called_once_with(message)
        app.ui.display_error.assert_not_called()
    else:
        app.ui.display_error.assert_called_once_with(message)
        app.ui.display_success.assert_not_called()


def test_workflow_exception_is_reported_as_failure(app):
    app.workflow.invoke.side_effect = RuntimeError('parse failed')
    assert app.process_receipt(Path('receipt.pdf')) is False
    app.ui.display_error.assert_called_once_with('parse failed')
    app.ui.display_success.assert_not_called()


def test_keyboard_interrupt_stops_batch(app):
    app._validate_config = Mock(side_effect=KeyboardInterrupt)
    app._test_notion = Mock()
    app.run()
    app._test_notion.assert_not_called()
    app.ui.display_error.assert_called_once_with('Application interrupted')


def test_entry_point_runs_application(monkeypatch):
    application = Mock()
    monkeypatch.setattr(main, 'ExpenseAutomation', Mock(return_value=application))
    main.main()
    application.run.assert_called_once()
