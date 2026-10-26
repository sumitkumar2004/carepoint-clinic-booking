import sqlite3

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS slots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id   TEXT NOT NULL,
    start_time  TEXT NOT NULL,              -- UTC, YYYY-MM-DDTHH:MM:SSZ
    end_time    TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'cancelled')),
    created_at  TEXT NOT NULL,
    cancelled_at TEXT,
    CHECK (end_time > start_time)
);

CREATE TABLE IF NOT EXISTS bookings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_id       INTEGER NOT NULL REFERENCES slots(id),
    patient_name  TEXT NOT NULL,
    patient_email TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'booked' CHECK (status IN ('booked', 'cancelled')),
    created_at    TEXT NOT NULL,
    cancelled_at  TEXT
);

-- The core guarantee: at most ONE active booking per slot, enforced by the
-- database itself, so it holds even if application-level checks are raced.
CREATE UNIQUE INDEX IF NOT EXISTS ux_bookings_one_active_per_slot
    ON bookings(slot_id) WHERE status = 'booked';

CREATE INDEX IF NOT EXISTS ix_slots_clinic_start ON slots(clinic_id, start_time);
CREATE INDEX IF NOT EXISTS ix_bookings_email ON bookings(patient_email);
"""


def connect(path):
    # isolation_level=None -> autocommit; transactions are managed explicitly
    # (BEGIN IMMEDIATE) in the service layer.
    conn = sqlite3.connect(path, timeout=15, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def get_db():
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(path):
    conn = connect(path)
    try:
        conn.executescript(SCHEMA)
    finally:
        conn.close()


def init_app(app):
    init_db(app.config["DATABASE"])
    app.teardown_appcontext(close_db)
