"""
BackendForge - L2 Integration Tests for FitTrackee Task

Adversarial tests targeting common LLM implementation mistakes:
- Pattern 1: Field name case (snake_case expected)
- Pattern 2: Nested/related data not returned
- Pattern 3: Filters/ordering declared but not implemented
- Pattern 4: Wrong status codes
- Pattern 5: Business logic "exists but empty"
- Pattern 6: Data isolation
- Pattern 7: Cascade/side-effect omissions
- Pattern 8: Sequence-sensitive/uniqueness bugs
"""

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")

# Helpers

def headers_for(user_id=None):
    uid = user_id or str(uuid.uuid4())
    return {"X-User-Id": uid, "Content-Type": "application/json"}


def api_get(path, params=None, headers=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers, timeout=30)


def api_post(path, json_data=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=headers, timeout=30)


def api_patch(path, json_data=None, headers=None):
    return requests.patch(f"{BASE_URL}{path}", json=json_data, headers=headers, timeout=30)


def api_delete(path, headers=None):
    return requests.delete(f"{BASE_URL}{path}", headers=headers, timeout=30)


def get_username(headers):
    resp = api_get("/api/auth/profile", headers=headers)
    return resp.json()["data"]["username"]


def make_admin_headers():
    """Return headers for first user (admin). Uses a fixed ID to be stable."""
    return {"X-User-Id": "00000000-0000-0000-0000-000000000001", "Content-Type": "application/json"}


# ================================================================
# L2 Tests
# ================================================================


class TestWorkoutFieldNamesAndTypes:
    """Pattern 1+2: Verify all workout response fields have correct snake_case names and types."""

    def test_workout_response_contains_all_expected_fields(self):
        h = headers_for()
        resp = api_post("/api/workouts", {
            "sport_id": 5,
            "duration": 3661,
            "distance": 10.5,
            "workout_date": "2024-06-10 07:30:00",
            "title": "Field Check Run",
            "notes": "Testing fields",
            "ascent": 120.5,
            "descent": 80.3,
        }, headers=h)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "success"
        assert "workouts" in data["data"]
        w = data["data"]["workouts"][0]

        # Verify all expected field names (snake_case)
        assert "id" in w
        assert "sport_id" in w
        assert "title" in w
        assert "workout_date" in w
        assert "distance" in w
        assert "duration" in w
        assert "ascent" in w
        assert "descent" in w
        assert "ave_speed" in w
        assert "max_speed" in w
        assert "notes" in w
        assert "equipments" in w
        assert "records" in w
        assert "moving" in w
        assert "pauses" in w
        assert "creation_date" in w

        # Verify values are correct types
        assert isinstance(w["id"], str)
        assert isinstance(w["sport_id"], int)
        assert isinstance(w["distance"], (int, float))
        assert isinstance(w["duration"], str)  # H:MM:SS string
        assert isinstance(w["ave_speed"], (int, float))
        assert isinstance(w["max_speed"], (int, float))
        assert isinstance(w["equipments"], list)
        assert isinstance(w["records"], list)

        # Verify NOT camelCase
        assert "sportId" not in w
        assert "workoutDate" not in w
        assert "aveSpeed" not in w
        assert "maxSpeed" not in w
        assert "creationDate" not in w


class TestWorkoutDurationFormatVariousValues:
    """Pattern 5: Verify duration formatting handles edge cases correctly."""

    def test_duration_format_under_one_hour(self):
        h = headers_for()
        resp = api_post("/api/workouts", {
            "sport_id": 5, "duration": 330, "distance": 1.0,
            "workout_date": "2024-06-11 08:00:00",
        }, headers=h)
        assert resp.status_code == 201
        w = resp.json()["data"]["workouts"][0]
        # 330s = 0:05:30
        assert w["duration"] == "0:05:30"

    def test_duration_format_exact_hour(self):
        h = headers_for()
        resp = api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-06-12 08:00:00",
        }, headers=h)
        assert resp.status_code == 201
        w = resp.json()["data"]["workouts"][0]
        assert w["duration"] == "1:00:00"

    def test_duration_format_multi_hour(self):
        h = headers_for()
        resp = api_post("/api/workouts", {
            "sport_id": 3, "duration": 45045, "distance": 15.0,
            "workout_date": "2024-06-13 06:00:00",
        }, headers=h)
        assert resp.status_code == 201
        w = resp.json()["data"]["workouts"][0]
        # 45045s = 12h 30m 45s = "12:30:45"
        assert w["duration"] == "12:30:45"


