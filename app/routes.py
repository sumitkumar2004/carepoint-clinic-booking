from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request, render_template

from . import services
from .db import get_db
from .errors import AppError, validation_error
from .validation import (parse_bool_arg, parse_int_arg, parse_time,
                         validate_booking_payload, validate_slot_payload)

bp = Blueprint("api", __name__)


def now():
    clock = current_app.config.get("CLOCK")
    return (clock() if clock else datetime.now(timezone.utc)).replace(microsecond=0)


def json_body():
    data = request.get_json(silent=True)
    if data is None:
        raise validation_error({"body": "Request body must be valid JSON "
                                        "(send Content-Type: application/json)."})
    return data


@bp.get("/")
def index():
    return render_template("index.html")


@bp.get("/api")
def api_info():
    return jsonify({
        "name": "Clinic Booking API",
        "endpoints": {
            "slots": "GET/POST /slots, GET/DELETE /slots/<id>",
            "bookings": "GET/POST /bookings, GET/DELETE /bookings/<id>",
            "health": "GET /health",
        },
        "docs": "See README.md for examples.",
    })


@bp.get("/health")
def health():
    return jsonify({"status": "ok"})


# ---------- slots ----------

@bp.post("/slots")
def create_slot():
    clinic_id, start, end = validate_slot_payload(json_body(), now())
    slot = services.create_slot(get_db(), clinic_id, start, end, now())
    return jsonify(slot), 201


@bp.get("/slots")
def list_slots():
    args, errors = request.args, {}
    available = parse_bool_arg(args.get("available"), "available", errors)
    start_from = parse_time(args["from"], "from", errors) if "from" in args else None
    start_to = parse_time(args["to"], "to", errors) if "to" in args else None
    limit = parse_int_arg(args.get("limit"), "limit", errors, 50, 1, 200)
    offset = parse_int_arg(args.get("offset"), "offset", errors, 0, 0, 10**9)
    if errors:
        raise validation_error(errors)
    slots = services.list_slots(get_db(), now(), args.get("clinic_id"), available,
                                start_from, start_to, limit, offset)
    return jsonify({"slots": slots, "count": len(slots)})


@bp.get("/slots/<int:slot_id>")
def get_slot(slot_id):
    return jsonify(services.get_slot(get_db(), slot_id))


@bp.delete("/slots/<int:slot_id>")
def cancel_slot(slot_id):
    return jsonify(services.cancel_slot(get_db(), slot_id, now()))


# ---------- bookings ----------

@bp.post("/bookings")
def create_booking():
    slot_id, name, email = validate_booking_payload(json_body())
    booking = services.book_slot(get_db(), slot_id, name, email, now())
    return jsonify(booking), 201


@bp.get("/bookings")
def list_bookings():
    args, errors = request.args, {}
    slot_id = parse_int_arg(args.get("slot_id"), "slot_id", errors, None, 1, 10**12)
    status = args.get("status")
    if status and status not in ("booked", "cancelled"):
        errors["status"] = "Must be 'booked' or 'cancelled'."
    limit = parse_int_arg(args.get("limit"), "limit", errors, 50, 1, 200)
    offset = parse_int_arg(args.get("offset"), "offset", errors, 0, 0, 10**9)
    if errors:
        raise validation_error(errors)
    bookings = services.list_bookings(get_db(), args.get("patient_email"), slot_id,
                                      status, limit, offset)
    return jsonify({"bookings": bookings, "count": len(bookings)})


@bp.get("/bookings/<int:booking_id>")
def get_booking(booking_id):
    return jsonify(services.get_booking(get_db(), booking_id))


@bp.delete("/bookings/<int:booking_id>")
def cancel_booking(booking_id):
    return jsonify(services.cancel_booking(get_db(), booking_id, now()))


# ---------- error handlers ----------

@bp.app_errorhandler(AppError)
def handle_app_error(err):
    return jsonify(err.to_dict()), err.status


@bp.app_errorhandler(404)
def handle_404(_err):
    return jsonify({"error": {"code": "not_found", "message": "No such endpoint."}}), 404


@bp.app_errorhandler(405)
def handle_405(_err):
    return jsonify({"error": {"code": "method_not_allowed",
                              "message": "Method not allowed for this endpoint."}}), 405


@bp.app_errorhandler(500)
def handle_500(_err):
    return jsonify({"error": {"code": "internal_error",
                              "message": "Something went wrong on our side."}}), 500
