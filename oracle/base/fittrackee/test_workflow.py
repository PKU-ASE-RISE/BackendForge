"""
BackendForge - L3 Workflow Tests for FitTrackee Task

Complex multi-step workflows crossing 3+ entity types, targeting:
- Pattern 2+5+7: Nested data + real business logic + cascade side-effects
- Pattern 3+6: Filter enforcement + data isolation
- Pattern 1+4+5: Field naming + status codes + computation accuracy

Each test: 6-12 steps, 12-20 assertions, 3+ entity types.
"""

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


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
    return {"X-User-Id": "00000000-0000-0000-0000-000000000001", "Content-Type": "application/json"}


# ================================================================
# L3 Workflow Tests
# ================================================================


class TestWorkoutLifecycleWithRecordsAndStats:
    """Pattern 5+7: Full workout lifecycle verifying records and stats update at each step."""

    def test_create_update_delete_with_record_and_stat_tracking(self):
        h = headers_for()
        username = get_username(h)

        # Step 1: Create first workout (10km running in 1h)
        r1 = api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-05-01 08:00:00",
            "ascent": 50.0, "descent": 30.0,
        }, headers=h)
        assert r1.status_code == 201
        w1_id = r1.json()["data"]["workouts"][0]["id"]

        # Step 2: Verify records created
        recs = api_get("/api/records", headers=h).json()["data"]["records"]
        s5_recs = {r["record_type"]: r for r in recs if r["sport_id"] == 5}
        assert abs(s5_recs["FD"]["value"] - 10.0) < 0.01
        assert s5_recs["LD"]["value"] == "1:00:00"
        assert abs(s5_recs["MS"]["value"] - 10.0) < 0.01
        assert abs(s5_recs["HA"]["value"] - 50.0) < 0.01

        # Step 3: Create a BETTER workout (20km running in 1.5h)
        r2 = api_post("/api/workouts", {
            "sport_id": 5, "duration": 5400, "distance": 20.0,
            "workout_date": "2024-05-05 08:00:00",
            "ascent": 200.0, "descent": 150.0,
        }, headers=h)
        assert r2.status_code == 201
        w2_id = r2.json()["data"]["workouts"][0]["id"]

        # Step 4: Verify records updated to reflect better workout
        recs2 = api_get("/api/records", headers=h).json()["data"]["records"]
        s5_recs2 = {r["record_type"]: r for r in recs2 if r["sport_id"] == 5}
        assert abs(s5_recs2["FD"]["value"] - 20.0) < 0.01
        assert s5_recs2["FD"]["workout_id"] == w2_id
        assert s5_recs2["LD"]["value"] == "1:30:00"
        assert s5_recs2["LD"]["workout_id"] == w2_id
        # MS: workout 2 = 20/1.5 = 13.33, workout 1 = 10/1 = 10 -> record = 13.33
        assert abs(s5_recs2["MS"]["value"] - (20.0 / 1.5)) < 0.01
        assert abs(s5_recs2["HA"]["value"] - 200.0) < 0.01

        # Step 5: Verify stats by sport
        stats = api_get(f"/api/stats/{username}/by_sport", headers=h).json()["data"]["statistics"]
        assert stats["5"]["nb_workouts"] == 2
        assert abs(stats["5"]["total_distance"] - 30.0) < 0.01
        assert stats["5"]["total_duration"] == 9000
        assert abs(stats["5"]["total_ascent"] - 250.0) < 0.01

        # Step 6: Delete the record-holding workout
        del_resp = api_delete(f"/api/workouts/{w2_id}", headers=h)
        assert del_resp.status_code == 204

        # Step 7: Verify records reverted to first workout
        recs3 = api_get("/api/records", headers=h).json()["data"]["records"]
        s5_recs3 = {r["record_type"]: r for r in recs3 if r["sport_id"] == 5}
        assert abs(s5_recs3["FD"]["value"] - 10.0) < 0.01
        assert s5_recs3["FD"]["workout_id"] == w1_id
        assert s5_recs3["LD"]["value"] == "1:00:00"

        # Step 8: Verify stats updated
        stats2 = api_get(f"/api/stats/{username}/by_sport", headers=h).json()["data"]["statistics"]
        assert stats2["5"]["nb_workouts"] == 1
        assert abs(stats2["5"]["total_distance"] - 10.0) < 0.01

        # Step 9: Verify profile reflects changes
        profile = api_get("/api/auth/profile", headers=h).json()["data"]
        assert profile["nb_workouts"] == 1
        assert abs(profile["total_distance"] - 10.0) < 0.01


