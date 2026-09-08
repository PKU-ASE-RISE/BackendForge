"""
Mock External Calendar Service
Simulates an external calendar (like Google Calendar) for the Cal.com scheduling platform.
Runs on port 9998.
"""

from flask import Flask, request, jsonify
import uuid
from datetime import datetime

app = Flask(__name__)

# In-memory storage
calendars = {}  # {calendarId: {id, name, events: {eventId: {id, start, end, title}}}}


@app.route("/v1/calendars", methods=["POST"])
def create_calendar():
    data = request.get_json() or {}
    name = data.get("name", "Untitled Calendar")
    calendar_id = str(uuid.uuid4())
    calendars[calendar_id] = {
        "id": calendar_id,
        "name": name,
        "events": {}
    }
    return jsonify({"calendarId": calendar_id, "name": name}), 201


@app.route("/v1/calendars/<calendar_id>/events", methods=["GET"])
def get_events(calendar_id):
    if calendar_id not in calendars:
        return jsonify({"error": "Calendar not found"}), 404

    start_param = request.args.get("start")
    end_param = request.args.get("end")

    if not start_param or not end_param:
        return jsonify({"error": "start and end query params required"}), 400

    try:
        start_dt = datetime.fromisoformat(start_param.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_param.replace("Z", "+00:00"))
    except ValueError:
        return jsonify({"error": "Invalid date format"}), 400

    events = []
    for event in calendars[calendar_id]["events"].values():
        event_start = datetime.fromisoformat(event["start"].replace("Z", "+00:00"))
        event_end = datetime.fromisoformat(event["end"].replace("Z", "+00:00"))
        # Include events that overlap with the requested range
        if event_start < end_dt and event_end > start_dt:
            events.append({
                "id": event["id"],
                "start": event["start"],
                "end": event["end"],
                "title": event["title"]
            })

    return jsonify({"events": events}), 200


@app.route("/v1/calendars/<calendar_id>/events", methods=["POST"])
def create_event(calendar_id):
    if calendar_id not in calendars:
        return jsonify({"error": "Calendar not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    start = data.get("start")
    end = data.get("end")
    title = data.get("title", "Untitled Event")

    if not start or not end:
        return jsonify({"error": "start and end are required"}), 400

    event_id = str(uuid.uuid4())
    event = {
        "id": event_id,
        "start": start,
        "end": end,
        "title": title
    }
    calendars[calendar_id]["events"][event_id] = event

    return jsonify(event), 201


@app.route("/v1/calendars/<calendar_id>/events/<event_id>", methods=["DELETE"])
def delete_event(calendar_id, event_id):
    if calendar_id not in calendars:
        return jsonify({"error": "Calendar not found"}), 404

    if event_id not in calendars[calendar_id]["events"]:
        return jsonify({"error": "Event not found"}), 404

    del calendars[calendar_id]["events"][event_id]
    return "", 204


@app.route("/webhooks", methods=["POST"])
def receive_webhook():
    """Deterministic local sink for webhook delivery tests."""
    request.get_json(silent=True)
    return "", 204


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9998)
