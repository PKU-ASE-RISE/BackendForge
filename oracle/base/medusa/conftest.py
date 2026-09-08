"""Shared transport safeguards for the released Medusa base tests."""

import pytest
import requests


REQUEST_TIMEOUT = (3.05, 10)


@pytest.fixture(scope="session", autouse=True)
def _bounded_http_requests():
    """Keep a stalled submission from hanging an evaluator test group."""
    original_request = requests.sessions.Session.request

    def request_with_timeout(session, method, url, **kwargs):
        kwargs.setdefault("timeout", REQUEST_TIMEOUT)
        return original_request(session, method, url, **kwargs)

    requests.sessions.Session.request = request_with_timeout
    try:
        yield
    finally:
        requests.sessions.Session.request = original_request
