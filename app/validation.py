import re
from datetime import datetime, timedelta, timezone

from .errors import validation_error

TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_SLOT_DURATION = timedelta(hours=12)


def format_time(dt):
    return dt.astimezone(timezone.utc).strftime(TIME_FORMAT)


def parse_time(value, field, errors):
    """Parse an ISO-8601 timestamp that carries a timezone; return UTC datetime."""
    if not isinstance(value, str) or not value.strip():
        errors[field] = "Required. Use an ISO-8601 timestamp, e.g. 2026-11-02T09:00:00Z."
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        errors[field] = "Not a valid ISO-8601 timestamp, e.g. 2026-11-02T09:00:00Z."
        return None
    if dt.tzinfo is None:
        errors[field] = "Timestamp must include a timezone or 'Z' (UTC)."
        return None
    return dt.astimezone(timezone.utc).replace(microsecond=0)


def require_json_object(data):
    if not isinstance(data, dict):
        raise validation_error({"body": "Request body must be a JSON object."})
    return data


def _require_text(data, field, errors, max_len):
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        errors[field] = "Required non-empty string."
        return None
    value = value.strip()
    if len(value) > max_len:
        errors[field] = f"Must be at most {max_len} characters."
        return None
    return value


def validate_slot_payload(data, now):
    data = require_json_object(data)
    errors = {}
    clinic_id = _require_text(data, "clinic_id", errors, 64)
    start = parse_time(data.get("start_time"), "start_time", errors)
    end = parse_time(data.get("end_time"), "end_time", errors)

    if start and end:
        if end <= start:
            errors["end_time"] = "end_time must be after start_time."
        elif end - start > MAX_SLOT_DURATION:
            errors["end_time"] = "A slot cannot be longer than 12 hours."
        if start <= now:
            errors["start_time"] = "start_time must be in the future."

    if errors:
        raise validation_error(errors)
    return clinic_id, start, end


def validate_booking_payload(data):
    data = require_json_object(data)
    errors = {}

    slot_id = data.get("slot_id")
    if isinstance(slot_id, bool) or not isinstance(slot_id, int) or slot_id < 1:
        errors["slot_id"] = "Required positive integer."

    name = _require_text(data, "patient_name", errors, 100)

    email = _require_text(data, "patient_email", errors, 254)
    if email and not EMAIL_RE.match(email):
        errors["patient_email"] = "Not a valid email address."

    if errors:
        raise validation_error(errors)
    return slot_id, name, email.lower()


def parse_bool_arg(value, field, errors):
    if value is None:
        return None
    if value.lower() in ("true", "1"):
        return True
    if value.lower() in ("false", "0"):
        return False
    errors[field] = "Must be true or false."
    return None


def parse_int_arg(value, field, errors, default, minimum, maximum):
    if value is None:
        return default
    try:
        number = int(value)
    except ValueError:
        errors[field] = "Must be an integer."
        return default
    if not minimum <= number <= maximum:
        errors[field] = f"Must be between {minimum} and {maximum}."
        return default
    return number