class TestWorkoutSpeedComputation:
    """Pattern 5: Verify speed is actually computed, not just echoed or hardcoded."""

    def test_speed_computed_correctly(self):
        h = headers_for()
        # 15km in 45min (2700s) -> 15 / (2700/3600) = 15 / 0.75 = 20.0 km/h
        resp = api_post("/api/workouts", {
            "sport_id": 1, "duration": 2700, "distance": 15.0,
            "workout_date": "2024-06-14 09:00:00",
        }, headers=h)
        assert resp.status_code == 201
        w = resp.json()["data"]["workouts"][0]
        assert abs(w["ave_speed"] - 20.0) < 0.01
        # For no-GPX workouts, max_speed equals ave_speed
        assert abs(w["max_speed"] - 20.0) < 0.01

    def test_speed_recalculated_on_update(self):
        h = headers_for()
        resp = api_post("/api/workouts", {
            "sport_id": 1, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-06-15 09:00:00",
        }, headers=h)
        w_id = resp.json()["data"]["workouts"][0]["id"]

        # Update distance from 10 to 30 -> speed = 30 / (3600/3600) = 30 km/h
        resp2 = api_patch(f"/api/workouts/{w_id}", {"distance": 30.0}, headers=h)
        assert resp2.status_code == 200
        w = resp2.json()["data"]["workouts"][0]
        assert abs(w["ave_speed"] - 30.0) < 0.01
        assert abs(w["max_speed"] - 30.0) < 0.01

    def test_speed_zero_duration(self):
        h = headers_for()
        # 0 duration -> speed should be 0
        resp = api_post("/api/workouts", {
            "sport_id": 6, "duration": 0, "distance": 5.0,
            "workout_date": "2024-06-16 10:00:00",
        }, headers=h)
        assert resp.status_code == 201
        w = resp.json()["data"]["workouts"][0]
        assert w["ave_speed"] == 0
        assert w["max_speed"] == 0


class TestWorkoutPaginationStructure:
    """Pattern 2+3: Verify pagination response has correct structure and values."""

    def test_pagination_fields_and_values(self):
        h = headers_for()
        # Create 7 workouts
        for i in range(7):
            api_post("/api/workouts", {
                "sport_id": 5, "duration": 1800, "distance": 5.0,
                "workout_date": f"2024-07-{i+1:02d} 08:00:00",
            }, headers=h)

        # Get page 1 with per_page=3
        resp = api_get("/api/workouts", params={"page": 1, "per_page": 3}, headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert "pagination" in data
        pag = data["pagination"]
        assert pag["page"] == 1
        assert pag["total"] == 7
        assert pag["pages"] == 3  # ceil(7/3)
        assert pag["has_next"] is True
        assert pag["has_prev"] is False
        assert len(data["data"]["workouts"]) == 3

        # Get page 2
        resp2 = api_get("/api/workouts", params={"page": 2, "per_page": 3}, headers=h)
        pag2 = resp2.json()["pagination"]
        assert pag2["page"] == 2
        assert pag2["has_prev"] is True
        assert pag2["has_next"] is True
        assert len(resp2.json()["data"]["workouts"]) == 3

        # Get page 3 (last page)
        resp3 = api_get("/api/workouts", params={"page": 3, "per_page": 3}, headers=h)
        pag3 = resp3.json()["pagination"]
        assert pag3["page"] == 3
        assert pag3["has_next"] is False
        assert len(resp3.json()["data"]["workouts"]) == 1


class TestWorkoutFilterBySportId:
    """Pattern 3: Verify sport_id filter is actually applied (not just accepted and ignored)."""

    def test_filter_returns_only_matching_sport(self):
        h = headers_for()
        # Create workouts in different sports
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 1800, "distance": 5.0,
            "workout_date": "2024-07-10 08:00:00",
        }, headers=h)
        api_post("/api/workouts", {
            "sport_id": 1, "duration": 3600, "distance": 30.0,
            "workout_date": "2024-07-11 09:00:00",
        }, headers=h)
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 2400, "distance": 8.0,
            "workout_date": "2024-07-12 07:00:00",
        }, headers=h)

        # Filter for running only (sport 5)
        resp = api_get("/api/workouts", params={"sport_id": 5, "per_page": 50}, headers=h)
        assert resp.status_code == 200
        workouts = resp.json()["data"]["workouts"]
        assert len(workouts) == 2
        for w in workouts:
            assert w["sport_id"] == 5

        # Filter for cycling only (sport 1)
        resp2 = api_get("/api/workouts", params={"sport_id": 1, "per_page": 50}, headers=h)
        workouts2 = resp2.json()["data"]["workouts"]
        assert len(workouts2) == 1
        assert workouts2[0]["sport_id"] == 1


