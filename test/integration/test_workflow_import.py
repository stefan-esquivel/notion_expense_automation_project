"""Check dependency warnings in a fresh process before imports are cached."""
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.integration
def test_workflow_import_has_no_langchain_pending_deprecations():
    source = Path(__file__).resolve().parents[2] / 'src'
    code = f'''
import sys
import warnings
from langchain_core._api.deprecation import LangChainPendingDeprecationWarning
warnings.simplefilter('error', LangChainPendingDeprecationWarning)
sys.path.insert(0, {str(source)!r})
from workflows.langgraph.graph import build_graph
build_graph()
'''
    result = subprocess.run(
        [sys.executable, '-c', code], capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