class TestEquipmentLifecycleWithWorkouts:
    """Pattern 2+5+7: Equipment accumulation across multiple workouts, with updates and deletes."""

    def test_equipment_totals_track_all_operations(self):
        h = headers_for()

        # Step 1: Create equipment
        eq_resp = api_post("/api/equipments", {
            "label": "Marathon Shoes",
            "equipment_type_id": 1,
            "description": "For long runs",
        }, headers=h)
        assert eq_resp.status_code == 201
        equip_id = eq_resp.json()["data"]["equipments"][0]["id"]

        # Step 2: Create 3 workouts and link them
        workouts = []
        for i, (dist, dur) in enumerate([(10.0, 3600), (15.0, 5400), (8.0, 2700)]):
            w = api_post("/api/workouts", {
                "sport_id": 5, "duration": dur, "distance": dist,
                "workout_date": f"2024-06-{i+1:02d} 08:00:00",
            }, headers=h)
            w_id = w.json()["data"]["workouts"][0]["id"]
            link = api_post(f"/api/workouts/{w_id}/equipments/{equip_id}", headers=h)
            assert link.status_code == 200
            workouts.append(w_id)

        # Step 3: Verify accumulated totals (10+15+8=33km, 3600+5400+2700=11700s, 3 workouts)
        eq = api_get(f"/api/equipments/{equip_id}", headers=h).json()["data"]["equipments"][0]
        assert abs(eq["total_distance"] - 33.0) < 0.01
        assert eq["total_duration"] == 11700
        assert eq["workouts_count"] == 3

        # Step 4: Update middle workout distance from 15 to 25
        api_patch(f"/api/workouts/{workouts[1]}", {"distance": 25.0}, headers=h)

        # Step 5: Verify equipment totals updated (10+25+8=43km)
        eq2 = api_get(f"/api/equipments/{equip_id}", headers=h).json()["data"]["equipments"][0]
        assert abs(eq2["total_distance"] - 43.0) < 0.01

        # Step 6: Unlink first workout
        unlink = api_delete(f"/api/workouts/{workouts[0]}/equipments/{equip_id}", headers=h)
        assert unlink.status_code == 204

        # Step 7: Verify totals decreased (25+8=33km, 5400+2700=8100s, 2 workouts)
        eq3 = api_get(f"/api/equipments/{equip_id}", headers=h).json()["data"]["equipments"][0]
        assert abs(eq3["total_distance"] - 33.0) < 0.01
        assert eq3["total_duration"] == 8100
        assert eq3["workouts_count"] == 2

        # Step 8: Delete one linked workout entirely
        api_delete(f"/api/workouts/{workouts[2]}", headers=h)

        # Step 9: Verify totals reflect deletion (only workout[1] remains: 25km, 5400s)
        eq4 = api_get(f"/api/equipments/{equip_id}", headers=h).json()["data"]["equipments"][0]
        assert abs(eq4["total_distance"] - 25.0) < 0.01
        assert eq4["total_duration"] == 5400
        assert eq4["workouts_count"] == 1

        # Step 10: Cannot delete equipment with linked workout
        del_resp = api_delete(f"/api/equipments/{equip_id}", headers=h)
        assert del_resp.status_code == 400


