"""Business rules. Everything that touches booking state lives here.

Concurrency strategy (two layers):
  1. Every state-changing operation runs inside BEGIN IMMEDIATE, which takes
     SQLite's write lock up front, so check-then-write sequences are serialised.
  2. A partial UNIQUE index (one 'booked' row per slot) is the backstop: even if
     a code path forgot the lock, the database would refuse a second booking.
"""
import sqlite3
from contextlib import contextmanager

from .errors import conflict, not_found
from .validation import format_time


@contextmanager
def write_transaction(db):
    db.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        db.execute("ROLLBACK")
        raise
    else:
        db.execute("COMMIT")


# ---------- serialisation ----------

def slot_to_dict(row):
    if row["status"] == "cancelled":
        state = "cancelled"
    elif row["is_booked"]:
        state = "booked"
    else:
        state = "available"
    return {
        "id": row["id"],
        "clinic_id": row["clinic_id"],
        "start_time": row["start_time"],
        "end_time": row["end_time"],
        "state": state,
        "created_at": row["created_at"],
        "cancelled_at": row["cancelled_at"],
    }


def booking_to_dict(row):
    return {
        "id": row["id"],
        "slot_id": row["slot_id"],
        "patient_name": row["patient_name"],
        "patient_email": row["patient_email"],
        "status": row["status"],
        "created_at": row["created_at"],
        "cancelled_at": row["cancelled_at"],
    }


_SLOT_SELECT = """
    SELECT s.*,
           EXISTS (SELECT 1 FROM bookings b
                   WHERE b.slot_id = s.id AND b.status = 'booked') AS is_booked
    FROM slots s
"""


def _get_slot_row(db, slot_id):
    row = db.execute(_SLOT_SELECT + " WHERE s.id = ?", (slot_id,)).fetchone()
    if row is None:
        raise not_found("Slot", slot_id)
    return row


def _get_booking_row(db, booking_id):
    row = db.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
    if row is None:
        raise not_found("Booking", booking_id)
    return row


# ---------- slots ----------

def create_slot(db, clinic_id, start, end, now):
    start_s, end_s = format_time(start), format_time(end)
    with write_transaction(db):
        overlap = db.execute(
            "SELECT id FROM slots WHERE clinic_id = ? AND status = 'open' "
            "AND start_time < ? AND end_time > ?",
            (clinic_id, end_s, start_s),
        ).fetchone()
        if overlap:
            raise conflict(
                "slot_overlap",
                f"Overlaps existing slot {overlap['id']} for clinic '{clinic_id}'.",
            )
        cur = db.execute(
            "INSERT INTO slots (clinic_id, start_time, end_time, created_at) "
            "VALUES (?, ?, ?, ?)",
            (clinic_id, start_s, end_s, format_time(now)),
        )
        slot_id = cur.lastrowid
    return slot_to_dict(_get_slot_row(db, slot_id))


def get_slot(db, slot_id):
    return slot_to_dict(_get_slot_row(db, slot_id))


def list_slots(db, now, clinic_id=None, available=None, start_from=None,
               start_to=None, limit=50, offset=0):
    where, params = [], []
    if clinic_id:
        where.append("s.clinic_id = ?")
        params.append(clinic_id)
    if start_from:
        where.append("s.start_time >= ?")
        params.append(format_time(start_from))
    if start_to:
        where.append("s.start_time < ?")
        params.append(format_time(start_to))
    if available is True:
        where.append("s.status = 'open' AND s.start_time > ? AND NOT EXISTS "
                     "(SELECT 1 FROM bookings b WHERE b.slot_id = s.id AND b.status = 'booked')")
        params.append(format_time(now))
    elif available is False:
        where.append("(s.status = 'cancelled' OR s.start_time <= ? OR EXISTS "
                     "(SELECT 1 FROM bookings b WHERE b.slot_id = s.id AND b.status = 'booked'))")
        params.append(format_time(now))

    sql = _SLOT_SELECT
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY s.start_time, s.id LIMIT ? OFFSET ?"
    rows = db.execute(sql, (*params, limit, offset)).fetchall()
    return [slot_to_dict(r) for r in rows]


def cancel_slot(db, slot_id, now):
    """Cancel a slot. Any active booking on it is cancelled too."""
    with write_transaction(db):
        row = _get_slot_row(db, slot_id)
        if row["status"] == "cancelled":
            raise conflict("slot_already_cancelled", f"Slot {slot_id} is already cancelled.")
        ts = format_time(now)
        db.execute("UPDATE slots SET status = 'cancelled', cancelled_at = ? WHERE id = ?",
                   (ts, slot_id))
        db.execute("UPDATE bookings SET status = 'cancelled', cancelled_at = ? "
                   "WHERE slot_id = ? AND status = 'booked'", (ts, slot_id))
    return slot_to_dict(_get_slot_row(db, slot_id))


# ---------- bookings ----------

def book_slot(db, slot_id, patient_name, patient_email, now):
    with write_transaction(db):
        slot = _get_slot_row(db, slot_id)
        if slot["status"] == "cancelled":
            raise conflict("slot_cancelled", f"Slot {slot_id} has been cancelled.")
        if slot["start_time"] <= format_time(now):
            raise conflict("slot_in_past", f"Slot {slot_id} has already started.")
        try:
            cur = db.execute(
                "INSERT INTO bookings (slot_id, patient_name, patient_email, created_at) "
                "VALUES (?, ?, ?, ?)",
                (slot_id, patient_name, patient_email, format_time(now)),
            )
        except sqlite3.IntegrityError:
            raise conflict("slot_already_booked", f"Slot {slot_id} is already booked.")
        booking_id = cur.lastrowid
    return booking_to_dict(_get_booking_row(db, booking_id))


def get_booking(db, booking_id):
    return booking_to_dict(_get_booking_row(db, booking_id))


def list_bookings(db, patient_email=None, slot_id=None, status=None, limit=50, offset=0):
    where, params = [], []
    if patient_email:
        where.append("patient_email = ?")
        params.append(patient_email.lower())
    if slot_id is not None:
        where.append("slot_id = ?")
        params.append(slot_id)
    if status:
        where.append("status = ?")
        params.append(status)
    sql = "SELECT * FROM bookings"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id LIMIT ? OFFSET ?"
    return [booking_to_dict(r) for r in db.execute(sql, (*params, limit, offset))]


def cancel_booking(db, booking_id, now):
    with write_transaction(db):
        row = _get_booking_row(db, booking_id)
        if row["status"] == "cancelled":
            raise conflict("booking_already_cancelled",
                           f"Booking {booking_id} is already cancelled.")
        db.execute("UPDATE bookings SET status = 'cancelled', cancelled_at = ? WHERE id = ?",
                   (format_time(now), booking_id))
    return booking_to_dict(_get_booking_row(db, booking_id))
