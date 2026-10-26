import threading
from datetime import datetime, timedelta, timezone

import pytest

from app import create_app

NOW = datetime(2026, 10, 26, 12, 0, 0, tzinfo=timezone.utc)


class Clock:
    """Controllable clock so tests never depend on the real time."""

    def __init__(self):
        self.now = NOW

    def __call__(self):
        return self.now


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def app(tmp_path, clock):
    # File-backed DB (not :memory:) so concurrent requests hit one real database.
    return create_app({"DATABASE": str(tmp_path / "test.db"), "CLOCK": clock, "TESTING": True})


@pytest.fixture
def client(app):
    return app.test_client()


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture
def make_slot(client):
    def _make(clinic="clinic-1", offset_hours=24, minutes=30):
        start = NOW + timedelta(hours=offset_hours)
        res = client.post("/slots", json={
            "clinic_id": clinic,
            "start_time": iso(start),
            "end_time": iso(start + timedelta(minutes=minutes)),
        })
        assert res.status_code == 201, res.get_json()
        return res.get_json()
    return _make


@pytest.fixture
def book(client):
    def _book(slot_id, name="Asha Rao", email="asha@example.com"):
        return client.post("/bookings", json={
            "slot_id": slot_id, "patient_name": name, "patient_email": email})
    return _book