class TestWorkoutFilterByDateRange:
    """Pattern 3: Verify date range filter actually works."""

    def test_from_to_filters_applied(self):
        h = headers_for()
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 1800, "distance": 5.0,
            "workout_date": "2024-01-15 08:00:00",
        }, headers=h)
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 1800, "distance": 5.0,
            "workout_date": "2024-03-20 08:00:00",
        }, headers=h)
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 1800, "distance": 5.0,
            "workout_date": "2024-06-10 08:00:00",
        }, headers=h)

        # Filter March only
        resp = api_get("/api/workouts", params={
            "from": "2024-03-01", "to": "2024-03-31", "per_page": 50
        }, headers=h)
        assert resp.status_code == 200
        workouts = resp.json()["data"]["workouts"]
        assert len(workouts) == 1
        assert "2024-03" in workouts[0]["workout_date"]

        # Pagination total should match filtered count
        assert resp.json()["pagination"]["total"] == 1


class TestWorkoutOrderByDistance:
    """Pattern 3: Verify order_by=distance actually sorts results."""

    def test_distance_ordering_asc_and_desc(self):
        h = headers_for()
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 1800, "distance": 15.0,
            "workout_date": "2024-08-01 08:00:00",
        }, headers=h)
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 1200, "distance": 3.0,
            "workout_date": "2024-08-02 08:00:00",
        }, headers=h)
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 2400, "distance": 25.0,
            "workout_date": "2024-08-03 08:00:00",
        }, headers=h)

        # ASC
        resp = api_get("/api/workouts", params={
            "order_by": "distance", "order": "asc", "per_page": 50
        }, headers=h)
        workouts = resp.json()["data"]["workouts"]
        distances = [w["distance"] for w in workouts]
        assert distances == sorted(distances)

        # DESC
        resp2 = api_get("/api/workouts", params={
            "order_by": "distance", "order": "desc", "per_page": 50
        }, headers=h)
        workouts2 = resp2.json()["data"]["workouts"]
        distances2 = [w["distance"] for w in workouts2]
        assert distances2 == sorted(distances2, reverse=True)


class TestWorkoutOrderByAveSpeed:
    """Pattern 3: Verify order_by=ave_speed works."""

    def test_ave_speed_ordering(self):
        h = headers_for()
        # Different speeds: 10/1=10, 20/1=20, 5/1=5
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-08-10 08:00:00",
        }, headers=h)
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 20.0,
            "workout_date": "2024-08-11 08:00:00",
        }, headers=h)
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 5.0,
            "workout_date": "2024-08-12 08:00:00",
        }, headers=h)

        resp = api_get("/api/workouts", params={
            "order_by": "ave_speed", "order": "asc", "per_page": 50
        }, headers=h)
        workouts = resp.json()["data"]["workouts"]
        speeds = [w["ave_speed"] for w in workouts]
        assert speeds == sorted(speeds)