class TestMultiUserIsolationComplete:
    """Pattern 6: Full data isolation between users across workouts, equipment, records, stats."""

    def test_user_a_and_b_fully_isolated(self):
        h_a = headers_for()
        h_b = headers_for()
        username_a = get_username(h_a)
        username_b = get_username(h_b)

        # Step 1: User A creates workout
        wa = api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-07-01 08:00:00",
            "ascent": 100.0,
        }, headers=h_a)
        assert wa.status_code == 201
        wa_id = wa.json()["data"]["workouts"][0]["id"]

        # Step 2: User B creates different workout
        wb = api_post("/api/workouts", {
            "sport_id": 1, "duration": 7200, "distance": 50.0,
            "workout_date": "2024-07-02 09:00:00",
        }, headers=h_b)
        assert wb.status_code == 201
        wb_id = wb.json()["data"]["workouts"][0]["id"]

        # Step 3: User B cannot access User A's workout
        resp = api_get(f"/api/workouts/{wa_id}", headers=h_b)
        assert resp.status_code == 404

        # Step 4: User A cannot access User B's workout
        resp = api_get(f"/api/workouts/{wb_id}", headers=h_a)
        assert resp.status_code == 404

        # Step 5: User A's workout list has only their workout
        list_a = api_get("/api/workouts", params={"per_page": 50}, headers=h_a)
        a_ids = [w["id"] for w in list_a.json()["data"]["workouts"]]
        assert wa_id in a_ids
        assert wb_id not in a_ids

        # Step 6: Records are isolated
        recs_a = api_get("/api/records", headers=h_a).json()["data"]["records"]
        recs_b = api_get("/api/records", headers=h_b).json()["data"]["records"]
        a_sports = {r["sport_id"] for r in recs_a}
        b_sports = {r["sport_id"] for r in recs_b}
        assert 5 in a_sports  # User A has running records
        assert 5 not in b_sports  # User B does not
        assert 1 in b_sports  # User B has cycling records
        assert 1 not in a_sports  # User A does not

        # Step 7: Stats are isolated
        stats_a = api_get(f"/api/stats/{username_a}/by_sport", headers=h_a).json()["data"]["statistics"]
        assert "5" in stats_a
        assert "1" not in stats_a

        stats_b = api_get(f"/api/stats/{username_b}/by_sport", headers=h_b).json()["data"]["statistics"]
        assert "1" in stats_b
        assert "5" not in stats_b

        # Step 8: User B cannot delete User A's workout
        del_resp = api_delete(f"/api/workouts/{wa_id}", headers=h_b)
        assert del_resp.status_code == 404

        # Step 9: User A's equipment is isolated
        eq_a = api_post("/api/equipments", {
            "label": "A's Shoes", "equipment_type_id": 1,
        }, headers=h_a)
        eq_a_id = eq_a.json()["data"]["equipments"][0]["id"]

        eq_get_b = api_get(f"/api/equipments/{eq_a_id}", headers=h_b)
        assert eq_get_b.status_code == 404

        # Step 10: User B cannot link User A's equipment to their workout
        link = api_post(f"/api/workouts/{wb_id}/equipments/{eq_a_id}", headers=h_b)
        assert link.status_code in [403, 404]

        # Step 11: Profile stats are independent
        profile_a = api_get("/api/auth/profile", headers=h_a).json()["data"]
        profile_b = api_get("/api/auth/profile", headers=h_b).json()["data"]
        assert profile_a["nb_workouts"] == 1
        assert profile_b["nb_workouts"] == 1
        assert abs(profile_a["total_distance"] - 10.0) < 0.01
        assert abs(profile_b["total_distance"] - 50.0) < 0.01


class TestRecordRecalculationOnWorkoutUpdate:
    """Pattern 5+7: Records must recalculate when workouts are updated."""

    def test_records_shift_correctly_on_updates(self):
        h = headers_for()

        # Step 1: Create workout A (10km, 3600s, ascent 100)
        ra = api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-08-01 08:00:00",
            "ascent": 100.0,
        }, headers=h)
        wa_id = ra.json()["data"]["workouts"][0]["id"]

        # Step 2: Create workout B (20km, 5400s, ascent 200) - all records go to B
        rb = api_post("/api/workouts", {
            "sport_id": 5, "duration": 5400, "distance": 20.0,
            "workout_date": "2024-08-05 08:00:00",
            "ascent": 200.0,
        }, headers=h)
        wb_id = rb.json()["data"]["workouts"][0]["id"]

        # Step 3: Verify B holds all records
        recs = api_get("/api/records", headers=h).json()["data"]["records"]
        s5 = {r["record_type"]: r for r in recs if r["sport_id"] == 5}
        assert s5["FD"]["workout_id"] == wb_id
        assert s5["LD"]["workout_id"] == wb_id
        assert s5["HA"]["workout_id"] == wb_id

        # Step 4: Update workout B to have LESS distance than A (5km)
        api_patch(f"/api/workouts/{wb_id}", {"distance": 5.0}, headers=h)

        # Step 5: FD record should now belong to A (10km > 5km)
        recs2 = api_get("/api/records", headers=h).json()["data"]["records"]
        s5_2 = {r["record_type"]: r for r in recs2 if r["sport_id"] == 5}
        assert abs(s5_2["FD"]["value"] - 10.0) < 0.01
        assert s5_2["FD"]["workout_id"] == wa_id

        # Step 6: LD should still belong to B (5400s > 3600s)
        assert s5_2["LD"]["workout_id"] == wb_id
        assert s5_2["LD"]["value"] == "1:30:00"

        # Step 7: MS recalculated: A = 10/1 = 10, B = 5/1.5 = 3.33 -> A wins
        assert abs(s5_2["MS"]["value"] - 10.0) < 0.01
        assert s5_2["MS"]["workout_id"] == wa_id

        # Step 8: HA still B (200 > 100)
        assert abs(s5_2["HA"]["value"] - 200.0) < 0.01
        assert s5_2["HA"]["workout_id"] == wb_id


