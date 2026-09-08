"""Shared pytest infrastructure for the released Hoppscotch base tests."""

import hashlib

import pytest
import requests


REQUEST_TIMEOUT = 30


@pytest.fixture(autouse=True)
def _isolate_state_and_bound_http(request, monkeypatch):
    """Use per-item principals and keep every black-box request finite."""
    suffix = hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:12]
    for index, name in enumerate(("USER1", "USER2", "USER3"), start=1):
        if hasattr(request.module, name):
            monkeypatch.setattr(request.module, name, f"user{index}_{suffix}")

    original_request = requests.sessions.Session.request

    def bounded_request(session, method, url, **kwargs):
        kwargs.setdefault("timeout", REQUEST_TIMEOUT)
        return original_request(session, method, url, **kwargs)

    monkeypatch.setattr(requests.sessions.Session, "request", bounded_request)
