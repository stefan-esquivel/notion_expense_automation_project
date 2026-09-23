"""Bounded retries which never blindly replay an uncertain page creation."""
import math
import random
import time

import httpx
from notion_client.errors import HTTPResponseError, RequestTimeoutError

MAX_ATTEMPTS = 4


def definitely_rejected(error: Exception) -> bool:
    return isinstance(error, HTTPResponseError) and (
        error.status in (400, 401, 403, 404, 409, 422, 429, 529))


def notion_request(call, *, safe_to_repeat=False):
    for attempt in range(MAX_ATTEMPTS):
        try:
            return call()
        except (HTTPResponseError, RequestTimeoutError, httpx.TransportError) as error:
            status = getattr(error, 'status', None)
            retryable = status in (429, 529) or (
                safe_to_repeat and (status in (500, 502, 503, 504) or status is None))
            if not retryable or attempt == MAX_ATTEMPTS - 1:
                raise
            delay = 2 ** attempt
            retry_after = getattr(error, 'headers', {}).get('Retry-After')
            if retry_after:
                try:
                    seconds = float(retry_after)
                    if math.isfinite(seconds):
                        delay = max(delay, seconds)
                except ValueError:
                    pass
            time.sleep(delay + random.uniform(0, 0.25))