class TestWorkoutWithEquipmentIdsCreateAndUpdate:
    """Pattern 2+5+7: Workout creation/update with equipment_ids triggers proper linking and accumulation."""

    def test_equipment_ids_on_create_and_update(self):
        h = headers_for()

        # Step 1: Create two equipments
        eq1 = api_post("/api/equipments", {"label": "Shoes Alpha", "equipment_type_id": 1}, headers=h)
        eq1_id = eq1.json()["data"]["equipments"][0]["id"]
        eq2 = api_post("/api/equipments", {"label": "Shoes Beta", "equipment_type_id": 1}, headers=h)
        eq2_id = eq2.json()["data"]["equipments"][0]["id"]

        # Step 2: Create workout with eq1 linked
        w = api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 12.0,
            "workout_date": "2024-09-01 08:00:00",
            "equipment_ids": [eq1_id],
        }, headers=h)
        assert w.status_code == 201
        w_id = w.json()["data"]["workouts"][0]["id"]
        assert len(w.json()["data"]["workouts"][0]["equipments"]) == 1
        assert w.json()["data"]["workouts"][0]["equipments"][0]["id"] == eq1_id

        # Step 3: Verify eq1 accumulated
        e1 = api_get(f"/api/equipments/{eq1_id}", headers=h).json()["data"]["equipments"][0]
        assert abs(e1["total_distance"] - 12.0) < 0.01
        assert e1["workouts_count"] == 1

        # Step 4: eq2 should have zero
        e2 = api_get(f"/api/equipments/{eq2_id}", headers=h).json()["data"]["equipments"][0]
        assert e2["total_distance"] == 0
        assert e2["workouts_count"] == 0

        # Step 5: Update workout to switch from eq1 to eq2
        upd = api_patch(f"/api/workouts/{w_id}", {
            "equipment_ids": [eq2_id],
        }, headers=h)
        assert upd.status_code == 200
        assert len(upd.json()["data"]["workouts"][0]["equipments"]) == 1
        assert upd.json()["data"]["workouts"][0]["equipments"][0]["id"] == eq2_id

        # Step 6: eq1 should be back to zero
        e1_after = api_get(f"/api/equipments/{eq1_id}", headers=h).json()["data"]["equipments"][0]
        assert e1_after["total_distance"] == 0
        assert e1_after["workouts_count"] == 0

        # Step 7: eq2 should now have the totals
        e2_after = api_get(f"/api/equipments/{eq2_id}", headers=h).json()["data"]["equipments"][0]
        assert abs(e2_after["total_distance"] - 12.0) < 0.01
        assert e2_after["workouts_count"] == 1

        # Step 8: Update workout distance - eq2 should reflect new distance
        api_patch(f"/api/workouts/{w_id}", {"distance": 20.0}, headers=h)
        e2_final = api_get(f"/api/equipments/{eq2_id}", headers=h).json()["data"]["equipments"][0]
        assert abs(e2_final["total_distance"] - 20.0) < 0.01


