"""Mock Payment Gateway Service for Saleor benchmark task."""
import uuid
from flask import Flask, request, jsonify

app = Flask(__name__)

# In-memory storage
charges = {}
refunds = {}


@app.route("/v1/charges", methods=["POST"])
def create_charge():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    amount = data.get("amount")
    currency = data.get("currency", "USD")
    capture = data.get("capture", True)

    if amount is None:
        return jsonify({"error": "amount is required"}), 400
    if amount <= 0:
        return jsonify({"error": "amount must be positive"}), 400

    charge_id = f"ch_{uuid.uuid4().hex[:16]}"
    status = "succeeded" if capture else "authorized"

    charge = {
        "id": charge_id,
        "amount": amount,
        "currency": currency,
        "status": status,
        "captured": capture,
        "capturedAmount": amount if capture else 0,
        "refundedAmount": 0,
        "metadata": data.get("metadata", {}),
    }
    charges[charge_id] = charge
    return jsonify(charge), 201


@app.route("/v1/charges/<charge_id>", methods=["GET"])
def get_charge(charge_id):
    charge = charges.get(charge_id)
    if not charge:
        return jsonify({"error": "Charge not found"}), 404
    return jsonify(charge), 200


@app.route("/v1/captures", methods=["POST"])
def capture_charge():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    charge_id = data.get("chargeId")
    amount = data.get("amount")

    if not charge_id:
        return jsonify({"error": "chargeId is required"}), 400

    charge = charges.get(charge_id)
    if not charge:
        return jsonify({"error": "Charge not found"}), 404

    if charge["status"] not in ("authorized", "partially_captured"):
        return jsonify({"error": f"Charge is in '{charge['status']}' state, cannot capture"}), 400

    # If amount not specified, capture full amount
    capture_amount = amount if amount is not None else charge["amount"]

    if capture_amount <= 0:
        return jsonify({"error": "Capture amount must be positive"}), 400
    if capture_amount > charge["amount"] - charge["capturedAmount"]:
        return jsonify({"error": "Capture amount exceeds authorized amount"}), 400

    charge["capturedAmount"] += capture_amount
    if charge["capturedAmount"] >= charge["amount"]:
        charge["status"] = "succeeded"
        charge["captured"] = True
    else:
        charge["status"] = "partially_captured"

    capture_record = {
        "id": f"cap_{uuid.uuid4().hex[:16]}",
        "chargeId": charge_id,
        "amount": capture_amount,
        "status": "succeeded",
    }

    return jsonify(capture_record), 201


@app.route("/v1/refunds", methods=["POST"])
def create_refund():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    charge_id = data.get("chargeId")
    amount = data.get("amount")

    if not charge_id:
        return jsonify({"error": "chargeId is required"}), 400

    charge = charges.get(charge_id)
    if not charge:
        return jsonify({"error": "Charge not found"}), 404

    if charge["status"] not in ("succeeded", "partially_captured", "partially_refunded"):
        return jsonify({"error": f"Cannot refund charge in '{charge['status']}' state"}), 400

    # If amount not specified, refund full captured amount
    refund_amount = amount if amount is not None else charge["capturedAmount"] - charge["refundedAmount"]

    if refund_amount <= 0:
        return jsonify({"error": "Refund amount must be positive"}), 400

    max_refundable = charge["capturedAmount"] - charge["refundedAmount"]
    if refund_amount > max_refundable:
        return jsonify({"error": "Refund amount exceeds captured amount"}), 400

    charge["refundedAmount"] += refund_amount
    if charge["refundedAmount"] >= charge["capturedAmount"]:
        charge["status"] = "refunded"
    else:
        charge["status"] = "partially_refunded"

    refund_id = f"ref_{uuid.uuid4().hex[:16]}"
    refund_record = {
        "id": refund_id,
        "chargeId": charge_id,
        "amount": refund_amount,
        "status": "succeeded",
    }
    refunds[refund_id] = refund_record

    return jsonify(refund_record), 201


@app.route("/v1/refunds/<refund_id>", methods=["GET"])
def get_refund(refund_id):
    refund = refunds.get(refund_id)
    if not refund:
        return jsonify({"error": "Refund not found"}), 404
    return jsonify(refund), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9999)
