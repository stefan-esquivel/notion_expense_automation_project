"""Unit tests for the OpenAI receipt client."""

import os
import sys
from unittest.mock import Mock, patch

import httpx
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from llm.client import APIConnectionError, APIStatusError, ReceiptLLMClient


@pytest.fixture
def llm_client():
    with patch('llm.client.OpenAI'):
        return ReceiptLLMClient(api_key='test-key')


def test_call_llm_retries_transient_connection_error(llm_client):
    successful_response = Mock()
    successful_response.choices = [Mock(message=Mock(content='{"items": []}'))]
    llm_client.client.chat.completions.create.side_effect = [
        APIConnectionError(request=httpx.Request('POST', 'https://api.openai.com')),
        successful_response,
    ]

    with patch('llm.client.time.sleep') as mock_sleep:
        result = llm_client._call_llm('system', 'user')

    assert result == '{"items": []}'
    assert llm_client.client.chat.completions.create.call_count == 2
    mock_sleep.assert_called_once_with(1)


def test_call_llm_retries_server_error(llm_client):
    server_error = APIStatusError(
        'Server error',
        response=httpx.Response(500, request=httpx.Request('POST', 'https://api.openai.com')),
        body=None,
    )
    successful_response = Mock()
    successful_response.choices = [Mock(message=Mock(content='success'))]
    llm_client.client.chat.completions.create.side_effect = [server_error, successful_response]

    with patch('llm.client.time.sleep') as mock_sleep:
        result = llm_client._call_llm('system', 'user')

    assert result == 'success'
    assert llm_client.client.chat.completions.create.call_count == 2
    mock_sleep.assert_called_once_with(1)


def test_call_llm_does_not_retry_client_error(llm_client):
    client_error = APIStatusError(
        'Unauthorized',
        response=httpx.Response(401, request=httpx.Request('POST', 'https://api.openai.com')),
        body=None,
    )
    llm_client.client.chat.completions.create.side_effect = client_error

    with patch('llm.client.time.sleep') as mock_sleep:
        with pytest.raises(APIStatusError):
            llm_client._call_llm('system', 'user')

    assert llm_client.client.chat.completions.create.call_count == 1
    mock_sleep.assert_not_called()


def test_call_llm_stops_after_three_attempts(llm_client):
    connection_error = APIConnectionError(request=httpx.Request('POST', 'https://api.openai.com'))
    llm_client.client.chat.completions.create.side_effect = connection_error

    with patch('llm.client.time.sleep') as mock_sleep:
        with pytest.raises(APIConnectionError):
            llm_client._call_llm('system', 'user')

    assert llm_client.client.chat.completions.create.call_count == 3
    assert mock_sleep.call_args_list == [((1,),), ((2,),)]
