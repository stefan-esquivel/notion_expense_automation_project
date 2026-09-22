"""Failure boundaries in the compiled graph, independent of external services."""
import importlib
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from domain.enums import WorkflowStatus
from domain.models.workflow import ScanResults, ValidationResult

graph = importlib.import_module('workflows.langgraph.graph')
pytestmark = pytest.mark.unit


@pytest.mark.parametrize('failed_node', [
    'ingest', 'extract', 'scan', 'augment', 'enrich', 'validate', 'review', 'revalidate',
])
def test_failed_node_terminates_without_running_downstream(monkeypatch, failed_node):
    order = ['ingest', 'extract', 'scan', 'augment', 'enrich', 'validate', 'review', 'revalidate']
    visited = []

    def node(name):
        def run(state):
            # The same validation function is registered at both graph stages.
            stage = 'revalidate' if name == 'validate' and 'review' in visited else name
            visited.append(stage)
            if stage == failed_node:
                return {'status': WorkflowStatus.FAILED, 'failure_reason': f'{stage} failed'}
            return {'scan_results': ScanResults(has_missing_data=True, missing_fields=['date']),
                    'validation_result': ValidationResult()}
        return run

    for name in order[:-1]:
        monkeypatch.setattr(graph, f'{name}_node', node(name))
    commit = Mock(side_effect=AssertionError('Failed workflows cannot commit'))
    monkeypatch.setattr(graph, 'commit_node', commit)
    result = graph.build_graph().invoke(graph.create_initial_state('synthetic.pdf'))
    assert visited == order[:order.index(failed_node) + 1]
    assert result['status'] == WorkflowStatus.FAILED
    assert result['failure_reason'] == f'{failed_node} failed'
    commit.assert_not_called()
