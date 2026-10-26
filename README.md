# CarePoint Clinic Booking — Flask Frontend + API

This package includes a responsive clinic appointment dashboard served by the existing Flask API. The UI supports publishing time slots, browsing availability, creating patient bookings, searching bookings by email, and cancelling slots/bookings.

## Run the website on Windows

1. Extract the ZIP file.
2. Open Command Prompt or PowerShell in the `clinic-booking-api` folder (the folder containing `run.py`).
3. Run `py -m pip install -r requirements.txt`
4. Run `py run.py`
5. Open `http://127.0.0.1:5000` in your browser.

The app uses SQLite and creates its database tables automatically. Keep `run.py` running while using the website. This is a local development setup; use a production WSGI server and configure security before public deployment.

## Frontend features

- Responsive dashboard with live slot and booking counts
- Create clinic time slots
- Filter slots by clinic ID and availability
- Book available appointments
- Search bookings by patient email
- Cancel appointments or time slots
- API validation/conflict messages shown in the UI



A small Flask + SQLite API where clinics publish time slots and patients book them.
A slot can **never** be double-booked, even when two requests arrive at the same moment.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run.py            # serves on http://127.0.0.1:5000
pytest -q                # run the tests
```

The database file defaults to `clinic.db`; override with `DATABASE=/path/to/file.db`.
Tables are created automatically on startup.

## How double-booking is prevented

Two independent layers:

1. **Serialised writes.** Every state-changing operation runs inside SQLite's
   `BEGIN IMMEDIATE`, which takes the write lock up front. Two concurrent
   "check slot is free, then insert booking" sequences cannot interleave.
2. **Database constraint as a backstop.** A partial unique index
   (`bookings(slot_id) WHERE status = 'booked'`) means the database itself rejects a second
   active booking for the same slot, even if application code were wrong. Cancelled bookings
   are excluded from the index, so a freed slot can be rebooked.

`tests/test_booking_rules.py` fires 25 simultaneous booking requests at one slot and asserts
exactly one `201` and 24 `409`s, and separately proves the DB constraint works when the
service layer is bypassed.

## Project layout

```
app/
  __init__.py     app factory
  routes.py       HTTP layer: parsing, status codes, error handlers
  services.py     business rules and transactions (no Flask imports)
  validation.py   input validation and parsing
  db.py           schema and connection handling
  errors.py       AppError type -> consistent JSON errors
tests/            pytest suite (injectable clock, file-backed temp DB)
run.py            entry point
```

## Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/slots` | Create a slot |
| GET | `/slots` | List slots (filters below) |
| GET | `/slots/<id>` | Get one slot |
| DELETE | `/slots/<id>` | Cancel a slot (also cancels its active booking) |
| POST | `/bookings` | Book a slot |
| GET | `/bookings` | List bookings (`patient_email`, `slot_id`, `status`) |
| GET | `/bookings/<id>` | Get one booking |
| DELETE | `/bookings/<id>` | Cancel a booking (frees the slot) |
| GET | `/health` | Liveness check |

List endpoints accept `limit` (1-200, default 50) and `offset`.
`GET /slots` filters: `clinic_id`, `available=true|false`, `from`, `to` (ISO timestamps).

Slot `state` is one of `available`, `booked`, `cancelled`.

## Rules

- Timestamps are ISO-8601 **with a timezone** (or `Z`); stored and returned in UTC.
- Slot start must be in the future, end after start, max 12 hours.
- Slots for the same clinic cannot overlap (`409 slot_overlap`).
- Cannot book a slot that is already booked, cancelled, or already started.
- Cancelling is a soft delete: records are kept with `cancelled_at`.

## Example requests

```bash
# Clinic publishes a slot
curl -X POST localhost:5000/slots -H 'Content-Type: application/json' -d '{
  "clinic_id": "clinic-42",
  "start_time": "2026-11-02T09:00:00+05:30",
  "end_time": "2026-11-02T09:30:00+05:30"}'

# List open slots for a clinic
curl 'localhost:5000/slots?clinic_id=clinic-42&available=true'

# Patient books it
curl -X POST localhost:5000/bookings -H 'Content-Type: application/json' -d '{
  "slot_id": 1, "patient_name": "Asha Rao", "patient_email": "asha@example.com"}'

# Cancel the booking
curl -X DELETE localhost:5000/bookings/1
```

## Errors

All errors share one shape:

```json
{"error": {"code": "validation_error",
           "message": "Request validation failed.",
           "details": {"end_time": "end_time must be after start_time."}}}
```

| Status | Codes |
|---|---|
| 400 | `validation_error` (per-field `details`) |
| 404 | `not_found` |
| 405 | `method_not_allowed` |
| 409 | `slot_already_booked`, `slot_cancelled`, `slot_in_past`, `slot_overlap`, `slot_already_cancelled`, `booking_already_cancelled` |

## Design notes / trade-offs

- SQLite allows one writer at a time, which makes the concurrency guarantee simple and
  strong. For Postgres, the same partial unique index works unchanged; use
  `SELECT ... FOR UPDATE` on the slot row in place of `BEGIN IMMEDIATE`.
- No authentication: clinic vs patient roles are out of scope for this exercise.
- Time is injected via `app.config["CLOCK"]` so tests are deterministic.
