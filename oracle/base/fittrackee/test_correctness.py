"""
BackendForge - Comprehensive Correctness Tests for FitTrackee Task

Tests focus on: statistics computation, record auto-calculation, equipment accumulation.
"""

import os
import uuid
import math

import pytest
import requests

# -- Config --

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")

# User IDs - first user to touch the server becomes admin
USER_ID = "00000000-0000-0000-0000-000000000001"
USER_ID_2 = "00000000-0000-0000-0000-000000000002"
USER_ID_3 = "00000000-0000-0000-0000-000000000003"

HEADERS = {
    "X-User-Id": USER_ID,
    "Content-Type": "application/json",
}

HEADERS_USER2 = {
    "X-User-Id": USER_ID_2,
    "Content-Type": "application/json",
}

HEADERS_USER3 = {
    "X-User-Id": USER_ID_3,
    "Content-Type": "application/json",
}

UNIQUE = uuid.uuid4().hex[:8]


# -- HTTP Helpers --

def api_get(path, params=None, headers=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers or HEADERS, timeout=30)


def api_post(path, json_data=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=headers or HEADERS, timeout=30)


def api_patch(path, json_data=None, headers=None):
    return requests.patch(f"{BASE_URL}{path}", json=json_data, headers=headers or HEADERS, timeout=30)


def api_delete(path, headers=None):
    return requests.delete(f"{BASE_URL}{path}", headers=headers or HEADERS, timeout=30)


def ensure_user():
    """Make a request to ensure user is auto-created."""
    api_get("/api/auth/profile")


def get_username(headers=None):
    """Get the username for the user identified by the headers."""
    resp = api_get("/api/auth/profile", headers=headers)
    return resp.json()["data"]["username"]


# ================================================================
# PART 1: Ping & Auth
# ================================================================


