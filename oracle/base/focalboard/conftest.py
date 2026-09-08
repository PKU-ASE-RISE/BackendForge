import uuid

import pytest


_IDENTITY_HEADERS = (
    ("USER1_ID", "USER1_HEADERS"),
    ("USER2_ID", "USER2_HEADERS"),
    ("USER3_ID", "USER3_HEADERS"),
    ("USER1_ID", "H1"),
    ("USER2_ID", "H2"),
    ("USER3_ID", "H3"),
    ("USER4_ID", "H4"),
)


@pytest.fixture(autouse=True)
def isolate_test_users(request, monkeypatch):
    """Give every item fresh user namespaces so persisted state cannot leak."""
    module = request.module
    for identity_name, headers_name in _IDENTITY_HEADERS:
        if not hasattr(module, identity_name) or not hasattr(module, headers_name):
            continue
        user_id = str(uuid.uuid4())
        monkeypatch.setattr(module, identity_name, user_id)
        monkeypatch.setitem(getattr(module, headers_name), "X-User-Id", user_id)
