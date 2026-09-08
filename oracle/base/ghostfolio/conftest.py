import uuid

import pytest


_IDENTITY_HEADERS = (
    ("USER1_ID", "USER1_HEADERS"),
    ("USER2_ID", "USER2_HEADERS"),
    ("USER_A_ID", "HEADERS_A"),
    ("USER_B_ID", "HEADERS_B"),
)


@pytest.fixture(autouse=True)
def isolate_default_users(request, monkeypatch):
    """Give each test fresh default users so state cannot leak between items."""
    module = request.module
    for identity_name, headers_name in _IDENTITY_HEADERS:
        if not hasattr(module, identity_name) or not hasattr(module, headers_name):
            continue

        user_id = str(uuid.uuid4())
        monkeypatch.setattr(module, identity_name, user_id)
        monkeypatch.setitem(getattr(module, headers_name), "X-User-Id", user_id)
