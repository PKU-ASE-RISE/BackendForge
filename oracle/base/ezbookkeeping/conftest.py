import uuid

import pytest


@pytest.fixture(autouse=True)
def isolate_default_users(request, monkeypatch):
    """Give each test fresh default identities without changing its HTTP scenario."""
    for header_name, id_name in (("HEADERS", "USER_ID"), ("HEADERS2", "USER2_ID")):
        headers = getattr(request.module, header_name, None)
        if headers is None:
            continue

        user_id = str(uuid.uuid4())
        monkeypatch.setattr(request.module, id_name, user_id)
        monkeypatch.setitem(headers, "X-User-Id", user_id)