class TestPingAndAuth:

    def test_ping_no_auth(self):
        """Ping should work without auth."""
        resp = requests.get(f"{BASE_URL}/api/ping", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_missing_header_returns_401(self):
        resp = requests.get(f"{BASE_URL}/api/sports", timeout=30)
        assert resp.status_code == 401

    def test_missing_header_on_workouts(self):
        resp = requests.get(f"{BASE_URL}/api/workouts", timeout=30)
        assert resp.status_code == 401

    def test_missing_header_on_records(self):
        resp = requests.get(f"{BASE_URL}/api/records", timeout=30)
        assert resp.status_code == 401

    def test_auto_create_user(self):
        """A new user ID auto-creates a profile."""
        ensure_user()
        resp = api_get("/api/auth/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        profile = data["data"]
        assert "username" in profile
        assert profile["display_ascent"] is True

    def test_first_user_is_admin(self):
        """The first auto-created user should be admin."""
        ensure_user()
        resp = api_get("/api/auth/profile")
        profile = resp.json()["data"]
        assert profile["is_admin"] is True

    def test_second_user_is_not_admin(self):
        """Subsequent users should not be admin."""
        resp = api_get("/api/auth/profile", headers=HEADERS_USER2)
        profile = resp.json()["data"]
        assert profile["is_admin"] is False


# ================================================================
# PART 2: User Profile
# ================================================================


class TestUserProfile:

    def test_get_profile(self):
        ensure_user()
        resp = api_get("/api/auth/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        profile = data["data"]
        assert "username" in profile
        assert "nb_workouts" in profile
        assert "nb_sports" in profile
        assert "total_distance" in profile
        assert "total_duration" in profile
        assert "created_at" in profile
        assert "sports_list" in profile
        assert "records" in profile

    def test_update_profile(self):
        ensure_user()
        original_profile = api_get("/api/auth/profile").json()["data"]
        original_values = {
            field: original_profile[field]
            for field in ("first_name", "last_name", "language", "timezone", "display_ascent")
        }
        try:
            resp = api_patch("/api/auth/profile", {
                "first_name": "Test",
                "last_name": "User",
                "language": "fr",
                "timezone": "Europe/Paris",
                "display_ascent": False,
            })
            assert resp.status_code == 200
            profile = resp.json()["data"]
            assert profile["first_name"] == "Test"
            assert profile["last_name"] == "User"
            assert profile["language"] == "fr"
            assert profile["timezone"] == "Europe/Paris"
            assert profile["display_ascent"] is False
        finally:
            api_patch("/api/auth/profile", original_values)

    def test_update_username(self):
        ensure_user()
        original_username = get_username()
        new_name = f"user_{UNIQUE}"
        try:
            resp = api_patch("/api/auth/profile", {"username": new_name})
            assert resp.status_code == 200
            assert resp.json()["data"]["username"] == new_name
        finally:
            api_patch("/api/auth/profile", {"username": original_username})


# ================================================================
# PART 3: Sports
# ================================================================


class TestSports:

    def test_list_sports(self):
        ensure_user()
        resp = api_get("/api/sports")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        sports = data["data"]["sports"]
        assert isinstance(sports, list)
        assert len(sports) >= 7
        # Check expected fields
        sport = sports[0]
        assert "id" in sport
        assert "label" in sport
        assert "is_active" in sport

    def test_get_sport(self):
        ensure_user()
        resp = api_get("/api/sports/1")
        assert resp.status_code == 200
        data = resp.json()
        sports = data["data"]["sports"]
        assert len(sports) == 1
        assert sports[0]["id"] == 1

    def test_get_sport_not_found(self):
        ensure_user()
        resp = api_get("/api/sports/999")
        assert resp.status_code == 404

    def test_update_sport_admin(self):
        """Admin can toggle sport is_active."""
        ensure_user()
        try:
            # Deactivate sport 7
            resp = api_patch("/api/sports/7", {"is_active": False})
            assert resp.status_code == 200
            sport = resp.json()["data"]["sports"][0]
            assert sport["is_active"] is False
        finally:
            resp = api_patch("/api/sports/7", {"is_active": True})

        assert resp.status_code == 200
        sport = resp.json()["data"]["sports"][0]
        assert sport["is_active"] is True

    def test_update_sport_non_admin_forbidden(self):
        """Non-admin cannot update sports."""
        try:
            resp = api_patch("/api/sports/1", {"is_active": False}, headers=HEADERS_USER2)
            assert resp.status_code == 403
        finally:
            api_patch("/api/sports/1", {"is_active": True})

    def test_update_sport_not_found(self):
        ensure_user()
        resp = api_patch("/api/sports/999", {"is_active": False})
        assert resp.status_code == 404


# ================================================================
# PART 4: Workouts CRUD
# ================================================================


class TestWorkoutsCRUD:

    def test_create_workout(self):
        ensure_user()
        resp = api_post("/api/workouts", {
            "sport_id": 5,
            "duration": 3600,
            "distance": 10.0,
            "workout_date": "2024-03-15 08:00:00",
            "title": f"Morning Run {UNIQUE}",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "success"
        workouts = data["data"]["workouts"]
        assert len(workouts) == 1
        w = workouts[0]
        assert w["sport_id"] == 5
        assert w["distance"] == 10.0
        assert w["title"] == f"Morning Run {UNIQUE}"
        assert "id" in w
        assert "duration" in w
        assert "ave_speed" in w
        assert "max_speed" in w
        assert "equipments" in w
        assert "records" in w

    def test_create_workout_duration_format(self):
        """Duration in response should be H:MM:SS string."""
        ensure_user()
        resp = api_post("/api/workouts", {
            "sport_id": 5,
            "duration": 5400,
            "distance": 12.0,
            "workout_date": "2024-03-16 09:00:00",
        })
        assert resp.status_code == 201
        w = resp.json()["data"]["workouts"][0]
        assert w["duration"] == "1:30:00"

    def test_create_workout_ave_speed(self):
        """ave_speed = distance / (duration / 3600)."""
        ensure_user()
        resp = api_post("/api/workouts", {
            "sport_id": 5,
            "duration": 1800,  # 30 min
            "distance": 5.0,
            "workout_date": "2024-03-17 07:00:00",
        })
        assert resp.status_code == 201
        w = resp.json()["data"]["workouts"][0]
        # 5.0 / (1800/3600) = 5.0 / 0.5 = 10.0
        assert abs(w["ave_speed"] - 10.0) < 0.01
        assert abs(w["max_speed"] - 10.0) < 0.01

    def test_create_workout_with_ascent(self):
        ensure_user()
        resp = api_post("/api/workouts", {
            "sport_id": 3,
            "duration": 7200,
            "distance": 8.0,
            "workout_date": "2024-03-18 06:00:00",
            "ascent": 500.0,
            "descent": 300.0,
            "notes": "Hill hike",
        })
        assert resp.status_code == 201
        w = resp.json()["data"]["workouts"][0]
        assert w["ascent"] == 500.0
        assert w["descent"] == 300.0
        assert w["notes"] == "Hill hike"

    def test_create_workout_invalid_sport(self):
        """Non-existent sport_id returns 404."""
        ensure_user()
        resp = api_post("/api/workouts", {
            "sport_id": 999,
            "duration": 3600,
            "distance": 10.0,
            "workout_date": "2024-03-19 08:00:00",
        })
        assert resp.status_code == 404

    def test_create_workout_inactive_sport(self):
        """Cannot create workout for inactive sport."""
        ensure_user()
        try:
            # Deactivate sport 7
            api_patch("/api/sports/7", {"is_active": False})
            resp = api_post("/api/workouts", {
                "sport_id": 7,
                "duration": 3600,
                "distance": 10.0,
                "workout_date": "2024-03-19 08:00:00",
            })
            assert resp.status_code == 400
        finally:
            api_patch("/api/sports/7", {"is_active": True})

    def test_get_workout(self):
        ensure_user()
        create_resp = api_post("/api/workouts", {
            "sport_id": 5,
            "duration": 2400,
            "distance": 7.5,
            "workout_date": "2024-04-01 10:00:00",
            "title": f"Get Test {UNIQUE}",
        })
        workout_id = create_resp.json()["data"]["workouts"][0]["id"]

        resp = api_get(f"/api/workouts/{workout_id}")
        assert resp.status_code == 200
        w = resp.json()["data"]["workouts"][0]
        assert w["id"] == workout_id
        assert w["title"] == f"Get Test {UNIQUE}"

    def test_get_workout_not_found(self):
        ensure_user()
        resp = api_get("/api/workouts/00000000-0000-0000-0000-999999999999")
        assert resp.status_code == 404

    def test_update_workout(self):
        ensure_user()
        create_resp = api_post("/api/workouts", {
            "sport_id": 5,
            "duration": 3600,
            "distance": 10.0,
            "workout_date": "2024-04-02 08:00:00",
        })
        workout_id = create_resp.json()["data"]["workouts"][0]["id"]

        resp = api_patch(f"/api/workouts/{workout_id}", {
            "distance": 12.0,
            "title": "Updated run",
        })
        assert resp.status_code == 200
        w = resp.json()["data"]["workouts"][0]
        assert w["distance"] == 12.0
        assert w["title"] == "Updated run"
        # Speed should be recalculated: 12.0 / (3600/3600) = 12.0
        assert abs(w["ave_speed"] - 12.0) < 0.01

    def test_delete_workout(self):
        ensure_user()
        create_resp = api_post("/api/workouts", {
            "sport_id": 5,
            "duration": 1200,
            "distance": 3.0,
            "workout_date": "2024-04-03 07:00:00",
        })
        workout_id = create_resp.json()["data"]["workouts"][0]["id"]

        resp = api_delete(f"/api/workouts/{workout_id}")
        assert resp.status_code == 204

        # Verify it's gone
        get_resp = api_get(f"/api/workouts/{workout_id}")
        assert get_resp.status_code == 404

    def test_delete_workout_not_found(self):
        ensure_user()
        resp = api_delete("/api/workouts/00000000-0000-0000-0000-999999999999")
        assert resp.status_code == 404


# ================================================================
# PART 5: Workout Listing & Pagination
# ================================================================


class TestWorkoutListing:

    def test_list_workouts_pagination(self):
        """Check pagination structure."""
        ensure_user()
        resp = api_get("/api/workouts", params={"page": 1, "per_page": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert "pagination" in data
        pag = data["pagination"]
        assert "page" in pag
        assert "pages" in pag
        assert "total" in pag
        assert "has_next" in pag
        assert "has_prev" in pag
        assert pag["page"] == 1
        workouts = data["data"]["workouts"]
        assert len(workouts) <= 2

    def test_list_workouts_order_desc(self):
        """Default order should be desc by workout_date."""
        ensure_user()
        # Create workouts with different dates
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 1800, "distance": 5.0,
            "workout_date": "2024-01-01 08:00:00",
        })
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 1800, "distance": 5.0,
            "workout_date": "2024-06-01 08:00:00",
        })

        resp = api_get("/api/workouts", params={"per_page": 50})
        workouts = resp.json()["data"]["workouts"]
        if len(workouts) >= 2:
            dates = [w["workout_date"] for w in workouts]
            assert dates == sorted(dates, reverse=True), "Workouts should be ordered desc by date"

    def test_list_workouts_order_asc(self):
        ensure_user()
        resp = api_get("/api/workouts", params={"order": "asc", "per_page": 50})
        workouts = resp.json()["data"]["workouts"]
        if len(workouts) >= 2:
            dates = [w["workout_date"] for w in workouts]
            assert dates == sorted(dates), "Workouts should be ordered asc by date"

    def test_list_workouts_filter_sport(self):
        """Filter by sport_id."""
        ensure_user()
        # Create a cycling workout
        api_post("/api/workouts", {
            "sport_id": 1, "duration": 3600, "distance": 30.0,
            "workout_date": "2024-05-01 09:00:00",
            "title": f"Cycling filter {UNIQUE}",
        })

        resp = api_get("/api/workouts", params={"sport_id": 1, "per_page": 50})
        workouts = resp.json()["data"]["workouts"]
        for w in workouts:
            assert w["sport_id"] == 1

    def test_list_workouts_filter_date_range(self):
        """Filter by from/to date."""
        ensure_user()
        resp = api_get("/api/workouts", params={
            "from": "2024-04-01",
            "to": "2024-04-30",
            "per_page": 50,
        })
        assert resp.status_code == 200
        workouts = resp.json()["data"]["workouts"]
        for w in workouts:
            assert w["workout_date"] >= "2024-04-01"
            assert w["workout_date"] <= "2024-04-30 23:59:59"

    def test_list_workouts_order_by_distance(self):
        """Order by distance."""
        ensure_user()
        resp = api_get("/api/workouts", params={"order_by": "distance", "order": "asc", "per_page": 50})
        workouts = resp.json()["data"]["workouts"]
        if len(workouts) >= 2:
            distances = [w["distance"] for w in workouts]
            assert distances == sorted(distances), "Should be sorted by distance asc"


# ================================================================
# PART 6: Records Auto-Calculation
# ================================================================


class TestRecords:

    def test_records_created_on_workout(self):
        """Creating a workout should create records for that sport."""
        ensure_user()
        # Use a dedicated user to avoid interference
        headers = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}
        resp = api_post("/api/workouts", {
            "sport_id": 6,
            "duration": 1800,
            "distance": 3.0,
            "workout_date": "2024-07-01 08:00:00",
            "ascent": 50.0,
            "descent": 40.0,
        }, headers=headers)
        assert resp.status_code == 201

        # Check records
        rec_resp = api_get("/api/records", headers=headers)
        assert rec_resp.status_code == 200
        records = rec_resp.json()["data"]["records"]
        sport6_records = [r for r in records if r["sport_id"] == 6]
        record_types = {r["record_type"] for r in sport6_records}
        assert "FD" in record_types, "Should have FD record"
        assert "LD" in record_types, "Should have LD record"
        assert "MS" in record_types, "Should have MS record"
        assert "HA" in record_types, "Should have HA record (ascent provided)"

    def test_record_values_correct(self):
        """Record values should match the workout data."""
        headers = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}
        resp = api_post("/api/workouts", {
            "sport_id": 5,
            "duration": 3600,
            "distance": 10.0,
            "workout_date": "2024-07-02 08:00:00",
            "ascent": 100.0,
        }, headers=headers)
        assert resp.status_code == 201
        workout_id = resp.json()["data"]["workouts"][0]["id"]

        rec_resp = api_get("/api/records", headers=headers)
        records = rec_resp.json()["data"]["records"]
        sport5_records = {r["record_type"]: r for r in records if r["sport_id"] == 5}

        # FD = 10.0 km
        assert abs(sport5_records["FD"]["value"] - 10.0) < 0.01
        assert sport5_records["FD"]["workout_id"] == workout_id

        # MS = 10.0 / (3600/3600) = 10.0 km/h
        assert abs(sport5_records["MS"]["value"] - 10.0) < 0.01

        # LD = "1:00:00"
        assert sport5_records["LD"]["value"] == "1:00:00"

        # HA = 100.0 m
        assert abs(sport5_records["HA"]["value"] - 100.0) < 0.01

    def test_records_update_on_better_workout(self):
        """Adding a better workout should update the record."""
        headers = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}

        # First workout: 10km in 1h
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-07-03 08:00:00",
        }, headers=headers)

        # Second workout: 15km in 1h (better distance and speed)
        resp2 = api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 15.0,
            "workout_date": "2024-07-04 08:00:00",
        }, headers=headers)
        workout2_id = resp2.json()["data"]["workouts"][0]["id"]

        rec_resp = api_get("/api/records", headers=headers)
        records = rec_resp.json()["data"]["records"]
        sport5_records = {r["record_type"]: r for r in records if r["sport_id"] == 5}

        # FD should be 15.0 from workout2
        assert abs(sport5_records["FD"]["value"] - 15.0) < 0.01
        assert sport5_records["FD"]["workout_id"] == workout2_id

        # MS should be 15.0 km/h from workout2
        assert abs(sport5_records["MS"]["value"] - 15.0) < 0.01

    def test_records_update_on_delete(self):
        """Deleting the record-holding workout should reassign the record."""
        headers = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}

        # Workout A: 5km
        resp_a = api_post("/api/workouts", {
            "sport_id": 5, "duration": 1800, "distance": 5.0,
            "workout_date": "2024-07-05 08:00:00",
        }, headers=headers)
        workout_a_id = resp_a.json()["data"]["workouts"][0]["id"]

        # Workout B: 20km (record holder)
        resp_b = api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 20.0,
            "workout_date": "2024-07-06 08:00:00",
        }, headers=headers)
        workout_b_id = resp_b.json()["data"]["workouts"][0]["id"]

        # Delete workout B
        del_resp = api_delete(f"/api/workouts/{workout_b_id}", headers=headers)
        assert del_resp.status_code == 204

        # FD record should now point to workout A (5km)
        rec_resp = api_get("/api/records", headers=headers)
        records = rec_resp.json()["data"]["records"]
        sport5_records = {r["record_type"]: r for r in records if r["sport_id"] == 5}
        assert abs(sport5_records["FD"]["value"] - 5.0) < 0.01
        assert sport5_records["FD"]["workout_id"] == workout_a_id

    def test_records_deleted_when_no_workouts(self):
        """Deleting all workouts for a sport should remove all records for that sport."""
        headers = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}

        resp = api_post("/api/workouts", {
            "sport_id": 6, "duration": 1800, "distance": 3.0,
            "workout_date": "2024-07-07 08:00:00",
        }, headers=headers)
        workout_id = resp.json()["data"]["workouts"][0]["id"]

        # Delete the only workout
        api_delete(f"/api/workouts/{workout_id}", headers=headers)

        # No records should exist for sport 6
        rec_resp = api_get("/api/records", headers=headers)
        records = rec_resp.json()["data"]["records"]
        sport6_records = [r for r in records if r["sport_id"] == 6]
        assert len(sport6_records) == 0

    def test_no_ha_record_without_ascent(self):
        """No HA record if no workout has ascent data."""
        headers = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-07-08 08:00:00",
        }, headers=headers)

        rec_resp = api_get("/api/records", headers=headers)
        records = rec_resp.json()["data"]["records"]
        sport5_records = {r["record_type"]: r for r in records if r["sport_id"] == 5}
        assert "HA" not in sport5_records, "No HA record without ascent data"

    def test_records_on_workout_response(self):
        """Workout detail should include records relevant to it."""
        headers = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}
        resp = api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-07-09 08:00:00",
        }, headers=headers)
        workout_id = resp.json()["data"]["workouts"][0]["id"]

        get_resp = api_get(f"/api/workouts/{workout_id}", headers=headers)
        w = get_resp.json()["data"]["workouts"][0]
        assert "records" in w
        # Since it's the only workout, all applicable records should reference it
        for rec in w["records"]:
            assert rec["workout_id"] == workout_id

    def test_record_update_on_workout_update(self):
        """Updating a workout should recalculate records."""
        headers = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}

        # Create workout with 10km
        resp = api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-07-10 08:00:00",
        }, headers=headers)
        workout_id = resp.json()["data"]["workouts"][0]["id"]

        # Update distance to 20km
        api_patch(f"/api/workouts/{workout_id}", {"distance": 20.0}, headers=headers)

        rec_resp = api_get("/api/records", headers=headers)
        records = rec_resp.json()["data"]["records"]
        sport5_records = {r["record_type"]: r for r in records if r["sport_id"] == 5}
        assert abs(sport5_records["FD"]["value"] - 20.0) < 0.01


