"""Real review/validation/commit flow with interactive and external I/O mocked."""

import importlib
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from config import Config
from domain.enums import WorkflowStatus
from domain.models.recipts import Receipt
from services.ui import ExpenseUI, OVERRIDE_SENTINEL


graph_module = importlib.import_module("workflows.langgraph.graph")
review_module = importlib.import_module("workflows.langgraph.nodes.review_node")
validate_module = importlib.import_module("workflows.langgraph.nodes.validate_node")
notion_module = importlib.import_module("services.notion_api")
pytestmark = pytest.mark.integration


@pytest.fixture
def workflow(monkeypatch, tmp_path):
    # Start with an extracted receipt; run the real validation, review and commit nodes.
    for name in ("ingest_node", "extract_node", "scan_node", "augment_node", "enrich_node"):
        monkeypatch.setattr(graph_module, name, lambda state: state)
    monkeypatch.setattr(Config, "SUBMISSION_JOURNAL_PATH", tmp_path / "journal.sqlite3")
    for name, value in {"YOUR_NAME": "Alex", "PARTNER_NAME": "Sam",
                        "YOUR_USER_ID": "a" * 32, "PARTNER_USER_ID": "b" * 32,
                        "NOTION_API_TOKEN": "synthetic-test-token",
                        "EXPENSE_TABLE_DATABASE_ID": "c" * 32,
                        "SPLIT_DETAILS_DATABASE_ID": "d" * 32,
                        "BALANCES_PAGE_ID": "e" * 32, "QA_SKIP_COMMIT": False}.items():
        monkeypatch.setattr(Config, name, value)
    monkeypatch.setattr(Config, "validate", Mock())
    api = Mock()
    api.pages.create.side_effect = [{"id": "1" * 32}, {"id": "2" * 32}]
    api.pages.retrieve.return_value = {"properties": {Config.EXPENSE_RELATION_PROPERTY: {"relation": []}}}
    monkeypatch.setattr(notion_module, "Client", Mock(return_value=api))
    ui = Mock(spec=ExpenseUI)
    ui.review_and_edit.side_effect = lambda info: info
    ui.select_payer.return_value = "Alex"
    ui.confirm_split.return_value = (True, 50)
    ui.confirm_send_to_notion.return_value = True
    ui.prompt_acknowledge_yellow.return_value = True
    monkeypatch.setattr(review_module, "ExpenseUI", Mock(return_value=ui))
    receipt = Receipt(vendor="Shop", transaction_type="Order", date="2020-01-01", total=12)
    state = {"receipt": receipt, "status": WorkflowStatus.PENDING,
             "acknowledged_warnings": set(), "failure_reason": None}
    return state, ui, api


def test_post_review_validation_failure_never_commits(workflow, monkeypatch):
    state, ui, api = workflow
    checker = validate_module._check_amount
    calls = 0

    def fail_on_revalidation(amount):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("synthetic revalidation failure")
        return checker(amount)

    monkeypatch.setattr(validate_module, "_check_amount", fail_on_revalidation)
    result = graph_module.build_graph().invoke(state)
    assert result["status"] == WorkflowStatus.FAILED
    assert "synthetic revalidation failure" in result["failure_reason"]
    api.pages.create.assert_not_called()


@pytest.mark.parametrize("vendor", ["Unknown", "Unknown Merchant"])
def test_unknown_merchant_correction_reaches_notion_payloads(workflow, vendor):
    state, ui, api = workflow
    state["receipt"].vendor = vendor
    ui.review_and_edit.side_effect = lambda info: {**info, "description": "Corner Shop",
                                                 "amount": 15, "date": datetime(2020, 2, 2)}
    result = graph_module.build_graph().invoke(state)
    assert result["status"] == WorkflowStatus.COMPLETED
    assert result["receipt"].vendor == "Corner Shop"
    assert result["validation_result"].issues == []
    expense, split = [call.kwargs["properties"] for call in api.pages.create.call_args_list]
    assert expense["Merchant / Description"]["title"][0]["text"]["content"] == "Corner Shop"
    assert split["Title"]["title"][0]["text"]["content"] == "Sam's Corner Shop Split"
    assert expense["Amount"]["number"] == 15
    assert expense["Date"]["date"]["start"] == "2020-02-02"


