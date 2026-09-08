"""Shared transport and state isolation for the released Novu base tests."""

from collections import defaultdict
from itertools import count
import os
from urllib.parse import quote, urlsplit
import uuid

import pytest
import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
API_HEADERS = {"X-API-Key": "test-api-key-1", "Content-Type": "application/json"}
REQUEST_TIMEOUT = 30
CLEANUP_TIMEOUT = 5
UUID_NAMESPACE = uuid.UUID("94bcfca7-6743-4c18-894f-5ebbe19eaf99")

RESOURCE_ROUTES = {
    "/v1/notification-groups": ("notification-groups", "id"),
    "/v1/environments": ("environments", "id"),
    "/v1/integrations": ("integrations", "id"),
    "/v1/workflows": ("workflows", "id"),
    "/v1/subscribers": ("subscribers", "subscriberId"),
    "/v1/topics": ("topics", "key"),
}
CLEANUP_ORDER = (
    "workflows",
    "integrations",
    "topics",
    "subscribers",
    "notification-groups",
    "environments",
)


def _relative_api_path(url):
    parsed = urlsplit(url)
    base = urlsplit(BASE_URL)
    if (parsed.scheme, parsed.netloc) != (base.scheme, base.netloc):
        return None

    base_path = base.path.rstrip("/")
    if base_path and not parsed.path.startswith(f"{base_path}/"):
        return None
    return parsed.path[len(base_path):] if base_path else parsed.path


@pytest.fixture(autouse=True)
def _isolate_state_and_bound_http(request, monkeypatch):
    """Bound HTTP, stabilize generated data, and remove per-item resources."""
    sequence = count()

    def deterministic_uuid4():
        return uuid.uuid5(UUID_NAMESPACE, f"{request.node.nodeid}:{next(sequence)}")

    monkeypatch.setattr(uuid, "uuid4", deterministic_uuid4)

    created = defaultdict(list)
    original_request = requests.sessions.Session.request

    def bounded_request(session, method, url, **kwargs):
        kwargs.setdefault("timeout", REQUEST_TIMEOUT)
        response = original_request(session, method, url, **kwargs)

        path = _relative_api_path(url)
        route = RESOURCE_ROUTES.get(path)
        if method.upper() == "POST" and 200 <= response.status_code < 300 and route:
            try:
                body = response.json()
            except requests.exceptions.JSONDecodeError:
                body = None
            resource, field = route
            identifier = body.get(field) if isinstance(body, dict) else None
            if isinstance(identifier, (str, int)) and not isinstance(identifier, bool):
                created[resource].append(str(identifier))
        return response

    monkeypatch.setattr(requests.sessions.Session, "request", bounded_request)
    yield

    cleanup_session = requests.Session()
    try:
        for resource in CLEANUP_ORDER:
            for identifier in reversed(dict.fromkeys(created[resource])):
                url = f"{BASE_URL}/v1/{resource}/{quote(identifier, safe='')}"
                try:
                    original_request(
                        cleanup_session,
                        "DELETE",
                        url,
                        headers=API_HEADERS,
                        timeout=CLEANUP_TIMEOUT,
                    )
                except requests.RequestException:
                    pass
    finally:
        cleanup_session.close()
