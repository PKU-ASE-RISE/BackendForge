"""Mock Payment Gateway for Spree benchmark task."""
import uuid
from flask import Flask, jsonify, request

app = Flask(__name__)

# In-memory storage for transactions
transactions = {}


@app.route("/v1/authorize", methods=["POST"])
def authorize():
    data = request.get_json() or {}
    amount = data.get("amount")
    currency = data.get("currency", "USD")

    if amount is None or amount <= 0:
        return jsonify({"error": "Invalid amount", "success": False}), 400

    transaction_id = str(uuid.uuid4())
    authorization_code = f"auth_{uuid.uuid4().hex[:12]}"

    transactions[transaction_id] = {
        "id": transaction_id,
        "type": "authorization",
        "amount": amount,
        "currency": currency,
        "status": "authorized",
        "authorizationCode": authorization_code,
    }

    return jsonify({
        "success": True,
        "transactionId": transaction_id,
        "authorizationCode": authorization_code,
        "amount": amount,
        "currency": currency,
        "status": "authorized",
    }), 200


@app.route("/v1/capture", methods=["POST"])
def capture():
    data = request.get_json() or {}
    transaction_id = data.get("transactionId")
    amount = data.get("amount")

    if not transaction_id or transaction_id not in transactions:
        return jsonify({"error": "Transaction not found", "success": False}), 404

    txn = transactions[transaction_id]
    if txn["status"] != "authorized":
        return jsonify({"error": f"Cannot capture transaction in state: {txn['status']}", "success": False}), 422

    capture_amount = amount if amount else txn["amount"]
    if capture_amount > txn["amount"]:
        return jsonify({"error": "Capture amount exceeds authorized amount", "success": False}), 422

    txn["status"] = "captured"
    txn["capturedAmount"] = capture_amount

    return jsonify({
        "success": True,
        "transactionId": transaction_id,
        "amount": capture_amount,
        "status": "captured",
    }), 200


@app.route("/v1/void", methods=["POST"])
def void():
    data = request.get_json() or {}
    transaction_id = data.get("transactionId")

    if not transaction_id or transaction_id not in transactions:
        return jsonify({"error": "Transaction not found", "success": False}), 404

    txn = transactions[transaction_id]
    if txn["status"] != "authorized":
        return jsonify({"error": f"Cannot void transaction in state: {txn['status']}", "success": False}), 422

    txn["status"] = "voided"

    return jsonify({
        "success": True,
        "transactionId": transaction_id,
        "status": "voided",
    }), 200


@app.route("/v1/credit", methods=["POST"])
def credit():
    data = request.get_json() or {}
    transaction_id = data.get("transactionId")
    amount = data.get("amount")

    if not transaction_id or transaction_id not in transactions:
        return jsonify({"error": "Transaction not found", "success": False}), 404

    txn = transactions[transaction_id]
    if txn["status"] != "captured":
        return jsonify({"error": f"Cannot credit transaction in state: {txn['status']}", "success": False}), 422

    credit_amount = amount if amount else txn.get("capturedAmount", txn["amount"])
    if credit_amount > txn.get("capturedAmount", txn["amount"]):
        return jsonify({"error": "Credit amount exceeds captured amount", "success": False}), 422

    txn["status"] = "refunded"
    txn["refundedAmount"] = credit_amount

    return jsonify({
        "success": True,
        "transactionId": transaction_id,
        "amount": credit_amount,
        "status": "refunded",
    }), 200


@app.route("/v1/transactions/<transaction_id>", methods=["GET"])
def get_transaction(transaction_id):
    if transaction_id not in transactions:
        return jsonify({"error": "Transaction not found"}), 404

    return jsonify(transactions[transaction_id]), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9999)
