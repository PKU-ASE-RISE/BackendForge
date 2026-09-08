"""Mock notification delivery service for testing."""
from copy import deepcopy
from threading import RLock

from flask import Flask, request, jsonify

app = Flask(__name__)

# In-memory store of all sent messages
messages = []
next_message_number = 1
state_lock = RLock()


def request_object():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None
    return data


def destination(data, field):
    value = data.get(field, "")
    return value if isinstance(value, str) else None


def record_message(message):
    global next_message_number

    with state_lock:
        message_id = f"00000000-0000-4000-8000-{next_message_number:012x}"
        next_message_number += 1
        stored = {"messageId": message_id, **message}
        messages.append(stored)
    return message_id


@app.route("/v1/send/email", methods=["POST"])
def send_email():
    data = request_object()
    if data is None:
        return jsonify({"error": "JSON object required"}), 400
    to = destination(data, "to")
    if to is None:
        return jsonify({"error": "to must be a string"}), 400
    status = "failed" if "fail" in to.lower() else "sent"
    msg = {
        "channel": "email",
        "to": to,
        "subject": data.get("subject", ""),
        "body": data.get("body", ""),
        "from": data.get("from", ""),
        "status": status,
    }
    message_id = record_message(msg)
    return jsonify({"messageId": message_id, "status": status})


@app.route("/v1/send/sms", methods=["POST"])
def send_sms():
    data = request_object()
    if data is None:
        return jsonify({"error": "JSON object required"}), 400
    to = destination(data, "to")
    if to is None:
        return jsonify({"error": "to must be a string"}), 400
    status = "failed" if "fail" in to.lower() else "sent"
    msg = {
        "channel": "sms",
        "to": to,
        "body": data.get("body", ""),
        "from": data.get("from", ""),
        "status": status,
    }
    message_id = record_message(msg)
    return jsonify({"messageId": message_id, "status": status})


@app.route("/v1/send/push", methods=["POST"])
def send_push():
    data = request_object()
    if data is None:
        return jsonify({"error": "JSON object required"}), 400
    token = destination(data, "token")
    if token is None:
        return jsonify({"error": "token must be a string"}), 400
    status = "failed" if "fail" in token.lower() else "sent"
    msg = {
        "channel": "push",
        "token": token,
        "title": data.get("title", ""),
        "body": data.get("body", ""),
        "data": data.get("data", {}),
        "status": status,
    }
    message_id = record_message(msg)
    return jsonify({"messageId": message_id, "status": status})


@app.route("/v1/status/<message_id>", methods=["GET"])
def get_status(message_id):
    with state_lock:
        status = next(
            (msg["status"] for msg in messages if msg["messageId"] == message_id),
            None,
        )
    if status is not None:
        return jsonify({"messageId": message_id, "status": status})
    return jsonify({"error": "not found"}), 404


@app.route("/v1/logs", methods=["GET"])
def get_logs():
    with state_lock:
        snapshot = deepcopy(messages)
    return jsonify({"messages": snapshot})


@app.route("/v1/logs/clear", methods=["POST"])
def clear_logs():
    global next_message_number

    with state_lock:
        messages.clear()
        next_message_number = 1
    return jsonify({"message": "cleared"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9998, threaded=True, use_reloader=False)