class TestRecordFieldNamesAndValues:
    """Pattern 1+5: Verify record response fields use correct names and compute real values."""

    def test_record_response_structure(self):
        h = headers_for()
        # Create workout to generate records
        resp = api_post("/api/workouts", {
            "sport_id": 5, "duration": 5400, "distance": 15.0,
            "workout_date": "2024-08-15 08:00:00",
            "ascent": 200.0,
        }, headers=h)
        assert resp.status_code == 201
        workout_id = resp.json()["data"]["workouts"][0]["id"]

        rec_resp = api_get("/api/records", headers=h)
        assert rec_resp.status_code == 200
        records = rec_resp.json()["data"]["records"]

        # Should have FD, LD, MS, HA records for sport 5
        sport5_recs = {r["record_type"]: r for r in records if r["sport_id"] == 5}
        assert "FD" in sport5_recs
        assert "LD" in sport5_recs
        assert "MS" in sport5_recs
        assert "HA" in sport5_recs

        # Verify field names (snake_case)
        fd = sport5_recs["FD"]
        assert "id" in fd
        assert "record_type" in fd
        assert "sport_id" in fd
        assert "user" in fd
        assert "value" in fd
        assert "workout_date" in fd
        assert "workout_id" in fd

        # Verify NOT camelCase
        assert "recordType" not in fd
        assert "sportId" not in fd
        assert "workoutDate" not in fd
        assert "workoutId" not in fd

        # Verify values
        assert abs(fd["value"] - 15.0) < 0.01
        assert fd["workout_id"] == workout_id
        # LD value should be string "1:30:00"
        assert sport5_recs["LD"]["value"] == "1:30:00"
        # MS = 15 / (5400/3600) = 15 / 1.5 = 10.0
        assert abs(sport5_recs["MS"]["value"] - 10.0) < 0.01
        # HA = 200.0
        assert abs(sport5_recs["HA"]["value"] - 200.0) < 0.01


class TestStatsBySportComputation:
    """Pattern 5: Verify statistics are actually computed from workouts, not dummy data."""

    def test_stats_reflect_actual_workout_data(self):
        h = headers_for()
        username = get_username(h)

        # Create known workouts
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-09-01 08:00:00",
            "ascent": 100.0, "descent": 50.0,
        }, headers=h)
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 1800, "distance": 6.0,
            "workout_date": "2024-09-02 08:00:00",
            "ascent": 30.0, "descent": 20.0,
        }, headers=h)
        api_post("/api/workouts", {
            "sport_id": 1, "duration": 7200, "distance": 50.0,
            "workout_date": "2024-09-03 09:00:00",
        }, headers=h)

        resp = api_get(f"/api/stats/{username}/by_sport", headers=h)
        assert resp.status_code == 200
        stats = resp.json()["data"]["statistics"]

        # Running (sport 5): 2 workouts, 16km, 5400s, 130m ascent, 70m descent
        assert "5" in stats
        s5 = stats["5"]
        assert s5["nb_workouts"] == 2
        assert abs(s5["total_distance"] - 16.0) < 0.01
        assert s5["total_duration"] == 5400
        assert abs(s5["total_ascent"] - 130.0) < 0.01
        assert abs(s5["total_descent"] - 70.0) < 0.01

        # Cycling (sport 1): 1 workout, 50km, 7200s
        assert "1" in stats
        s1 = stats["1"]
        assert s1["nb_workouts"] == 1
        assert abs(s1["total_distance"] - 50.0) < 0.01
        assert s1["total_duration"] == 7200


