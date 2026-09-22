"""Retry classification and timing without real delays or API calls."""
from unittest.mock import Mock
import sys
from pathlib import Path

import httpx
import pytest
from notion_client.errors import APIResponseError, RequestTimeoutError
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from services import notion_retry

pytestmark = pytest.mark.unit


def error(status, retry_after='0'):
    return APIResponseError(httpx.Response(status, headers={'Retry-After': retry_after}),
                            'synthetic failure', 'rate_limited')


@pytest.fixture
def sleeps(monkeypatch):
    sleep = Mock()
    monkeypatch.setattr(notion_retry.time, 'sleep', sleep)
    monkeypatch.setattr(notion_retry.random, 'uniform', lambda *_: 0)
    return sleep


@pytest.mark.parametrize('status', [429, 529])
def test_explicit_rejection_retries_and_respects_header(sleeps, status):
    call = Mock(side_effect=[error(status, '9'), 'page-id'])
    assert notion_retry.notion_request(call) == 'page-id'
    sleeps.assert_called_once_with(9)
    assert call.call_count == 2


def test_exhaustion_uses_bounded_exponential_backoff(sleeps):
    failure = error(429)
    call = Mock(side_effect=failure)
    with pytest.raises(APIResponseError) as caught:
        notion_retry.notion_request(call)
    assert caught.value is failure
    assert call.call_count == 4
    assert [c.args[0] for c in sleeps.call_args_list] == [1, 2, 4]


@pytest.mark.parametrize('failure', [error(400), error(401), error(403), error(500),
                                     error(503), RequestTimeoutError(), httpx.ReadTimeout('timeout')])
def test_create_does_not_retry_permanent_or_uncertain_failure(sleeps, failure):
    call = Mock(side_effect=failure)
    with pytest.raises(type(failure)):
        notion_retry.notion_request(call)
    call.assert_called_once()
    sleeps.assert_not_called()


@pytest.mark.parametrize('failure', [error(503), RequestTimeoutError(), httpx.ReadTimeout('timeout')])
def test_safe_operations_recover_from_transient_failure(sleeps, failure):
    call = Mock(side_effect=[failure, 'ok'])
    assert notion_retry.notion_request(call, safe_to_repeat=True) == 'ok'
    assert call.call_count == 2