class TestStatsByTimeWithFilters:
    """Pattern 3+5: Verify by_time stats support sport_id and date filters."""

    def test_by_time_filtered_by_sport_and_date(self):
        h = headers_for()
        username = get_username(h)

        # Step 1: Create workouts across different months and sports
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-03-10 08:00:00",
        }, headers=h)
        api_post("/api/workouts", {
            "sport_id": 1, "duration": 5400, "distance": 30.0,
            "workout_date": "2024-03-15 09:00:00",
        }, headers=h)
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 1800, "distance": 5.0,
            "workout_date": "2024-06-10 08:00:00",
        }, headers=h)
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 2700, "distance": 8.0,
            "workout_date": "2024-09-20 08:00:00",
        }, headers=h)

        # Step 2: Filter by sport_id=5 only
        resp = api_get(f"/api/stats/{username}/by_time", params={
            "time": "month", "sport_id": 5,
        }, headers=h)
        assert resp.status_code == 200
        stats = resp.json()["data"]["statistics"]
        # Should have running workouts only - no cycling in any month
        if "2024" in stats and "3" in stats["2024"]:
            assert "1" not in stats["2024"]["3"]  # No cycling
            assert "5" in stats["2024"]["3"]  # Running present

        # Step 3: Filter by date range (only March)
        resp2 = api_get(f"/api/stats/{username}/by_time", params={
            "time": "month", "from": "2024-03-01", "to": "2024-03-31",
        }, headers=h)
        stats2 = resp2.json()["data"]["statistics"]
        assert "2024" in stats2
        assert "3" in stats2["2024"]
        # Only March data should appear
        if "6" in stats2.get("2024", {}):
            assert False, "June data should not appear in March-only filter"

        # Step 4: Verify correct totals in filtered view
        march_s5 = stats2["2024"]["3"]["5"]
        assert march_s5["nb_workouts"] == 1
        assert abs(march_s5["total_distance"] - 10.0) < 0.01


class TestSportDeactivationWorkflow:
    """Pattern 5+8: Sport deactivation prevents new workouts but doesn't affect existing ones."""

    def test_sport_deactivation_and_reactivation(self):
        admin_h = make_admin_headers()
        user_h = headers_for()
        username = get_username(user_h)

        # Step 1: Create workout with sport 3 (Hiking)
        w = api_post("/api/workouts", {
            "sport_id": 3, "duration": 7200, "distance": 12.0,
            "workout_date": "2024-11-01 07:00:00",
            "ascent": 500.0, "descent": 400.0,
        }, headers=user_h)
        assert w.status_code == 201
        w_id = w.json()["data"]["workouts"][0]["id"]

        try:
            # Step 2: Deactivate sport 3 (admin)
            resp = api_patch("/api/sports/3", {"is_active": False}, headers=admin_h)
            assert resp.status_code == 200
            assert resp.json()["data"]["sports"][0]["is_active"] is False

            # Step 3: Cannot create NEW workout with sport 3
            w2 = api_post("/api/workouts", {
                "sport_id": 3, "duration": 3600, "distance": 5.0,
                "workout_date": "2024-11-05 08:00:00",
            }, headers=user_h)
            assert w2.status_code == 400

            # Step 4: Existing workout still accessible
            get_resp = api_get(f"/api/workouts/{w_id}", headers=user_h)
            assert get_resp.status_code == 200
            assert get_resp.json()["data"]["workouts"][0]["sport_id"] == 3

            # Step 5: Records for sport 3 still exist
            recs = api_get("/api/records", headers=user_h).json()["data"]["records"]
            s3_recs = [r for r in recs if r["sport_id"] == 3]
            assert len(s3_recs) > 0

            # Step 6: Stats still include sport 3 data
            stats = api_get(f"/api/stats/{username}/by_sport", headers=user_h).json()["data"]["statistics"]
            assert "3" in stats
            assert stats["3"]["nb_workouts"] == 1
        finally:
            # Step 7: Re-activate sport 3
            api_patch("/api/sports/3", {"is_active": True}, headers=admin_h)

        # Step 8: Can create workout again
        w3 = api_post("/api/workouts", {
            "sport_id": 3, "duration": 3600, "distance": 5.0,
            "workout_date": "2024-11-10 08:00:00",
        }, headers=user_h)
        assert w3.status_code == 201


