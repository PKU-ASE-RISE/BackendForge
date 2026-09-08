import os
import re
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
HEADERS = {
    "X-Api-Key": "direct-reference-prober",
    "Content-Type": "application/json",
}


def test_generated_short_codes_lowercase():
    generated_codes = []

    for _ in range(20):
        response = requests.post(
            f"{BASE_URL}/rest/v3/short-urls",
            headers=HEADERS,
            json={"longUrl": f"https://example.com/lowercase-probe/{uuid.uuid4().hex}"},
            timeout=30,
        )
        assert response.status_code == 200, response.text
        generated_codes.append(response.json()["shortCode"])

    invalid_codes = [
        code for code in generated_codes if not re.fullmatch(r"[a-z0-9]{5,8}", code)
    ]
    assert invalid_codes == [], f"Generated short codes must be lowercase: {invalid_codes}"