class TestStatsByTimeMonthStructure:
    """Pattern 2+5: Verify nested time stats structure is correct."""

    def test_month_grouping_nested_structure(self):
        h = headers_for()
        username = get_username(h)

        api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-05-10 08:00:00",
        }, headers=h)
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 1800, "distance": 5.0,
            "workout_date": "2024-05-20 08:00:00",
        }, headers=h)
        api_post("/api/workouts", {
            "sport_id": 1, "duration": 3600, "distance": 30.0,
            "workout_date": "2024-06-05 09:00:00",
        }, headers=h)

        resp = api_get(f"/api/stats/{username}/by_time", params={"time": "month"}, headers=h)
        assert resp.status_code == 200
        stats = resp.json()["data"]["statistics"]

        # Structure: { "2024": { "5": { "5": {...} }, "6": { "1": {...} } } }
        assert "2024" in stats
        assert "5" in stats["2024"]  # May
        assert "5" in stats["2024"]["5"]  # sport_id 5
        may_s5 = stats["2024"]["5"]["5"]
        assert may_s5["nb_workouts"] == 2
        assert abs(may_s5["total_distance"] - 15.0) < 0.01
        assert may_s5["total_duration"] == 5400

        assert "6" in stats["2024"]  # June
        assert "1" in stats["2024"]["6"]  # sport_id 1
        jun_s1 = stats["2024"]["6"]["1"]
        assert jun_s1["nb_workouts"] == 1
        assert abs(jun_s1["total_distance"] - 30.0) < 0.01


class TestEquipmentNestedTypeInResponse:
    """Pattern 2: Verify equipment_type is embedded as object, not just an ID."""

    def test_equipment_type_is_nested_object(self):
        h = headers_for()
        resp = api_post("/api/equipments", {
            "label": "Nested Type Shoe",
            "equipment_type_id": 1,
            "description": "For testing nested type",
        }, headers=h)
        assert resp.status_code == 201
        e = resp.json()["data"]["equipments"][0]

        # equipment_type should be an object with id, label, is_active
        assert "equipment_type" in e
        et = e["equipment_type"]
        assert isinstance(et, dict)
        assert et["id"] == 1
        assert et["label"] == "Shoe"
        assert "is_active" in et

        # Verify on GET too
        eq_id = e["id"]
        get_resp = api_get(f"/api/equipments/{eq_id}", headers=h)
        e2 = get_resp.json()["data"]["equipments"][0]
        assert isinstance(e2["equipment_type"], dict)
        assert e2["equipment_type"]["id"] == 1


class TestEquipmentAccumulationAfterLink:
    """Pattern 5+7: Verify equipment totals are actually computed from linked workouts."""

    def test_totals_computed_not_static(self):
        h = headers_for()
        eq_resp = api_post("/api/equipments", {
            "label": "Compute Shoes",
            "equipment_type_id": 1,
        }, headers=h)
        equip_id = eq_resp.json()["data"]["equipments"][0]["id"]

        # Verify starts at 0
        eq = api_get(f"/api/equipments/{equip_id}", headers=h).json()["data"]["equipments"][0]
        assert eq["total_distance"] == 0
        assert eq["total_duration"] == 0
        assert eq["workouts_count"] == 0

        # Create and link
        w_resp = api_post("/api/workouts", {
            "sport_id": 5, "duration": 2700, "distance": 8.5,
            "workout_date": "2024-09-15 08:00:00",
        }, headers=h)
        w_id = w_resp.json()["data"]["workouts"][0]["id"]
        link_resp = api_post(f"/api/workouts/{w_id}/equipments/{equip_id}", headers=h)
        assert link_resp.status_code == 200

        # Check updated totals
        eq2 = api_get(f"/api/equipments/{equip_id}", headers=h).json()["data"]["equipments"][0]
        assert abs(eq2["total_distance"] - 8.5) < 0.01
        assert eq2["total_duration"] == 2700
        assert eq2["workouts_count"] == 1


