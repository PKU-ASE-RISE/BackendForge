import uuid

import pytest


@pytest.fixture(autouse=True)
def isolate_default_users(request, monkeypatch):
    """Give every test fresh default identities without changing its HTTP surface."""
    header_id_pairs = (
        ("HEADERS", "USER_ID"),
        ("USER2_HEADERS", "USER2_ID"),
        ("HEADERS_USER2", "USER2_ID"),
    )
    for header_name, id_name in header_id_pairs:
        headers = getattr(request.module, header_name, None)
        if headers is not None:
            user_id = str(uuid.uuid4())
            monkeypatch.setattr(request.module, id_name, user_id)
            monkeypatch.setitem(headers, "X-User-Id", user_id)