# ================================================================
# PART 7: Statistics
# ================================================================


class TestStatistics:

    def test_stats_by_sport(self):
        """Stats by sport should aggregate workouts."""
        headers = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}
        username = get_username(headers=headers)

        # Create 2 running workouts and 1 cycling workout
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-08-01 08:00:00",
            "ascent": 50.0, "descent": 30.0,
        }, headers=headers)
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 1800, "distance": 5.0,
            "workout_date": "2024-08-02 08:00:00",
            "ascent": 25.0, "descent": 15.0,
        }, headers=headers)
        api_post("/api/workouts", {
            "sport_id": 1, "duration": 7200, "distance": 40.0,
            "workout_date": "2024-08-03 09:00:00",
        }, headers=headers)

        resp = api_get(f"/api/stats/{username}/by_sport", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        stats = data["data"]["statistics"]

        # Running (sport 5)
        assert "5" in stats
        running = stats["5"]
        assert running["nb_workouts"] == 2
        assert abs(running["total_distance"] - 15.0) < 0.01
        assert running["total_duration"] == 5400
        assert abs(running["total_ascent"] - 75.0) < 0.01
        assert abs(running["total_descent"] - 45.0) < 0.01

        # Cycling (sport 1)
        assert "1" in stats
        cycling = stats["1"]
        assert cycling["nb_workouts"] == 1
        assert abs(cycling["total_distance"] - 40.0) < 0.01

    def test_stats_by_sport_filter(self):
        """Stats by sport can filter by sport_id."""
        headers = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}
        username = get_username(headers=headers)

        api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-08-04 08:00:00",
        }, headers=headers)
        api_post("/api/workouts", {
            "sport_id": 1, "duration": 3600, "distance": 30.0,
            "workout_date": "2024-08-05 08:00:00",
        }, headers=headers)

        resp = api_get(f"/api/stats/{username}/by_sport", params={"sport_id": 5}, headers=headers)
        stats = resp.json()["data"]["statistics"]
        assert "5" in stats
        assert "1" not in stats

    def test_stats_by_time_month(self):
        """Stats by time with month grouping."""
        headers = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}
        username = get_username(headers=headers)

        api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-03-15 08:00:00",
        }, headers=headers)
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 1800, "distance": 5.0,
            "workout_date": "2024-03-20 08:00:00",
        }, headers=headers)

        resp = api_get(f"/api/stats/{username}/by_time", params={"time": "month"}, headers=headers)
        assert resp.status_code == 200
        stats = resp.json()["data"]["statistics"]
        # Should have 2024 -> 3 (March) -> sport 5
        assert "2024" in stats
        assert "3" in stats["2024"]
        march_sport5 = stats["2024"]["3"]["5"]
        assert march_sport5["nb_workouts"] == 2
        assert abs(march_sport5["total_distance"] - 15.0) < 0.01
        assert march_sport5["total_duration"] == 5400

    def test_stats_by_time_year(self):
        """Stats by time with year grouping."""
        headers = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}
        username = get_username(headers=headers)

        api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-01-15 08:00:00",
        }, headers=headers)
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 1800, "distance": 5.0,
            "workout_date": "2024-11-20 08:00:00",
        }, headers=headers)

        resp = api_get(f"/api/stats/{username}/by_time", params={"time": "year"}, headers=headers)
        assert resp.status_code == 200
        stats = resp.json()["data"]["statistics"]
        assert "2024" in stats
        # For year grouping, the inner key is empty string
        year_data = stats["2024"][""]["5"]
        assert year_data["nb_workouts"] == 2
        assert abs(year_data["total_distance"] - 15.0) < 0.01

    def test_stats_by_time_week(self):
        """Stats by time with week grouping."""
        headers = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}
        username = get_username(headers=headers)

        # 2024-01-08 is ISO week 2
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-01-08 08:00:00",
        }, headers=headers)

        resp = api_get(f"/api/stats/{username}/by_time", params={"time": "week"}, headers=headers)
        assert resp.status_code == 200
        stats = resp.json()["data"]["statistics"]
        assert "2024" in stats
        # ISO week 2
        assert "2" in stats["2024"]

    def test_stats_user_not_found(self):
        """Stats for non-existent username should return 404."""
        ensure_user()
        resp = api_get("/api/stats/nonexistent_user_xyz/by_sport")
        assert resp.status_code == 404

    def test_stats_empty(self):
        """User with no workouts should return empty statistics."""
        headers = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}
        username = get_username(headers=headers)

        resp = api_get(f"/api/stats/{username}/by_sport", headers=headers)
        assert resp.status_code == 200
        stats = resp.json()["data"]["statistics"]
        assert stats == {} or len(stats) == 0