def test_invalid_edit_returns_to_review_before_commit(workflow):
    state, ui, api = workflow
    future = datetime.now() + timedelta(days=30)
    ui.review_and_edit.side_effect = [
        {"description": "Shop", "amount": 12, "date": future},
        {"description": "Shop", "amount": 12, "date": datetime(2020, 1, 2)},
    ]

    def correct_date(issue, receipt):
        api.pages.create.assert_not_called()
        assert issue.key == "future_date"
        return "2020-01-02"

    ui.prompt_fix_red_issue.side_effect = correct_date
    result = graph_module.build_graph().invoke(state)
    assert result["status"] == WorkflowStatus.COMPLETED
    assert result["validation_result"].issues == []
    assert ui.review_and_edit.call_count == 2
    ui.select_payer.assert_called_once()
    ui.confirm_split.assert_called_once()
    assert api.pages.create.call_count == 2
    expense = api.pages.create.call_args_list[0].kwargs["properties"]
    assert expense["Date"]["date"]["start"] == "2020-01-02"


@pytest.mark.parametrize("kind", ["warning", "override"])
def test_acknowledged_issue_allows_commit(workflow, kind):
    state, ui, api = workflow
    if kind == "warning":
        state["receipt"].total = 20000
        key = "high_amount"
    else:
        state["receipt"].date = (datetime.now() + timedelta(days=30)).isoformat()
        ui.prompt_fix_red_issue.return_value = OVERRIDE_SENTINEL
        key = "future_date"
    result = graph_module.build_graph().invoke(state)
    assert result["status"] == WorkflowStatus.COMPLETED
    assert key in result["acknowledged_warnings"]
    assert result["validation_result"].is_green(result["acknowledged_warnings"])
    assert api.pages.create.call_count == 2


@pytest.mark.parametrize("action", ["cancel", "decline", "reject_warning"])
def test_rejected_review_never_commits(workflow, action):
    state, ui, api = workflow
    if action == "cancel":
        ui.review_and_edit.side_effect = KeyboardInterrupt
    elif action == "decline":
        ui.confirm_send_to_notion.return_value = False
    else:
        state["receipt"].total = 20000
        ui.prompt_acknowledge_yellow.return_value = False
    result = graph_module.build_graph().invoke(state)
    assert result["status"] == WorkflowStatus.FAILED
    api.pages.create.assert_not_called()


@pytest.mark.parametrize("explained", [True, False])
def test_low_confidence_advisory_is_reviewed_before_commit(workflow, monkeypatch, explained):
    from domain.models.enrichment import EnrichedReceipt

    state, ui, api = workflow
    state["enriched_receipt"] = EnrichedReceipt(merchant_category="other", confidence_score=0.4)
    client = Mock()
    client.suspicious_confidence_check.return_value = (
        {"suspicious_reasons": ["ambiguous merchant category"], "summary": "Verify merchant category"}
        if explained else {"suspicious_reasons": [], "summary": "No specific issues detected"}
    )
    monkeypatch.setattr("llm.receipt_extractor.ReceiptLLMClient", Mock(return_value=client))
    key = "suspicious_confidence" if explained else "low_enrichment_confidence"

    def acknowledge(issue):
        api.pages.create.assert_not_called()
        assert issue.key == key
        return True

    ui.prompt_acknowledge_yellow.side_effect = acknowledge
    result = graph_module.build_graph().invoke(state)
    assert result["status"] == WorkflowStatus.COMPLETED
    assert [i.key for i in result["validation_result"].issues] == [key]
    assert key in result["acknowledged_warnings"]
    ui.prompt_acknowledge_yellow.assert_called_once()
    assert client.suspicious_confidence_check.call_count == 2
    assert client.suspicious_confidence_check.call_args.kwargs["confidence_score"] == 0.4
    assert api.pages.create.call_count == 2


@pytest.mark.parametrize('description,expected', [
    ('Amazon Order (Baking Sheets)', "Sam's Amazon Order Split (Baking Sheets)"),
    ('Walmart (Groceries)', "Sam's Walmart Food Split (Groceries)"),
    ('Netflix', "Sam's Netflix Payment (Jan)"),
])
def test_shared_titles_reach_preview_and_notion(workflow, description, expected):
    state, ui, api = workflow
    ui.review_and_edit.side_effect = lambda info: {**info, 'description': description}
    result = graph_module.build_graph().invoke(state)
    assert result['status'] == WorkflowStatus.COMPLETED
    assert result['expense_summary'].splits[0].title == expected
    assert api.pages.create.call_args_list[1].kwargs['properties']['Title']['title'][0]['text']['content'] == expected