class TestDeleteWorkoutCascadeEffects:
    """Pattern 7: Deleting a workout updates records, stats, equipment, and profile."""

    def test_delete_cascades_everywhere(self):
        h = headers_for()
        username = get_username(h)

        # Step 1: Create equipment
        eq = api_post("/api/equipments", {
            "label": "Cascade Test Shoes", "equipment_type_id": 1,
        }, headers=h)
        eq_id = eq.json()["data"]["equipments"][0]["id"]

        # Step 2: Create workout and link equipment
        w = api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-12-01 08:00:00",
            "ascent": 80.0,
            "equipment_ids": [eq_id],
        }, headers=h)
        assert w.status_code == 201
        w_id = w.json()["data"]["workouts"][0]["id"]

        # Step 3: Verify everything exists
        profile = api_get("/api/auth/profile", headers=h).json()["data"]
        assert profile["nb_workouts"] == 1
        assert abs(profile["total_distance"] - 10.0) < 0.01
        assert 5 in profile["sports_list"]

        recs = api_get("/api/records", headers=h).json()["data"]["records"]
        assert len([r for r in recs if r["sport_id"] == 5]) >= 3  # FD, LD, MS, HA

        eq_data = api_get(f"/api/equipments/{eq_id}", headers=h).json()["data"]["equipments"][0]
        assert eq_data["workouts_count"] == 1
        assert abs(eq_data["total_distance"] - 10.0) < 0.01

        stats = api_get(f"/api/stats/{username}/by_sport", headers=h).json()["data"]["statistics"]
        assert "5" in stats

        # Step 4: DELETE the workout
        del_resp = api_delete(f"/api/workouts/{w_id}", headers=h)
        assert del_resp.status_code == 204

        # Step 5: Profile should show 0 workouts
        profile2 = api_get("/api/auth/profile", headers=h).json()["data"]
        assert profile2["nb_workouts"] == 0
        assert profile2["total_distance"] == 0
        assert profile2["sports_list"] == []

        # Step 6: Records should be empty for sport 5
        recs2 = api_get("/api/records", headers=h).json()["data"]["records"]
        s5_recs = [r for r in recs2 if r["sport_id"] == 5]
        assert len(s5_recs) == 0

        # Step 7: Equipment totals should be 0
        eq_data2 = api_get(f"/api/equipments/{eq_id}", headers=h).json()["data"]["equipments"][0]
        assert eq_data2["workouts_count"] == 0
        assert eq_data2["total_distance"] == 0
        assert eq_data2["total_duration"] == 0

        # Step 8: Stats should be empty
        stats2 = api_get(f"/api/stats/{username}/by_sport", headers=h).json()["data"]["statistics"]
        assert stats2 == {} or "5" not in stats2


class TestMultiSportRecordsIndependence:
    """Pattern 5+6: Records for different sports are independent."""

    def test_records_per_sport_independent(self):
        h = headers_for()

        # Step 1: Create running workout (sport 5)
        r1 = api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-04-01 08:00:00",
        }, headers=h)
        w1_id = r1.json()["data"]["workouts"][0]["id"]

        # Step 2: Create cycling workout (sport 1) with much longer distance
        r2 = api_post("/api/workouts", {
            "sport_id": 1, "duration": 7200, "distance": 60.0,
            "workout_date": "2024-04-02 09:00:00",
        }, headers=h)
        w2_id = r2.json()["data"]["workouts"][0]["id"]

        # Step 3: Verify records are per-sport
        recs = api_get("/api/records", headers=h).json()["data"]["records"]
        s5_recs = {r["record_type"]: r for r in recs if r["sport_id"] == 5}
        s1_recs = {r["record_type"]: r for r in recs if r["sport_id"] == 1}

        # Running FD = 10km, Cycling FD = 60km (independent)
        assert abs(s5_recs["FD"]["value"] - 10.0) < 0.01
        assert s5_recs["FD"]["workout_id"] == w1_id
        assert abs(s1_recs["FD"]["value"] - 60.0) < 0.01
        assert s1_recs["FD"]["workout_id"] == w2_id

        # Step 4: Delete running workout - cycling records unaffected
        api_delete(f"/api/workouts/{w1_id}", headers=h)

        recs2 = api_get("/api/records", headers=h).json()["data"]["records"]
        s5_recs2 = [r for r in recs2 if r["sport_id"] == 5]
        s1_recs2 = {r["record_type"]: r for r in recs2 if r["sport_id"] == 1}
        assert len(s5_recs2) == 0  # Running records gone
        assert abs(s1_recs2["FD"]["value"] - 60.0) < 0.01  # Cycling untouched

        # Step 5: Profile reflects only cycling now
        profile = api_get("/api/auth/profile", headers=h).json()["data"]
        assert profile["nb_workouts"] == 1
        assert abs(profile["total_distance"] - 60.0) < 0.01
        assert profile["nb_sports"] == 1