# ================================================================
# PART 8: Equipment CRUD
# ================================================================


class TestEquipmentCRUD:

    def test_create_equipment(self):
        ensure_user()
        resp = api_post("/api/equipments", {
            "label": f"Trail Shoes {UNIQUE}",
            "equipment_type_id": 1,
            "description": "Good for trails",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "success"
        equips = data["data"]["equipments"]
        assert len(equips) == 1
        e = equips[0]
        assert e["label"] == f"Trail Shoes {UNIQUE}"
        assert e["equipment_type"]["id"] == 1
        assert e["equipment_type"]["label"] == "Shoe"
        assert e["description"] == "Good for trails"
        assert e["is_active"] is True
        assert e["total_distance"] == 0
        assert e["total_duration"] == 0
        assert e["workouts_count"] == 0
        assert "id" in e

    def test_list_equipment(self):
        ensure_user()
        resp = api_get("/api/equipments")
        assert resp.status_code == 200
        equips = resp.json()["data"]["equipments"]
        assert isinstance(equips, list)

    def test_get_equipment(self):
        ensure_user()
        create_resp = api_post("/api/equipments", {
            "label": f"Road Bike {UNIQUE}",
            "equipment_type_id": 2,
        })
        equip_id = create_resp.json()["data"]["equipments"][0]["id"]

        resp = api_get(f"/api/equipments/{equip_id}")
        assert resp.status_code == 200
        e = resp.json()["data"]["equipments"][0]
        assert e["id"] == equip_id

    def test_get_equipment_not_found(self):
        ensure_user()
        resp = api_get("/api/equipments/00000000-0000-0000-0000-999999999999")
        assert resp.status_code == 404

    def test_update_equipment(self):
        ensure_user()
        create_resp = api_post("/api/equipments", {
            "label": f"Old Shoes {UNIQUE}",
            "equipment_type_id": 1,
        })
        equip_id = create_resp.json()["data"]["equipments"][0]["id"]

        resp = api_patch(f"/api/equipments/{equip_id}", {
            "label": f"New Shoes {UNIQUE}",
            "is_active": False,
        })
        assert resp.status_code == 200
        e = resp.json()["data"]["equipments"][0]
        assert e["label"] == f"New Shoes {UNIQUE}"
        assert e["is_active"] is False

    def test_delete_equipment_no_workouts(self):
        ensure_user()
        create_resp = api_post("/api/equipments", {
            "label": f"Delete Me {UNIQUE}",
            "equipment_type_id": 1,
        })
        equip_id = create_resp.json()["data"]["equipments"][0]["id"]

        resp = api_delete(f"/api/equipments/{equip_id}")
        assert resp.status_code == 204

        # Verify gone
        get_resp = api_get(f"/api/equipments/{equip_id}")
        assert get_resp.status_code == 404

    def test_filter_equipment_by_type(self):
        ensure_user()
        # Create shoe and bike
        api_post("/api/equipments", {
            "label": f"Filter Shoe {UNIQUE}",
            "equipment_type_id": 1,
        })
        api_post("/api/equipments", {
            "label": f"Filter Bike {UNIQUE}",
            "equipment_type_id": 2,
        })

        resp = api_get("/api/equipments", params={"equipment_type_id": 1})
        equips = resp.json()["data"]["equipments"]
        for e in equips:
            assert e["equipment_type"]["id"] == 1


# ================================================================
# PART 9: Equipment Types
# ================================================================


class TestEquipmentTypes:

    def test_list_equipment_types(self):
        ensure_user()
        resp = api_get("/api/equipment-types")
        assert resp.status_code == 200
        types = resp.json()["data"]["equipment_types"]
        assert isinstance(types, list)
        assert len(types) >= 6
        labels = [t["label"] for t in types]
        assert "Shoe" in labels
        assert "Bike" in labels

    def test_get_equipment_type(self):
        ensure_user()
        resp = api_get("/api/equipment-types/1")
        assert resp.status_code == 200
        types = resp.json()["data"]["equipment_types"]
        assert len(types) == 1
        assert types[0]["id"] == 1
        assert types[0]["label"] == "Shoe"

    def test_get_equipment_type_not_found(self):
        ensure_user()
        resp = api_get("/api/equipment-types/999")
        assert resp.status_code == 404


# ================================================================
# PART 10: Equipment Accumulation
# ================================================================


class TestEquipmentAccumulation:

    def test_equipment_accumulates_on_link(self):
        """Linking equipment to a workout should update totals."""
        headers = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}

        # Create equipment
        eq_resp = api_post("/api/equipments", {
            "label": "Accum Shoes",
            "equipment_type_id": 1,
        }, headers=headers)
        equip_id = eq_resp.json()["data"]["equipments"][0]["id"]

        # Create workout
        w_resp = api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-09-01 08:00:00",
        }, headers=headers)
        workout_id = w_resp.json()["data"]["workouts"][0]["id"]

        # Link equipment
        link_resp = api_post(f"/api/workouts/{workout_id}/equipments/{equip_id}", headers=headers)
        assert link_resp.status_code == 200

        # Check equipment totals
        eq_get = api_get(f"/api/equipments/{equip_id}", headers=headers)
        e = eq_get.json()["data"]["equipments"][0]
        assert abs(e["total_distance"] - 10.0) < 0.01
        assert e["total_duration"] == 3600
        assert e["workouts_count"] == 1

    def test_equipment_accumulates_multiple_workouts(self):
        """Multiple linked workouts should sum up."""
        headers = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}

        eq_resp = api_post("/api/equipments", {
            "label": "Multi Shoes",
            "equipment_type_id": 1,
        }, headers=headers)
        equip_id = eq_resp.json()["data"]["equipments"][0]["id"]

        # Workout 1: 10km, 3600s
        w1_resp = api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-09-02 08:00:00",
        }, headers=headers)
        w1_id = w1_resp.json()["data"]["workouts"][0]["id"]
        api_post(f"/api/workouts/{w1_id}/equipments/{equip_id}", headers=headers)

        # Workout 2: 5km, 1800s
        w2_resp = api_post("/api/workouts", {
            "sport_id": 5, "duration": 1800, "distance": 5.0,
            "workout_date": "2024-09-03 08:00:00",
        }, headers=headers)
        w2_id = w2_resp.json()["data"]["workouts"][0]["id"]
        api_post(f"/api/workouts/{w2_id}/equipments/{equip_id}", headers=headers)

        # Check totals
        eq_get = api_get(f"/api/equipments/{equip_id}", headers=headers)
        e = eq_get.json()["data"]["equipments"][0]
        assert abs(e["total_distance"] - 15.0) < 0.01
        assert e["total_duration"] == 5400
        assert e["workouts_count"] == 2

    def test_equipment_decreases_on_unlink(self):
        """Unlinking equipment should decrease totals."""
        headers = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}

        eq_resp = api_post("/api/equipments", {
            "label": "Unlink Shoes",
            "equipment_type_id": 1,
        }, headers=headers)
        equip_id = eq_resp.json()["data"]["equipments"][0]["id"]

        # Create and link 2 workouts
        w1_resp = api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-09-04 08:00:00",
        }, headers=headers)
        w1_id = w1_resp.json()["data"]["workouts"][0]["id"]
        api_post(f"/api/workouts/{w1_id}/equipments/{equip_id}", headers=headers)

        w2_resp = api_post("/api/workouts", {
            "sport_id": 5, "duration": 1800, "distance": 5.0,
            "workout_date": "2024-09-05 08:00:00",
        }, headers=headers)
        w2_id = w2_resp.json()["data"]["workouts"][0]["id"]
        api_post(f"/api/workouts/{w2_id}/equipments/{equip_id}", headers=headers)

        # Unlink workout 1
        del_resp = api_delete(f"/api/workouts/{w1_id}/equipments/{equip_id}", headers=headers)
        assert del_resp.status_code == 204

        # Totals should now reflect only workout 2
        eq_get = api_get(f"/api/equipments/{equip_id}", headers=headers)
        e = eq_get.json()["data"]["equipments"][0]
        assert abs(e["total_distance"] - 5.0) < 0.01
        assert e["total_duration"] == 1800
        assert e["workouts_count"] == 1

    def test_equipment_updates_on_workout_update(self):
        """Updating a linked workout should update equipment totals."""
        headers = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}

        eq_resp = api_post("/api/equipments", {
            "label": "Update Shoes",
            "equipment_type_id": 1,
        }, headers=headers)
        equip_id = eq_resp.json()["data"]["equipments"][0]["id"]

        w_resp = api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-09-06 08:00:00",
        }, headers=headers)
        w_id = w_resp.json()["data"]["workouts"][0]["id"]
        api_post(f"/api/workouts/{w_id}/equipments/{equip_id}", headers=headers)

        # Update workout distance
        api_patch(f"/api/workouts/{w_id}", {"distance": 20.0}, headers=headers)

        eq_get = api_get(f"/api/equipments/{equip_id}", headers=headers)
        e = eq_get.json()["data"]["equipments"][0]
        assert abs(e["total_distance"] - 20.0) < 0.01

    def test_equipment_updates_on_workout_delete(self):
        """Deleting a linked workout should decrease equipment totals."""
        headers = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}

        eq_resp = api_post("/api/equipments", {
            "label": "Delete Shoes",
            "equipment_type_id": 1,
        }, headers=headers)
        equip_id = eq_resp.json()["data"]["equipments"][0]["id"]

        w_resp = api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-09-07 08:00:00",
        }, headers=headers)
        w_id = w_resp.json()["data"]["workouts"][0]["id"]
        api_post(f"/api/workouts/{w_id}/equipments/{equip_id}", headers=headers)

        # Delete the workout
        api_delete(f"/api/workouts/{w_id}", headers=headers)

        eq_get = api_get(f"/api/equipments/{equip_id}", headers=headers)
        e = eq_get.json()["data"]["equipments"][0]
        assert e["total_distance"] == 0
        assert e["total_duration"] == 0
        assert e["workouts_count"] == 0

    def test_cannot_delete_equipment_with_workouts(self):
        """Equipment with linked workouts cannot be deleted."""
        headers = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}

        eq_resp = api_post("/api/equipments", {
            "label": "Cant Delete Shoes",
            "equipment_type_id": 1,
        }, headers=headers)
        equip_id = eq_resp.json()["data"]["equipments"][0]["id"]

        w_resp = api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-09-08 08:00:00",
        }, headers=headers)
        w_id = w_resp.json()["data"]["workouts"][0]["id"]
        api_post(f"/api/workouts/{w_id}/equipments/{equip_id}", headers=headers)

        # Try to delete
        resp = api_delete(f"/api/equipments/{equip_id}", headers=headers)
        assert resp.status_code == 400

    def test_link_duplicate_returns_400(self):
        """Linking same equipment twice should return 400."""
        headers = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}

        eq_resp = api_post("/api/equipments", {
            "label": "Dup Link Shoes",
            "equipment_type_id": 1,
        }, headers=headers)
        equip_id = eq_resp.json()["data"]["equipments"][0]["id"]

        w_resp = api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-09-09 08:00:00",
        }, headers=headers)
        w_id = w_resp.json()["data"]["workouts"][0]["id"]

        # First link
        resp1 = api_post(f"/api/workouts/{w_id}/equipments/{equip_id}", headers=headers)
        assert resp1.status_code == 200

        # Second link (duplicate)
        resp2 = api_post(f"/api/workouts/{w_id}/equipments/{equip_id}", headers=headers)
        assert resp2.status_code == 400

    def test_link_inactive_equipment_returns_400(self):
        """Cannot link inactive equipment."""
        headers = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}

        eq_resp = api_post("/api/equipments", {
            "label": "Inactive Shoes",
            "equipment_type_id": 1,
            "is_active": False,
        }, headers=headers)
        equip_id = eq_resp.json()["data"]["equipments"][0]["id"]

        w_resp = api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-09-10 08:00:00",
        }, headers=headers)
        w_id = w_resp.json()["data"]["workouts"][0]["id"]

        resp = api_post(f"/api/workouts/{w_id}/equipments/{equip_id}", headers=headers)
        assert resp.status_code == 400

    def test_equipment_shows_on_workout(self):
        """Linked equipment should appear in workout response."""
        headers = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}

        eq_resp = api_post("/api/equipments", {
            "label": "Visible Shoes",
            "equipment_type_id": 1,
        }, headers=headers)
        equip_id = eq_resp.json()["data"]["equipments"][0]["id"]

        w_resp = api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-09-11 08:00:00",
        }, headers=headers)
        w_id = w_resp.json()["data"]["workouts"][0]["id"]
        api_post(f"/api/workouts/{w_id}/equipments/{equip_id}", headers=headers)

        # Get workout
        get_resp = api_get(f"/api/workouts/{w_id}", headers=headers)
        w = get_resp.json()["data"]["workouts"][0]
        assert len(w["equipments"]) == 1
        assert w["equipments"][0]["id"] == equip_id
        assert w["equipments"][0]["label"] == "Visible Shoes"