def test_root_lists_endpoints(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "endpoints" in res.get_json()


# ---------------- slot creation & validation ----------------

def test_create_slot(client):
    start = NOW + timedelta(days=1)
    res = client.post("/slots", json={
        "clinic_id": "c1", "start_time": iso(start),
        "end_time": iso(start + timedelta(minutes=30))})
    assert res.status_code == 201
    body = res.get_json()
    assert body["state"] == "available" and body["clinic_id"] == "c1"


def test_create_slot_accepts_timezone_offsets(client):
    res = client.post("/slots", json={
        "clinic_id": "c1",
        "start_time": "2026-11-02T09:00:00+05:30",
        "end_time": "2026-11-02T09:30:00+05:30"})
    assert res.status_code == 201
    assert res.get_json()["start_time"] == "2026-11-02T03:30:00Z"


@pytest.mark.parametrize("payload,field", [
    ({}, "clinic_id"),
    ({"clinic_id": "c1", "start_time": "tomorrow", "end_time": "2026-11-02T10:00:00Z"}, "start_time"),
    ({"clinic_id": "c1", "start_time": "2026-11-02T09:00:00", "end_time": "2026-11-02T10:00:00Z"}, "start_time"),
    ({"clinic_id": "c1", "start_time": "2026-11-02T10:00:00Z", "end_time": "2026-11-02T09:00:00Z"}, "end_time"),
    ({"clinic_id": "c1", "start_time": "2026-10-01T10:00:00Z", "end_time": "2026-10-01T11:00:00Z"}, "start_time"),
    ({"clinic_id": "c1", "start_time": "2026-11-02T00:00:00Z", "end_time": "2026-11-03T00:00:00Z"}, "end_time"),
])
def test_create_slot_validation_errors_are_specific(client, payload, field):
    res = client.post("/slots", json=payload)
    assert res.status_code == 400
    err = res.get_json()["error"]
    assert err["code"] == "validation_error"
    assert field in err["details"]


def test_invalid_json_body_rejected(client):
    res = client.post("/slots", data="not json", content_type="application/json")
    assert res.status_code == 400


def test_overlapping_slots_for_same_clinic_rejected(client, make_slot):
    make_slot(offset_hours=24, minutes=60)
    start = NOW + timedelta(hours=24, minutes=30)
    res = client.post("/slots", json={
        "clinic_id": "clinic-1", "start_time": iso(start),
        "end_time": iso(start + timedelta(minutes=30))})
    assert res.status_code == 409
    assert res.get_json()["error"]["code"] == "slot_overlap"


def test_overlap_allowed_across_clinics(make_slot):
    make_slot(clinic="a")
    make_slot(clinic="b")


# ---------------- booking rules ----------------

def test_book_available_slot(book, make_slot, client):
    slot = make_slot()
    res = book(slot["id"])
    assert res.status_code == 201
    assert res.get_json()["status"] == "booked"
    assert client.get(f"/slots/{slot['id']}").get_json()["state"] == "booked"


def test_cannot_double_book_a_slot(book, make_slot):
    slot = make_slot()
    assert book(slot["id"]).status_code == 201
    res = book(slot["id"], name="Someone Else", email="other@example.com")
    assert res.status_code == 409
    assert res.get_json()["error"]["code"] == "slot_already_booked"


def test_cancel_booking_frees_slot_for_rebooking(book, make_slot, client):
    slot = make_slot()
    first = book(slot["id"]).get_json()
    assert client.delete(f"/bookings/{first['id']}").status_code == 200
    assert client.get(f"/slots/{slot['id']}").get_json()["state"] == "available"
    second = book(slot["id"], email="next@example.com")
    assert second.status_code == 201
    assert second.get_json()["id"] != first["id"]


def test_cancelling_booking_twice_conflicts(book, make_slot, client):
    b = book(make_slot()["id"]).get_json()
    assert client.delete(f"/bookings/{b['id']}").status_code == 200
    res = client.delete(f"/bookings/{b['id']}")
    assert res.status_code == 409
    assert res.get_json()["error"]["code"] == "booking_already_cancelled"


def test_cannot_book_cancelled_slot(book, make_slot, client):
    slot = make_slot()
    assert client.delete(f"/slots/{slot['id']}").status_code == 200
    res = book(slot["id"])
    assert res.status_code == 409
    assert res.get_json()["error"]["code"] == "slot_cancelled"


def test_cancelling_slot_cancels_its_active_booking(book, make_slot, client):
    slot = make_slot()
    b = book(slot["id"]).get_json()
    assert client.delete(f"/slots/{slot['id']}").status_code == 200
    assert client.get(f"/bookings/{b['id']}").get_json()["status"] == "cancelled"


def test_cannot_book_slot_that_already_started(book, make_slot, clock):
    slot = make_slot(offset_hours=1)
    clock.now = NOW + timedelta(hours=2)
    res = book(slot["id"])
    assert res.status_code == 409
    assert res.get_json()["error"]["code"] == "slot_in_past"


def test_book_unknown_slot_404(book):
    assert book(9999).status_code == 404


@pytest.mark.parametrize("payload,field", [
    ({}, "slot_id"),
    ({"slot_id": "abc", "patient_name": "A", "patient_email": "a@b.co"}, "slot_id"),
    ({"slot_id": 1, "patient_name": "  ", "patient_email": "a@b.co"}, "patient_name"),
    ({"slot_id": 1, "patient_name": "A", "patient_email": "not-an-email"}, "patient_email"),
])
def test_booking_validation_errors(client, payload, field):
    res = client.post("/bookings", json=payload)
    assert res.status_code == 400
    assert field in res.get_json()["error"]["details"]


# ---------------- listing ----------------

def test_list_slots_available_filter(client, make_slot, book):
    free = make_slot(offset_hours=24)
    taken = make_slot(offset_hours=26)
    gone = make_slot(offset_hours=28)
    book(taken["id"])
    client.delete(f"/slots/{gone['id']}")

    available = client.get("/slots?available=true").get_json()["slots"]
    assert [s["id"] for s in available] == [free["id"]]

    unavailable = client.get("/slots?available=false").get_json()["slots"]
    assert {s["id"] for s in unavailable} == {taken["id"], gone["id"]}


def test_list_slots_filters_by_clinic(client, make_slot):
    make_slot(clinic="a")
    make_slot(clinic="b", offset_hours=30)
    slots = client.get("/slots?clinic_id=b").get_json()["slots"]
    assert len(slots) == 1 and slots[0]["clinic_id"] == "b"


def test_list_slots_rejects_bad_query_params(client):
    res = client.get("/slots?available=maybe&limit=0")
    assert res.status_code == 400
    assert {"available", "limit"} <= set(res.get_json()["error"]["details"])


def test_list_bookings_by_patient_email(client, make_slot, book):
    book(make_slot(offset_hours=24)["id"], email="x@example.com")
    book(make_slot(offset_hours=26)["id"], email="y@example.com")
    res = client.get("/bookings?patient_email=X@example.com").get_json()
    assert res["count"] == 1


# ---------------- concurrency ----------------

def test_concurrent_requests_cannot_double_book(app, make_slot):
    slot = make_slot()
    n = 25
    barrier = threading.Barrier(n)
    results = []
    lock = threading.Lock()

    def attempt(i):
        c = app.test_client()
        barrier.wait()  # release all requests at the same instant
        res = c.post("/bookings", json={
            "slot_id": slot["id"], "patient_name": f"Patient {i}",
            "patient_email": f"p{i}@example.com"})
        with lock:
            results.append(res.status_code)

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(results) == [201] + [409] * (n - 1)

    active = app.test_client().get(f"/bookings?slot_id={slot['id']}&status=booked").get_json()
    assert active["count"] == 1


def test_database_itself_refuses_a_second_active_booking(app, make_slot):
    """Backstop: even bypassing the service layer, the unique index holds."""
    import sqlite3
    slot = make_slot()
    conn = sqlite3.connect(app.config["DATABASE"])
    ins = ("INSERT INTO bookings (slot_id, patient_name, patient_email, created_at) "
           "VALUES (?, 'n', 'e@x.co', 't')")
    conn.execute(ins, (slot["id"],))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(ins, (slot["id"],))
    conn.close()