class TestEquipmentLinkingConstraints:
    """Pattern 5+6+8: Equipment linking rules enforced correctly."""

    def test_all_linking_constraints(self):
        h_a = headers_for()
        h_b = headers_for()

        # Step 1: User A creates equipment
        eq = api_post("/api/equipments", {"label": "Constraint Shoes", "equipment_type_id": 1}, headers=h_a)
        eq_id = eq.json()["data"]["equipments"][0]["id"]

        # Step 2: User A creates inactive equipment
        eq_inactive = api_post("/api/equipments", {
            "label": "Inactive Shoes", "equipment_type_id": 1, "is_active": False,
        }, headers=h_a)
        eq_inactive_id = eq_inactive.json()["data"]["equipments"][0]["id"]

        # Step 3: User A creates workout
        w = api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-11-15 08:00:00",
        }, headers=h_a)
        wa_id = w.json()["data"]["workouts"][0]["id"]

        # Step 4: Link active equipment -> success
        link = api_post(f"/api/workouts/{wa_id}/equipments/{eq_id}", headers=h_a)
        assert link.status_code == 200

        # Step 5: Duplicate link -> 400
        link2 = api_post(f"/api/workouts/{wa_id}/equipments/{eq_id}", headers=h_a)
        assert link2.status_code == 400

        # Step 6: Link inactive equipment -> 400
        link3 = api_post(f"/api/workouts/{wa_id}/equipments/{eq_inactive_id}", headers=h_a)
        assert link3.status_code == 400

        # Step 7: User B creates a workout
        wb = api_post("/api/workouts", {
            "sport_id": 5, "duration": 1800, "distance": 5.0,
            "workout_date": "2024-11-16 08:00:00",
        }, headers=h_b)
        wb_id = wb.json()["data"]["workouts"][0]["id"]

        # Step 8: User B tries to link User A's equipment -> forbidden/not found
        cross_link = api_post(f"/api/workouts/{wb_id}/equipments/{eq_id}", headers=h_b)
        assert cross_link.status_code in [403, 404]

        # Step 9: Link to non-existent workout -> 404
        fake_w_id = "00000000-0000-0000-0000-ffffffffffff"
        link4 = api_post(f"/api/workouts/{fake_w_id}/equipments/{eq_id}", headers=h_a)
        assert link4.status_code == 404

        # Step 10: Link to non-existent equipment -> 404
        fake_eq_id = "00000000-0000-0000-0000-eeeeeeeeeeee"
        link5 = api_post(f"/api/workouts/{wa_id}/equipments/{fake_eq_id}", headers=h_a)
        assert link5.status_code == 404


class TestWorkoutFilterCombinations:
    """Pattern 3: Verify multiple filters work together correctly."""

    def test_combined_filters_sport_and_date(self):
        h = headers_for()

        # Step 1: Create diverse workouts
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-01-15 08:00:00", "title": "Jan Run",
        }, headers=h)
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 1800, "distance": 5.0,
            "workout_date": "2024-03-15 08:00:00", "title": "Mar Run",
        }, headers=h)
        api_post("/api/workouts", {
            "sport_id": 1, "duration": 5400, "distance": 30.0,
            "workout_date": "2024-03-20 09:00:00", "title": "Mar Cycle",
        }, headers=h)
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 2700, "distance": 8.0,
            "workout_date": "2024-06-10 07:00:00", "title": "Jun Run",
        }, headers=h)

        # Step 2: Filter by sport 5 AND March date range -> only "Mar Run"
        resp = api_get("/api/workouts", params={
            "sport_id": 5, "from": "2024-03-01", "to": "2024-03-31", "per_page": 50,
        }, headers=h)
        assert resp.status_code == 200
        workouts = resp.json()["data"]["workouts"]
        assert len(workouts) == 1
        assert workouts[0]["title"] == "Mar Run"
        assert workouts[0]["sport_id"] == 5

        # Step 3: Filter by sport 1 AND March -> only "Mar Cycle"
        resp2 = api_get("/api/workouts", params={
            "sport_id": 1, "from": "2024-03-01", "to": "2024-03-31", "per_page": 50,
        }, headers=h)
        workouts2 = resp2.json()["data"]["workouts"]
        assert len(workouts2) == 1
        assert workouts2[0]["title"] == "Mar Cycle"

        # Step 4: Filter by title "Run" should get 3 results
        resp3 = api_get("/api/workouts", params={"title": "Run", "per_page": 50}, headers=h)
        workouts3 = resp3.json()["data"]["workouts"]
        assert len(workouts3) == 3
        for w in workouts3:
            assert "Run" in w["title"]

        # Step 5: Verify pagination total reflects filter
        resp4 = api_get("/api/workouts", params={
            "sport_id": 5, "per_page": 2, "page": 1,
        }, headers=h)
        pag = resp4.json()["pagination"]
        assert pag["total"] == 3  # 3 running workouts total
        assert pag["pages"] == 2  # ceil(3/2)