# ================================================================
# PART 11: Data Isolation
# ================================================================


class TestDataIsolation:

    def test_workout_isolation(self):
        """User A's workouts not visible to User B."""
        headers_a = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}
        headers_b = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}

        resp = api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-10-01 08:00:00",
            "title": "Secret workout",
        }, headers=headers_a)
        workout_id = resp.json()["data"]["workouts"][0]["id"]

        # User B cannot see it
        get_resp = api_get(f"/api/workouts/{workout_id}", headers=headers_b)
        assert get_resp.status_code == 404

    def test_equipment_isolation(self):
        """User A's equipment not visible to User B."""
        headers_a = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}
        headers_b = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}

        resp = api_post("/api/equipments", {
            "label": "Private Shoes",
            "equipment_type_id": 1,
        }, headers=headers_a)
        equip_id = resp.json()["data"]["equipments"][0]["id"]

        get_resp = api_get(f"/api/equipments/{equip_id}", headers=headers_b)
        assert get_resp.status_code == 404

    def test_records_isolation(self):
        """User A's records not visible to User B."""
        headers_a = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}
        headers_b = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}

        api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-10-02 08:00:00",
        }, headers=headers_a)

        # User B should have no records
        rec_resp = api_get("/api/records", headers=headers_b)
        records = rec_resp.json()["data"]["records"]
        assert len(records) == 0

    def test_cannot_link_other_users_equipment(self):
        """User A cannot link User B's equipment to their workout."""
        headers_a = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}
        headers_b = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}

        # User B creates equipment
        eq_resp = api_post("/api/equipments", {
            "label": "User B Shoes",
            "equipment_type_id": 1,
        }, headers=headers_b)
        equip_id = eq_resp.json()["data"]["equipments"][0]["id"]

        # User A creates workout
        w_resp = api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-10-03 08:00:00",
        }, headers=headers_a)
        w_id = w_resp.json()["data"]["workouts"][0]["id"]

        # User A tries to link User B's equipment
        resp = api_post(f"/api/workouts/{w_id}/equipments/{equip_id}", headers=headers_a)
        assert resp.status_code in [403, 404]

    def test_cannot_delete_other_users_workout(self):
        """User B cannot delete User A's workout."""
        headers_a = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}
        headers_b = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}

        resp = api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-10-04 08:00:00",
        }, headers=headers_a)
        workout_id = resp.json()["data"]["workouts"][0]["id"]

        del_resp = api_delete(f"/api/workouts/{workout_id}", headers=headers_b)
        assert del_resp.status_code == 404


