import pytest
import requests


HTTP_TIMEOUT = (2.0, 5.0)


@pytest.fixture(autouse=True)
def bounded_http_requests(monkeypatch):
    original_request = requests.sessions.Session.request

    def request_with_timeout(self, *args, **kwargs):
        kwargs.setdefault("timeout", HTTP_TIMEOUT)
        return original_request(self, *args, **kwargs)

    monkeypatch.setattr(requests.sessions.Session, "request", request_with_timeout)
