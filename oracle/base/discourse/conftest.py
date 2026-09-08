"""Pytest infrastructure shared by the released Discourse base tests."""

import math
import os

import pytest
import requests


def _request_timeout():
    value = os.environ.get("DISCOURSE_REQUEST_TIMEOUT", "10")
    try:
        timeout = float(value)
    except ValueError as exc:
        raise pytest.UsageError(
            "DISCOURSE_REQUEST_TIMEOUT must be a positive number"
        ) from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise pytest.UsageError(
            "DISCOURSE_REQUEST_TIMEOUT must be a positive number"
        )
    return (3.05, timeout)


@pytest.fixture(scope="session", autouse=True)
def _bounded_http_requests():
    """Keep a broken submission from hanging indefinitely on one request."""
    original_request = requests.sessions.Session.request
    timeout = _request_timeout()

    def request_with_timeout(session, method, url, **kwargs):
        kwargs.setdefault("timeout", timeout)
        return original_request(session, method, url, **kwargs)

    requests.sessions.Session.request = request_with_timeout
    try:
        yield
    finally:
        requests.sessions.Session.request = original_request