# ================================================================
# PART 12: Profile Computed Fields
# ================================================================


class TestProfileComputed:

    def test_profile_nb_workouts(self):
        """Profile should show correct nb_workouts count."""
        headers = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}

        # Profile with no workouts
        resp = api_get("/api/auth/profile", headers=headers)
        assert resp.json()["data"]["nb_workouts"] == 0

        # Create 2 workouts
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-11-01 08:00:00",
        }, headers=headers)
        api_post("/api/workouts", {
            "sport_id": 1, "duration": 7200, "distance": 40.0,
            "workout_date": "2024-11-02 08:00:00",
        }, headers=headers)

        resp = api_get("/api/auth/profile", headers=headers)
        profile = resp.json()["data"]
        assert profile["nb_workouts"] == 2
        assert profile["nb_sports"] == 2
        assert abs(profile["total_distance"] - 50.0) < 0.01
        assert 5 in profile["sports_list"]
        assert 1 in profile["sports_list"]

    def test_profile_total_duration_format(self):
        """Profile total_duration should be formatted as H:MM:SS."""
        headers = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}

        api_post("/api/workouts", {
            "sport_id": 5, "duration": 5400,  # 1:30:00
            "distance": 10.0,
            "workout_date": "2024-11-03 08:00:00",
        }, headers=headers)

        resp = api_get("/api/auth/profile", headers=headers)
        profile = resp.json()["data"]
        assert profile["total_duration"] == "1:30:00"


