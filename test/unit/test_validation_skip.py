"""Regression coverage for declining receipt validation without stalling a batch."""

import importlib
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from domain.enums import ValidationSeverity, WorkflowStatus
from domain.models.recipts import Receipt
from domain.models.workflow import ValidationIssue, ValidationResult
from services.ui import ExpenseUI, OVERRIDE_SENTINEL, SKIP_SENTINEL
from workflows.langgraph.nodes.review_node import _resolve_issues, review_node

ui_module = importlib.import_module("services.ui")
review_module = importlib.import_module("workflows.langgraph.nodes.review_node")
graph_module = importlib.import_module("workflows.langgraph.graph")


@pytest.fixture
def ui():
    return ExpenseUI("Alex", "Sam")


@pytest.fixture
def receipt():
    return Receipt(vendor="Shop", transaction_type="Order", date="2020-01-01", total=1200)


def issue(field="date", severity=ValidationSeverity.RED):
    return ValidationIssue(field=field, severity=severity, key=f"{severity.value}_{field}", message=f"Check {field}")


def state_for(receipt, problem):
    return {"receipt": receipt, "validation_result": ValidationResult(issues=[problem]),
            "acknowledged_warnings": set(), "failure_reason": None}


@pytest.mark.parametrize("field,value,confirmed,expected", [
    ("date", "2020-01-01", False, SKIP_SENTINEL),
    ("date", "2020-01-01", True, OVERRIDE_SENTINEL),
    ("date", "2026-09-21", False, "2026-09-21"),
    ("vendor", "Shop", False, SKIP_SENTINEL),
    ("vendor", " Shop ", False, SKIP_SENTINEL),
    ("vendor", "Other shop", False, "Other shop"),
    ("total", "$1,200.00", False, SKIP_SENTINEL),
    ("total", "1200", False, SKIP_SENTINEL),
    ("total", "12.50", False, "12.50"),
    ("total", "invalid", False, "invalid"),
])
@pytest.mark.unit
def test_red_prompt_outcomes(ui, receipt, monkeypatch, field, value, confirmed, expected):
    monkeypatch.setattr(ui_module.Prompt, "ask", Mock(return_value=value))
    monkeypatch.setattr(ui_module.Confirm, "ask", Mock(return_value=confirmed))
    assert ui.prompt_fix_red_issue(issue(field), receipt) == expected


@pytest.mark.parametrize("field", ["date", "vendor", "total"])
@pytest.mark.unit
def test_red_prompt_cancellation(ui, receipt, monkeypatch, field):
    monkeypatch.setattr(ui_module.Prompt, "ask", Mock(side_effect=KeyboardInterrupt))
    assert ui.prompt_fix_red_issue(issue(field), receipt) is None


@pytest.mark.unit
def test_date_override_cancellation(ui, receipt, monkeypatch):
    monkeypatch.setattr(ui_module.Prompt, "ask", Mock(return_value=receipt.date))
    monkeypatch.setattr(ui_module.Confirm, "ask", Mock(side_effect=KeyboardInterrupt))
    assert ui.prompt_fix_red_issue(issue(), receipt) is None


@pytest.mark.parametrize("severity,field", [(ValidationSeverity.YELLOW, "total"),
    (ValidationSeverity.RED, "date"), (ValidationSeverity.RED, "vendor"), (ValidationSeverity.RED, "total")])
@pytest.mark.unit
def test_review_skip_stops_before_other_prompts(ui, receipt, monkeypatch, severity, field):
    problem = issue(field, severity)
    state = state_for(receipt, problem)
    state["validation_result"].issues.append(issue("vendor", ValidationSeverity.YELLOW))
    monkeypatch.setattr(review_module, "ExpenseUI", Mock(return_value=ui))
    monkeypatch.setattr(ui_module.Prompt, "ask", Mock(side_effect=lambda *a, **kw: kw["default"]))
    confirm = Mock(return_value=False)
    monkeypatch.setattr(ui_module.Confirm, "ask", confirm)
    console = Console(record=True, width=160)
    monkeypatch.setattr(ui_module, "console", console)
    for method in ("review_and_edit", "select_payer", "confirm_split", "display_final_preview", "confirm_send_to_notion"):
        monkeypatch.setattr(ui, method, Mock(side_effect=AssertionError("Unexpected later prompt")))
    result = review_node(state)
    assert result["status"] == WorkflowStatus.FAILED
    assert problem.key not in result["acknowledged_warnings"]
    assert severity.name in result["failure_reason"]
    assert problem.message in result["failure_reason"]
    assert "skipping this file" in result["failure_reason"]
    output = console.export_text()
    assert "skipping this file" in output and problem.message in output
    assert confirm.call_count == (1 if field == "date" or severity == ValidationSeverity.YELLOW else 0)