class TestEquipmentOnWorkoutResponse:
    """Pattern 2: Verify equipment summary appears in workout response after linking."""

    def test_workout_equipments_list_populated(self):
        h = headers_for()
        eq_resp = api_post("/api/equipments", {
            "label": "Workout Embed Shoe",
            "equipment_type_id": 1,
        }, headers=h)
        equip_id = eq_resp.json()["data"]["equipments"][0]["id"]

        w_resp = api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-09-16 08:00:00",
        }, headers=h)
        w_id = w_resp.json()["data"]["workouts"][0]["id"]
        # Before link, equipments should be empty
        w_before = api_get(f"/api/workouts/{w_id}", headers=h).json()["data"]["workouts"][0]
        assert w_before["equipments"] == []

        # Link
        api_post(f"/api/workouts/{w_id}/equipments/{equip_id}", headers=h)

        # After link, equipment should appear with id, label, equipment_type
        w_after = api_get(f"/api/workouts/{w_id}", headers=h).json()["data"]["workouts"][0]
        assert len(w_after["equipments"]) == 1
        eq_summary = w_after["equipments"][0]
        assert eq_summary["id"] == equip_id
        assert eq_summary["label"] == "Workout Embed Shoe"
        assert "equipment_type" in eq_summary
        assert eq_summary["equipment_type"]["id"] == 1


class TestProfileComputedFields:
    """Pattern 5: Verify profile stats are computed from actual workout data."""

    def test_profile_stats_computed_correctly(self):
        h = headers_for()
        # Fresh user - should have 0 everything
        profile = api_get("/api/auth/profile", headers=h).json()["data"]
        assert profile["nb_workouts"] == 0
        assert profile["nb_sports"] == 0
        assert profile["total_distance"] == 0
        assert profile["total_duration"] == "0:00:00"
        assert profile["sports_list"] == []

        # Create workouts in 2 sports
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-10-01 08:00:00",
        }, headers=h)
        api_post("/api/workouts", {
            "sport_id": 1, "duration": 5400, "distance": 35.0,
            "workout_date": "2024-10-02 09:00:00",
        }, headers=h)

        profile2 = api_get("/api/auth/profile", headers=h).json()["data"]
        assert profile2["nb_workouts"] == 2
        assert profile2["nb_sports"] == 2
        assert abs(profile2["total_distance"] - 45.0) < 0.01
        # 3600 + 5400 = 9000s = 2:30:00
        assert profile2["total_duration"] == "2:30:00"
        assert set(profile2["sports_list"]) == {1, 5}


class TestSportDeactivationBlocksWorkout:
    """Pattern 5: Verify that deactivating a sport actually prevents workout creation."""

    def test_inactive_sport_rejected(self):
        admin_h = make_admin_headers()
        # Ensure admin user is created first
        api_get("/api/auth/profile", headers=admin_h)
        user_h = headers_for()

        try:
            # Deactivate sport 7 (Trail)
            resp = api_patch("/api/sports/7", {"is_active": False}, headers=admin_h)
            assert resp.status_code == 200
            assert resp.json()["data"]["sports"][0]["is_active"] is False

            # Try to create workout with sport 7
            w_resp = api_post("/api/workouts", {
                "sport_id": 7, "duration": 3600, "distance": 10.0,
                "workout_date": "2024-10-05 08:00:00",
            }, headers=user_h)
            assert w_resp.status_code == 400
        finally:
            api_patch("/api/sports/7", {"is_active": True}, headers=admin_h)


class TestCreateWorkoutStatus201:
    """Pattern 4: Verify POST workout returns 201, not 200."""

    def test_create_returns_201(self):
        h = headers_for()
        resp = api_post("/api/workouts", {
            "sport_id": 5, "duration": 1800, "distance": 5.0,
            "workout_date": "2024-10-10 08:00:00",
        }, headers=h)
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}"
        assert resp.json()["status"] == "success"


class TestDeleteWorkoutStatus204:
    """Pattern 4: Verify DELETE workout returns 204, not 200."""

    def test_delete_returns_204(self):
        h = headers_for()
        resp = api_post("/api/workouts", {
            "sport_id": 5, "duration": 1800, "distance": 5.0,
            "workout_date": "2024-10-11 08:00:00",
        }, headers=h)
        w_id = resp.json()["data"]["workouts"][0]["id"]

        del_resp = api_delete(f"/api/workouts/{w_id}", headers=h)
        assert del_resp.status_code == 204, f"Expected 204, got {del_resp.status_code}"


