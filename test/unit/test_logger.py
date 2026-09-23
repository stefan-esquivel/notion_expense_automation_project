"""Logging must work before configuration validation on a fresh checkout."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from logger import AppLogger, Config

pytestmark = pytest.mark.unit


def test_logger_creates_missing_directory_before_opening_file(monkeypatch, tmp_path):
    folder = tmp_path / 'fresh' / 'logs'
    monkeypatch.setattr(Config, 'LOG_FOLDER', folder)
    logger = AppLogger._setup_logger(f'fresh-checkout-{tmp_path.name}')
    try:
        logger.info('synthetic startup message')
        logs = list(folder.glob('expense_automation_*.log'))
        assert len(logs) == 1
        assert 'synthetic startup message' in logs[0].read_text()
    finally:
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)