@pytest.mark.unit
def test_invalid_total_retries_then_applies_correction(ui, receipt, monkeypatch):
    state = state_for(receipt, issue("total"))
    prompt = Mock(side_effect=["invalid", "12.50"])
    monkeypatch.setattr(ui_module.Prompt, "ask", prompt)
    assert _resolve_issues(state, ui)
    assert receipt.total == 12.50
    assert prompt.call_count == 2


@pytest.mark.parametrize("severity", [ValidationSeverity.RED, ValidationSeverity.YELLOW])
@pytest.mark.unit
def test_accepted_override_or_warning_is_green(ui, receipt, monkeypatch, severity):
    problem = issue("date", severity)
    state = state_for(receipt, problem)
    monkeypatch.setattr(ui_module.Prompt, "ask", Mock(return_value=receipt.date))
    monkeypatch.setattr(ui_module.Confirm, "ask", Mock(return_value=True))
    assert _resolve_issues(state, ui)
    assert state["validation_result"].is_green(state["acknowledged_warnings"])


@pytest.mark.parametrize("severity", [ValidationSeverity.RED, ValidationSeverity.YELLOW])
@pytest.mark.unit
def test_review_cancellation_keeps_existing_reason(ui, receipt, monkeypatch, severity):
    monkeypatch.setattr(review_module, "ExpenseUI", Mock(return_value=ui))
    monkeypatch.setattr(ui_module.Prompt, "ask", Mock(side_effect=KeyboardInterrupt))
    monkeypatch.setattr(ui_module.Confirm, "ask", Mock(side_effect=KeyboardInterrupt))
    result = review_node(state_for(receipt, issue(severity=severity)))
    assert result["status"] == WorkflowStatus.FAILED
    assert result["failure_reason"] == "Review cancelled by user"


@pytest.mark.parametrize("severity", [ValidationSeverity.RED, ValidationSeverity.YELLOW])
@pytest.mark.integration
def test_graph_skip_then_batch_processes_next_file(ui, receipt, monkeypatch, tmp_path, severity):
    main_module = importlib.import_module("main")
    first, second = tmp_path / "first.pdf", tmp_path / "second.pdf"
    first.write_bytes(b"first receipt")
    second.write_bytes(b"second receipt")
    problem = issue(severity=severity)
    states = {str(first): state_for(receipt, problem), str(second): state_for(receipt.model_copy(), problem)}
    states[str(second)]["validation_result"] = ValidationResult(issues=[])
    for name in ("ingest_node", "extract_node", "scan_node", "augment_node", "enrich_node"):
        monkeypatch.setattr(graph_module, name, lambda state: state)
    validate = Mock(side_effect=lambda state: state)
    monkeypatch.setattr(graph_module, "validate_node", validate)
    commit = Mock(side_effect=lambda state: {**state, "status": WorkflowStatus.COMPLETED,
        "results": SimpleNamespace(archive_path="archived.pdf", notion_expense_id="mock-id")})
    monkeypatch.setattr(graph_module, "commit_node", commit)
    monkeypatch.setattr(review_module, "ExpenseUI", Mock(return_value=ui))
    monkeypatch.setattr(ui_module.Prompt, "ask", Mock(return_value=receipt.date))
    monkeypatch.setattr(ui_module.Confirm, "ask", Mock(return_value=False))
    monkeypatch.setattr(ui, "review_and_edit", Mock(return_value={"description": "Shop", "amount": 1200, "date": datetime(2020, 1, 1)}))
    monkeypatch.setattr(ui, "select_payer", Mock(return_value="Alex"))
    monkeypatch.setattr(ui, "confirm_split", Mock(return_value=(False, 50)))
    monkeypatch.setattr(ui, "confirm_send_to_notion", Mock(return_value=True))
    monkeypatch.setattr(main_module, "create_initial_state", Mock(side_effect=lambda path: states[path]))
    app = main_module.ExpenseAutomation()
    monkeypatch.setattr(app, "_validate_config", Mock())
    monkeypatch.setattr(app, "_test_notion", Mock(return_value=True))
    monkeypatch.setattr(app, "scan_input_folder", Mock(return_value=[first, second]))
    app.run()
    assert main_module.create_initial_state.call_count == 2
    # First receipt validates once; second validates before and after review.
    assert validate.call_count == 3
    assert commit.call_count == 1
    assert commit.call_args.args[0]["validation_result"].issues == []
    assert commit.call_args.args[0]["receipt"] == states[str(second)]["receipt"]
    ui.confirm_send_to_notion.assert_called_once()
    assert first.read_bytes() == b"first receipt"
