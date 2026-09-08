import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def headers(token):
    return {"X-Store-Token": token, "Content-Type": "application/json"}


def create_variant(store):
    admin = f"admin_{store}_admin"
    product = requests.post(
        f"{BASE_URL}/api/v1/products",
        headers=headers(admin),
        json={"name": f"WishOwner-{uuid.uuid4().hex}", "price": 9.0, "currency": "USD"},
        timeout=10,
    ).json()
    variant = requests.post(
        f"{BASE_URL}/api/v1/products/{product['id']}/variants",
        headers=headers(admin),
        json={"sku": f"WISH-{uuid.uuid4().hex}", "price": 9.0, "currency": "USD"},
        timeout=10,
    )
    assert variant.status_code == 201
    return variant.json()


def test_remove_wishlist_item_requires_owner():
    store = f"r1wlown{uuid.uuid4().hex[:12]}"
    owner = f"{store}_customer1"
    other = f"{store}_customer2"
    variant = create_variant(store)
    wishlist = requests.post(
        f"{BASE_URL}/api/v1/wishlists",
        headers=headers(owner),
        json={"name": f"Favorites-{uuid.uuid4().hex}"},
        timeout=10,
    ).json()
    item_response = requests.post(
        f"{BASE_URL}/api/v1/wishlists/{wishlist['id']}/items",
        headers=headers(owner),
        json={"variantId": variant["id"]},
        timeout=10,
    )
    assert item_response.status_code == 201
    item_id = item_response.json()["id"]

    response = requests.delete(
        f"{BASE_URL}/api/v1/wishlists/{wishlist['id']}/items/{item_id}",
        headers=headers(other),
        timeout=10,
    )

    assert response.status_code in (403, 404)
    wishlist_after = requests.get(f"{BASE_URL}/api/v1/wishlists/{wishlist['id']}", headers=headers(owner), timeout=10).json()
    assert any(item["id"] == item_id for item in wishlist_after["items"])
