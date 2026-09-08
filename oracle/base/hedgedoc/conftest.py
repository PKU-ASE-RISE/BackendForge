"""Shared transport safeguards for the released HedgeDoc base tests."""

import pytest
import requests


REQUEST_TIMEOUT = 30


@pytest.fixture(autouse=True)
def _bound_http_requests(monkeypatch):
    """Keep every black-box HTTP call finite without changing call semantics."""
    original_request = requests.sessions.Session.request

    def bounded_request(session, method, url, **kwargs):
        kwargs.setdefault("timeout", REQUEST_TIMEOUT)
        return original_request(session, method, url, **kwargs)

    monkeypatch.setattr(requests.sessions.Session, "request", bounded_request)
