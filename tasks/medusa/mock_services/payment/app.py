"""Mock Payment Service - Stripe-like payment gateway for testing."""
from copy import deepcopy
from itertools import count
from math import isfinite
from threading import RLock

from flask import Flask, request, jsonify

app = Flask(__name__)

# In-memory storage
charges = {}
refunds = {}
idempotency_cache = {}
charge_ids = count(1)
refund_ids = count(1)
state_lock = RLock()

CREATED_AT = "2024-01-01T00:00:00Z"


def now_iso():
    return CREATED_AT


def next_id(prefix, sequence):
    return f"{prefix}_{next(sequence):016x}"


def is_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and isfinite(value)
    )


@app.route("/v1/charges", methods=["POST"])
def create_charge():
    idempotency_key = request.headers.get("Idempotency-Key")
    if idempotency_key:
        with state_lock:
            cached_charge = idempotency_cache.get(idempotency_key)
            if cached_charge is not None:
                return jsonify(deepcopy(cached_charge)), 201

    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data:
        return jsonify({"error": "Request body required"}), 400

    amount = data.get("amount")
    currency = data.get("currency", "usd")
    description = data.get("description", "")
    metadata = data.get("metadata", {})

    if amount is None:
        return jsonify({"error": "amount is required"}), 400
    if not is_number(amount):
        return jsonify({"error": "amount must be numeric"}), 400

    status = "failed" if amount > 999999 else "succeeded"

    with state_lock:
        if idempotency_key and idempotency_key in idempotency_cache:
            return jsonify(deepcopy(idempotency_cache[idempotency_key])), 201

        charge = {
            "id": next_id("ch", charge_ids),
            "amount": amount,
            "currency": currency,
            "status": status,
            "description": description,
            "metadata": metadata,
            "createdAt": now_iso(),
        }
        charges[charge["id"]] = charge
        if idempotency_key:
            idempotency_cache[idempotency_key] = deepcopy(charge)

        return jsonify(deepcopy(charge)), 201


@app.route("/v1/charges/<charge_id>", methods=["GET"])
def get_charge(charge_id):
    with state_lock:
        charge = charges.get(charge_id)
        if not charge:
            return jsonify({"error": "Charge not found"}), 404
        return jsonify(deepcopy(charge)), 200


@app.route("/v1/refunds", methods=["POST"])
def create_refund():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data:
        return jsonify({"error": "Request body required"}), 400

    charge_id = data.get("chargeId")
    amount = data.get("amount")
    reason = data.get("reason", "")

    if not charge_id:
        return jsonify({"error": "chargeId is required"}), 400

    if amount is not None and not is_number(amount):
        return jsonify({"error": "amount must be numeric"}), 400

    with state_lock:
        charge = charges.get(charge_id)
        if not charge:
            return jsonify({"error": "Charge not found"}), 404

        if charge["status"] != "succeeded":
            return jsonify({"error": "Charge must have status succeeded to refund"}), 422

        if amount is None:
            amount = charge["amount"]

        if amount > charge["amount"]:
            return jsonify({"error": "Refund amount exceeds charge amount"}), 422

        refund = {
            "id": next_id("re", refund_ids),
            "chargeId": charge_id,
            "amount": amount,
            "reason": reason,
            "status": "succeeded",
            "createdAt": now_iso(),
        }
        refunds[refund["id"]] = refund
        charge["status"] = "refunded"

        return jsonify(deepcopy(refund)), 201


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9999, threaded=True, use_reloader=False)