class TestRecordsOnWorkoutResponse:
    """Pattern 2: Workout response should include records relevant to that workout."""

    def test_workout_includes_its_records(self):
        h = headers_for()

        # Step 1: Create first workout (will hold all records initially)
        w1 = api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-04-10 08:00:00",
            "ascent": 100.0,
        }, headers=h)
        w1_id = w1.json()["data"]["workouts"][0]["id"]

        # Step 2: Verify workout response includes records
        get1 = api_get(f"/api/workouts/{w1_id}", headers=h)
        w1_data = get1.json()["data"]["workouts"][0]
        assert "records" in w1_data
        assert len(w1_data["records"]) >= 3  # FD, LD, MS, HA
        rec_types = {r["record_type"] for r in w1_data["records"]}
        assert "FD" in rec_types
        assert "LD" in rec_types
        assert "MS" in rec_types
        assert "HA" in rec_types
        for r in w1_data["records"]:
            assert r["workout_id"] == w1_id

        # Step 3: Create better workout that takes some records
        w2 = api_post("/api/workouts", {
            "sport_id": 5, "duration": 7200, "distance": 25.0,
            "workout_date": "2024-04-15 08:00:00",
            "ascent": 300.0,
        }, headers=h)
        w2_id = w2.json()["data"]["workouts"][0]["id"]

        # Step 4: w2 should have FD, LD, HA records; w1 should lose them
        get2 = api_get(f"/api/workouts/{w2_id}", headers=h)
        w2_data = get2.json()["data"]["workouts"][0]
        w2_rec_types = {r["record_type"] for r in w2_data["records"]}
        assert "FD" in w2_rec_types  # 25 > 10
        assert "LD" in w2_rec_types  # 7200 > 3600
        assert "HA" in w2_rec_types  # 300 > 100

        # Step 5: w1 might still hold MS if speed is better (10/1=10 vs 25/2=12.5 -> w2 wins both)
        # Actually w2 speed = 25/2 = 12.5 > w1 speed = 10. So w2 has all records.
        get1_after = api_get(f"/api/workouts/{w1_id}", headers=h)
        w1_data_after = get1_after.json()["data"]["workouts"][0]
        w1_recs_after = w1_data_after["records"]
        # w1 should have no records since w2 beats in all categories
        assert len(w1_recs_after) == 0


class TestProfileUpdatesReflectedInStats:
    """Pattern 5: Username change should work with stats endpoint."""

    def test_username_change_works_with_stats(self):
        h = headers_for()
        original_username = get_username(h)

        # Step 1: Create workout
        api_post("/api/workouts", {
            "sport_id": 5, "duration": 3600, "distance": 10.0,
            "workout_date": "2024-12-10 08:00:00",
        }, headers=h)

        # Step 2: Stats work with original username
        resp = api_get(f"/api/stats/{original_username}/by_sport", headers=h)
        assert resp.status_code == 200
        assert "5" in resp.json()["data"]["statistics"]

        # Step 3: Change username
        new_name = f"renamed_{uuid.uuid4().hex[:6]}"
        api_patch("/api/auth/profile", {"username": new_name}, headers=h)

        # Step 4: Stats work with new username
        resp2 = api_get(f"/api/stats/{new_name}/by_sport", headers=h)
        assert resp2.status_code == 200
        assert "5" in resp2.json()["data"]["statistics"]

        # Step 5: Old username no longer works
        resp3 = api_get(f"/api/stats/{original_username}/by_sport", headers=h)
        assert resp3.status_code == 404