class TestWorkoutNotFound404:
    """Pattern 4: Verify non-existent workout returns 404, not 200 with empty data."""

    def test_get_nonexistent_returns_404(self):
        h = headers_for()
        fake_id = "00000000-0000-0000-0000-ffffffffffff"
        resp = api_get(f"/api/workouts/{fake_id}", headers=h)
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"

    def test_delete_nonexistent_returns_404(self):
        h = headers_for()
        fake_id = "00000000-0000-0000-0000-ffffffffffff"
        resp = api_delete(f"/api/workouts/{fake_id}", headers=h)
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"

    def test_patch_nonexistent_returns_404(self):
        h = headers_for()
        fake_id = "00000000-0000-0000-0000-ffffffffffff"
        resp = api_patch(f"/api/workouts/{fake_id}", {"title": "nope"}, headers=h)
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"


class TestEquipmentDeleteBlocked400:
    """Pattern 4+5: Cannot delete equipment with linked workouts — returns 400."""

    def test_delete_with_linked_workout_returns_400(self):
        h = headers_for()
        eq_resp = api_post("/api/equipments", {
            "label": "Block Delete Shoe",
            "equipment_type_id": 1,
        }, headers=h)
        equip_id = eq_resp.json()["data"]["equipments"][0]["id"]

        w_resp = api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-10-12 08:00:00",
        }, headers=h)
        w_id = w_resp.json()["data"]["workouts"][0]["id"]
        api_post(f"/api/workouts/{w_id}/equipments/{equip_id}", headers=h)

        # Try delete
        del_resp = api_delete(f"/api/equipments/{equip_id}", headers=h)
        assert del_resp.status_code == 400

        # Equipment should still exist
        get_resp = api_get(f"/api/equipments/{equip_id}", headers=h)
        assert get_resp.status_code == 200


class TestWorkoutMovingAndPauses:
    """Pattern 1+2: For no-GPX workouts, moving=duration, pauses=null."""

    def test_moving_equals_duration_and_pauses_null(self):
        h = headers_for()
        resp = api_post("/api/workouts", {
            "sport_id": 5, "duration": 4500, "distance": 12.0,
            "workout_date": "2024-10-15 08:00:00",
        }, headers=h)
        assert resp.status_code == 201
        w = resp.json()["data"]["workouts"][0]
        # moving should equal duration string: 4500s = 1:15:00
        assert w["moving"] == "1:15:00"
        assert w["pauses"] is None


class TestRecordLDValueFormat:
    """Pattern 1: LD record value must be string 'H:MM:SS', not integer seconds."""

    def test_ld_value_is_formatted_string(self):
        h = headers_for()
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 7261, "distance": 20.0,
            "workout_date": "2024-10-16 06:00:00",
        }, headers=h)

        records = api_get("/api/records", headers=h).json()["data"]["records"]
        ld_records = [r for r in records if r["record_type"] == "LD" and r["sport_id"] == 5]
        assert len(ld_records) >= 1
        ld = ld_records[0]
        # 7261s = 2:01:01
        assert ld["value"] == "2:01:01"
        assert isinstance(ld["value"], str)


class TestWorkoutTitleFilter:
    """Pattern 3: Verify title filter (case-insensitive partial match) works."""

    def test_title_filter_partial_case_insensitive(self):
        h = headers_for()
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 1800, "distance": 5.0,
            "workout_date": "2024-10-20 08:00:00",
            "title": "Morning Jog in the Park",
        }, headers=h)
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-10-21 08:00:00",
            "title": "Evening Sprint",
        }, headers=h)
        api_post("/api/workouts", {
            "sport_id": 1, "duration": 5400, "distance": 30.0,
            "workout_date": "2024-10-22 09:00:00",
            "title": "Park Cycling Route",
        }, headers=h)

        # Filter by "park" (case insensitive) should match 2
        resp = api_get("/api/workouts", params={"title": "park", "per_page": 50}, headers=h)
        assert resp.status_code == 200
        workouts = resp.json()["data"]["workouts"]
        assert len(workouts) == 2
        titles = [w["title"] for w in workouts]
        assert any("Park" in t for t in titles)


