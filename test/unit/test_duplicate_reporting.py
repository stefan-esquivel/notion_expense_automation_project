"""An existing submission is a normal skip, not an error or new creation."""
import importlib
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from domain.enums import WorkflowStatus

pytestmark = pytest.mark.unit


def test_duplicate_is_reported_without_error(monkeypatch):
    main = importlib.import_module('main')
    ui = Mock()
    graph = Mock()
    graph.invoke.return_value = {'status': WorkflowStatus.DUPLICATE}
    monkeypatch.setattr(main, 'ExpenseUI', Mock(return_value=ui))
    monkeypatch.setattr(main, 'build_graph', Mock(return_value=graph))
    monkeypatch.setattr(main, 'create_initial_state', Mock(return_value={}))
    app = main.ExpenseAutomation()
    assert app.process_receipt(Path('duplicate.pdf')) is None
    ui.display_duplicate.assert_called_once()
    ui.display_error.assert_not_called()
    ui.display_success.assert_not_called()


def test_batch_summary_counts_duplicates_separately(monkeypatch):
    main = importlib.import_module('main')
    monkeypatch.setattr(main, 'ExpenseUI', Mock())
    monkeypatch.setattr(main, 'build_graph', Mock())
    app = main.ExpenseAutomation()
    app.logger = Mock()
    app._validate_config = Mock()
    app._test_notion = Mock(return_value=True)
    app.scan_input_folder = Mock(return_value=[Path('new.pdf'), Path('duplicate.pdf'), Path('bad.pdf')])
    app.process_receipt = Mock(side_effect=[True, None, False])
    app.run()
    app.logger.info.assert_any_call('Processed 1/3 receipts successfully; skipped 1 already-submitted receipts')