# ================================================================
# PART 13: Equipment with Workout Creation (equipment_ids)
# ================================================================


class TestEquipmentOnWorkoutCreate:

    def test_create_workout_with_equipment_ids(self):
        """Creating a workout with equipment_ids should link equipment."""
        headers = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}

        eq_resp = api_post("/api/equipments", {
            "label": "Create Link Shoes",
            "equipment_type_id": 1,
        }, headers=headers)
        equip_id = eq_resp.json()["data"]["equipments"][0]["id"]

        w_resp = api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-12-01 08:00:00",
            "equipment_ids": [equip_id],
        }, headers=headers)
        assert w_resp.status_code == 201
        w = w_resp.json()["data"]["workouts"][0]
        assert len(w["equipments"]) == 1
        assert w["equipments"][0]["id"] == equip_id

        # Equipment should have totals
        eq_get = api_get(f"/api/equipments/{equip_id}", headers=headers)
        e = eq_get.json()["data"]["equipments"][0]
        assert abs(e["total_distance"] - 10.0) < 0.01
        assert e["workouts_count"] == 1

    def test_update_workout_equipment_ids(self):
        """Updating workout with new equipment_ids should update links."""
        headers = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}

        eq1_resp = api_post("/api/equipments", {
            "label": "Shoes A",
            "equipment_type_id": 1,
        }, headers=headers)
        eq1_id = eq1_resp.json()["data"]["equipments"][0]["id"]

        eq2_resp = api_post("/api/equipments", {
            "label": "Shoes B",
            "equipment_type_id": 1,
        }, headers=headers)
        eq2_id = eq2_resp.json()["data"]["equipments"][0]["id"]

        # Create with eq1
        w_resp = api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-12-02 08:00:00",
            "equipment_ids": [eq1_id],
        }, headers=headers)
        w_id = w_resp.json()["data"]["workouts"][0]["id"]

        # Update to eq2
        api_patch(f"/api/workouts/{w_id}", {
            "equipment_ids": [eq2_id],
        }, headers=headers)

        # eq1 should now have 0 distance
        eq1_get = api_get(f"/api/equipments/{eq1_id}", headers=headers)
        assert eq1_get.json()["data"]["equipments"][0]["total_distance"] == 0
        assert eq1_get.json()["data"]["equipments"][0]["workouts_count"] == 0

        # eq2 should have 10km
        eq2_get = api_get(f"/api/equipments/{eq2_id}", headers=headers)
        assert abs(eq2_get.json()["data"]["equipments"][0]["total_distance"] - 10.0) < 0.01
        assert eq2_get.json()["data"]["equipments"][0]["workouts_count"] == 1
