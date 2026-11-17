import threading
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import connections
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from .models import Vehicle, VehicleEntry

ENTRY_PAYLOAD = {
    "vehicle_number": "KA03AB1234",
    "vehicle_type": "TRUCK",
    "driver_name": "Ramesh",
    "driver_mobile": "9876543210",
    "vendor_name": "ABC Cement Suppliers",
    "purpose": "MATERIAL_DELIVERY",
}


class BaseAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("tester", password="pass12345")
        self.client.force_authenticate(self.user)

    def enter(self, **overrides):
        return self.client.post("/api/entries/", {**ENTRY_PAYLOAD, **overrides}, format="json")


class VehicleTests(BaseAPITest):
    def test_manual_registration(self):
        r = self.client.post(
            "/api/vehicles/",
            {"vehicle_number": " ka03ab1234 ", "vehicle_type": "TRUCK"},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["vehicle_number"], "KA03AB1234")

    def test_duplicate_manual_registration_rejected(self):
        body = {"vehicle_number": "KA03AB1234", "vehicle_type": "TRUCK"}
        self.client.post("/api/vehicles/", body, format="json")
        r = self.client.post("/api/vehicles/", {**body, "vehicle_number": " ka03ab1234"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Vehicle.objects.count(), 1)

    def test_blank_and_invalid_type_rejected(self):
        r = self.client.post("/api/vehicles/", {"vehicle_number": "   ", "vehicle_type": "CAR"}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.client.post("/api/vehicles/", {"vehicle_number": "X1", "vehicle_type": "BOAT"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_update_vehicle(self):
        v = Vehicle.objects.create(vehicle_number="KA01", vehicle_type="CAR")
        r = self.client.patch(f"/api/vehicles/{v.id}/", {"owner_name": "New Owner"}, format="json")
        self.assertEqual(r.status_code, 200)
        v.refresh_from_db()
        self.assertEqual(v.owner_name, "New Owner")

    def test_unauthenticated_rejected(self):
        r = APIClient().get("/api/vehicles/")
        self.assertIn(r.status_code, (401, 403))


class EntryTests(BaseAPITest):
    def test_first_time_entry_creates_vehicle_and_entry(self):
        r = self.enter()
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["status"], "INSIDE")
        self.assertEqual(Vehicle.objects.count(), 1)
        self.assertEqual(VehicleEntry.objects.count(), 1)

    def test_lowercase_number_is_normalized(self):
        r = self.enter(vehicle_number="  ka03ab1234 ")
        self.assertEqual(r.data["vehicle"]["vehicle_number"], "KA03AB1234")

    def test_existing_vehicle_is_reused(self):
        v = Vehicle.objects.create(vehicle_number="KA03AB1234", vehicle_type="TRUCK")
        r = self.enter()
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["vehicle"]["id"], v.id)
        self.assertEqual(Vehicle.objects.count(), 1)

    def test_missing_driver_name(self):
        payload = {k: v for k, v in ENTRY_PAYLOAD.items() if k != "driver_name"}
        r = self.client.post("/api/entries/", payload, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("driver_name", r.data)

    def test_invalid_mobile(self):
        r = self.enter(driver_mobile="12345")
        self.assertEqual(r.status_code, 400)
        self.assertIn("driver_mobile", r.data)

    def test_invalid_first_entry_leaves_nothing_behind(self):
        r = self.enter(driver_mobile="123")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Vehicle.objects.count(), 0)
        self.assertEqual(VehicleEntry.objects.count(), 0)

    def test_second_active_entry_rejected(self):
        self.enter()
        r = self.enter()
        self.assertEqual(r.status_code, 400)
        self.assertEqual(VehicleEntry.objects.count(), 1)

    def test_type_mismatch_rejected_and_master_unchanged(self):
        Vehicle.objects.create(vehicle_number="KA03AB1234", vehicle_type="TRUCK")
        r = self.enter(vehicle_type="CAR")
        self.assertEqual(r.status_code, 400)
        self.assertIn("vehicle_type", r.data)
        self.assertEqual(Vehicle.objects.get().vehicle_type, "TRUCK")
        self.assertEqual(VehicleEntry.objects.count(), 0)

    def test_client_cannot_set_entry_time_or_status(self):
        before = timezone.now()
        r = self.enter(entry_time="2020-01-01T00:00:00Z", status="EXITED")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["status"], "INSIDE")
        entry = VehicleEntry.objects.get(id=r.data["id"])
        self.assertGreaterEqual(entry.entry_time, before)  # server time, not 2020
        self.assertIsNone(entry.exit_time)

class ExitTests(BaseAPITest):
    def test_exit_then_duplicate_exit(self):
        entry_id = self.enter().data["id"]
        r = self.client.post(f"/api/entries/{entry_id}/exit/", {}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "EXITED")
        self.assertIsNotNone(r.data["exit_time"])
        r = self.client.post(f"/api/entries/{entry_id}/exit/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_exit_not_found(self):
        r = self.client.post("/api/entries/99999/exit/", {}, format="json")
        self.assertEqual(r.status_code, 404)

    def test_duration_in_minutes(self):
        entry_id = self.enter().data["id"]
        VehicleEntry.objects.filter(id=entry_id).update(
            entry_time=timezone.now() - timedelta(minutes=90)
        )
        r = self.client.post(f"/api/entries/{entry_id}/exit/", {}, format="json")
        self.assertEqual(r.data["duration_minutes"], 90)

    def test_reentry_after_exit_reuses_vehicle_and_keeps_history(self):
        first = self.enter().data
        self.client.post(f"/api/entries/{first['id']}/exit/", {}, format="json")
        second = self.enter()
        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.data["vehicle"]["id"], first["vehicle"]["id"])
        self.assertEqual(Vehicle.objects.count(), 1)
        self.assertEqual(VehicleEntry.objects.count(), 2)


class HistoryAndReportTests(BaseAPITest):
    def test_inside_returns_only_active(self):
        done = self.enter(vehicle_number="AA11").data["id"]
        self.client.post(f"/api/entries/{done}/exit/", {}, format="json")
        self.enter(vehicle_number="BB22")
        r = self.client.get("/api/entries/inside/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["total_inside"], 1)
        self.assertEqual(r.data["vehicles"][0]["vehicle_number"], "BB22")

    def test_filter_by_vehicle_number_and_status(self):
        self.enter(vehicle_number="AA11")
        self.enter(vehicle_number="BB22")
        r = self.client.get("/api/entries/?vehicle_number=aa11")
        self.assertEqual(len(r.data), 1)
        r = self.client.get("/api/entries/?status=INSIDE")
        self.assertEqual(len(r.data), 2)
        self.assertEqual(self.client.get("/api/entries/?status=NOPE").status_code, 400)

    def test_filter_by_entry_date_and_ordering(self):
        old = self.enter(vehicle_number="OLD1").data["id"]
        VehicleEntry.objects.filter(id=old).update(
            entry_time=timezone.now() - timedelta(days=3)
        )
        self.enter(vehicle_number="NEW1")
        today = timezone.localdate().isoformat()
        r = self.client.get(f"/api/entries/?date={today}")
        self.assertEqual([e["vehicle"]["vehicle_number"] for e in r.data], ["NEW1"])
        r = self.client.get("/api/entries/")
        self.assertEqual(r.data[0]["vehicle"]["vehicle_number"], "NEW1")  # latest first
        self.assertEqual(self.client.get("/api/entries/?date=abc").status_code, 400)

    def test_daily_report_metrics_are_independent(self):
        # Entered yesterday, exits today: counts as an exit today, not an entry today.
        a = self.enter(vehicle_number="AA11").data["id"]
        VehicleEntry.objects.filter(id=a).update(
            entry_time=timezone.now() - timedelta(days=1)
        )
        self.client.post(f"/api/entries/{a}/exit/", {}, format="json")
        # Entered today, still inside.
        self.enter(vehicle_number="BB22")
        # Entered today, exited today.
        b = self.enter(vehicle_number="CC33").data["id"]
        self.client.post(f"/api/entries/{b}/exit/", {}, format="json")

        today = timezone.localdate().isoformat()
        r = self.client.get(f"/api/reports/daily/?date={today}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["total_entries"], 2)
        self.assertEqual(r.data["total_exits"], 2)
        self.assertEqual(r.data["currently_inside"], 1)

    def test_daily_report_requires_valid_date(self):
        self.assertEqual(self.client.get("/api/reports/daily/").status_code, 400)
        self.assertEqual(self.client.get("/api/reports/daily/?date=x").status_code, 400)


class ConcurrencyTests(TransactionTestCase):
    """TransactionTestCase commits for real, so the DB constraint is truly exercised."""

    def test_simultaneous_entries_create_only_one_active_entry(self):
        user = User.objects.create_user("racer", password="pass12345")
        n = 5
        barrier = threading.Barrier(n)
        results = []

        def worker():
            client = APIClient()
            client.force_authenticate(user)
            barrier.wait()
            try:
                r = client.post("/api/entries/", ENTRY_PAYLOAD, format="json")
                results.append(r.status_code)
            finally:
                connections.close_all()

        threads = [threading.Thread(target=worker) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(results.count(201), 1, results)
        self.assertEqual(VehicleEntry.objects.filter(status="INSIDE").count(), 1)
        self.assertEqual(Vehicle.objects.count(), 1)