class TestStatsByTimeYearGrouping:
    """Pattern 2+5: Year grouping uses empty string as period key."""

    def test_year_grouping_uses_empty_key(self):
        h = headers_for()
        username = get_username(h)

        api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-02-10 08:00:00",
        }, headers=h)
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 1800, "distance": 5.0,
            "workout_date": "2024-11-20 08:00:00",
        }, headers=h)

        resp = api_get(f"/api/stats/{username}/by_time", params={"time": "year"}, headers=h)
        assert resp.status_code == 200
        stats = resp.json()["data"]["statistics"]
        assert "2024" in stats
        # Year grouping: inner key is empty string ""
        assert "" in stats["2024"]
        year_data = stats["2024"][""]
        assert "5" in year_data
        assert year_data["5"]["nb_workouts"] == 2
        assert abs(year_data["5"]["total_distance"] - 15.0) < 0.01
        assert year_data["5"]["total_duration"] == 5400


class TestCreateEquipmentStatus201:
    """Pattern 4: POST equipment returns 201."""

    def test_create_equipment_returns_201(self):
        h = headers_for()
        resp = api_post("/api/equipments", {
            "label": "Status Test Shoe",
            "equipment_type_id": 1,
        }, headers=h)
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}"


class TestUnlinkEquipmentStatus204:
    """Pattern 4: DELETE equipment link returns 204."""

    def test_unlink_returns_204(self):
        h = headers_for()
        eq_resp = api_post("/api/equipments", {
            "label": "Unlink Status Shoe",
            "equipment_type_id": 1,
        }, headers=h)
        equip_id = eq_resp.json()["data"]["equipments"][0]["id"]

        w_resp = api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-10-25 08:00:00",
        }, headers=h)
        w_id = w_resp.json()["data"]["workouts"][0]["id"]
        api_post(f"/api/workouts/{w_id}/equipments/{equip_id}", headers=h)

        # Unlink
        del_resp = api_delete(f"/api/workouts/{w_id}/equipments/{equip_id}", headers=h)
        assert del_resp.status_code == 204, f"Expected 204, got {del_resp.status_code}"


class TestAdminPermissionEnforced:
    """Pattern 6: Non-admin cannot update sports."""

    def test_non_admin_sport_update_returns_403(self):
        # Ensure admin exists
        admin_h = make_admin_headers()
        api_get("/api/auth/profile", headers=admin_h)

        # Non-admin user
        non_admin_h = headers_for()
        api_get("/api/auth/profile", headers=non_admin_h)
        profile = api_get("/api/auth/profile", headers=non_admin_h).json()["data"]
        assert profile["is_admin"] is False

        try:
            # Try to toggle sport
            resp = api_patch("/api/sports/1", {"is_active": False}, headers=non_admin_h)
            assert resp.status_code == 403
        finally:
            api_patch("/api/sports/1", {"is_active": True}, headers=admin_h)


class TestEquipmentFilterByType:
    """Pattern 3: Verify equipment_type_id filter is implemented."""

    def test_filter_by_equipment_type(self):
        h = headers_for()
        api_post("/api/equipments", {"label": "Filter Shoe A", "equipment_type_id": 1}, headers=h)
        api_post("/api/equipments", {"label": "Filter Bike A", "equipment_type_id": 2}, headers=h)
        api_post("/api/equipments", {"label": "Filter Shoe B", "equipment_type_id": 1}, headers=h)

        # Filter shoes only
        resp = api_get("/api/equipments", params={"equipment_type_id": 1}, headers=h)
        assert resp.status_code == 200
        equips = resp.json()["data"]["equipments"]
        assert len(equips) == 2
        for e in equips:
            assert e["equipment_type"]["id"] == 1

        # Filter bikes only
        resp2 = api_get("/api/equipments", params={"equipment_type_id": 2}, headers=h)
        equips2 = resp2.json()["data"]["equipments"]
        assert len(equips2) == 1
        assert equips2[0]["equipment_type"]["id"] == 2
