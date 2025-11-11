# Standard library imports
from functools import wraps
from flask import session, redirect, url_for, request, jsonify, current_app
from datetime import datetime, timedelta, time as dtime, timezone
import secrets
from dateutil import parser

# Application-specific imports
from .consts import DAY_START
from .models import User  # Import the User model for authentication


def str_to_bool(val):
    """
    Convert a string or boolean value to a boolean.

    Args:
        val (str | bool): The value to convert.

    Returns:
        bool: The boolean representation of the input value.
    """
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() == "true"
    return False


def login_required(f):
    """
    Decorator to ensure a user is logged in and exists in the database.

    - Redirects to login page if not logged in (for HTML requests).
    - Returns 401 JSON error for API requests if not logged in.
    - Passes the fetched user object as the first argument to the decorated view.

    Args:
        f (function): The view function to wrap.

    Returns:
        function: The decorated function.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        username = session.get("username")
        if not username:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized: Not logged in"}), 401
            return redirect(url_for("auth.login"))

        user = User.query.filter_by(username=username).first()
        if not user:
            # Handle case where user is in session but not in DB
            if request.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized: User not found"}), 401
            return redirect(url_for("auth.login"))

        # Pass the fetched user object to the route function
        return f(user, *args, **kwargs)

    return decorated_function


def csrf_protect(f):
    """
    Decorator to protect a route from CSRF attacks.

    - Checks for a valid CSRF token in the session and request (form or header).
    - Skips check if app is in TESTING mode.
    - Returns 400 error if token is missing or invalid.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Only check for state-changing methods
        if current_app.config.get("TESTING"):
            return f(*args, **kwargs)

        if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
            token = session.get("csrf_token")
            if not token:
                return jsonify({"error": "CSRF token missing from session"}), 400

            # Get token from form or from header (for AJAX)
            request_token = request.form.get("csrf_token") or request.headers.get(
                "X-CSRF-Token"
            )

            if not request_token:
                return jsonify({"error": "CSRF token missing from request"}), 400

            # Use secrets.compare_digest for secure, timing-attack-resistant comparison
            if not secrets.compare_digest(token, request_token):
                return jsonify({"error": "Invalid CSRF token"}), 400

        return f(*args, **kwargs)

    return decorated_function


def make_csrf_token():
    """
    Generates and stores a CSRF token in the session if not already present.
    Skips token generation in TESTING mode.
    """
    if current_app.config.get("TESTING"):
        return
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)


def to_dt(iso_or_dt) -> datetime:
    """
    Robustly convert an ISO string or a datetime object to a timezone-aware UTC datetime.

    Args:
        iso_or_dt (str | datetime): The input value.

    Returns:
        datetime: Timezone-aware UTC datetime object.
    """
    if not iso_or_dt:
        return None

    # If it's already a datetime object, just make it timezone-aware.
    if isinstance(iso_or_dt, datetime):
        if iso_or_dt.tzinfo is None:
            return iso_or_dt.replace(tzinfo=timezone.utc)
        return iso_or_dt.astimezone(timezone.utc)

    # If it's a string, parse it.
    if isinstance(iso_or_dt, str):
        try:
            # Use fromisoformat for standard ISO strings
            dt = datetime.fromisoformat(iso_or_dt.replace("Z", "+00:00"))
        except ValueError:
            # Fallback to dateutil.parser for more lenient parsing
            dt = parser.parse(iso_or_dt)

        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    # Handle other unexpected types
    raise TypeError(f"Unsupported type for to_dt: {type(iso_or_dt)}")


def to_iso(dt: datetime) -> str:
    """
    Return an ISO string in UTC (with Z) from a datetime or None.

    Args:
        dt (datetime): The datetime object.

    Returns:
        str: ISO 8601 formatted string in UTC.
    """
    if dt is None:
        return None
    # Ensure the datetime is in UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def free_slots(events, day):
    """
    Calculates free time slots for a given day, respecting existing events
    and applying a 30-minute margin (buffer) around them.

    Args:
        events (list): List of event objects with start/end attributes.
        day (date): The day for which to calculate free slots.

    Returns:
        list: List of (start_datetime, end_datetime) tuples representing free slots.
    """
    from zoneinfo import ZoneInfo

    DAY_END = dtime(22, 0)
    USER_TZ = ZoneInfo("Europe/Zurich")  # Define user timezone

    # Filter events for the given day and sort by start time
    events_today = [event for event in events if to_dt(event.start).date() == day]
    events_today.sort(key=lambda event: to_dt(event.start))

    free_slots = []

    # Convert local DAY_START to UTC
    naive_day_start = datetime.combine(day, DAY_START)
    current_start = naive_day_start.replace(tzinfo=USER_TZ).astimezone(timezone.utc)

    for event in events_today:
        event_start = to_dt(event.start)
        event_end = to_dt(event.end) if event.end else to_dt(event_start)
        if event.all_day:
            return []  # No free slots if there's an all-day event

        # Add free slot before the event, with 30 min buffer
        if current_start <= event_start - timedelta(minutes=30):
            free_slots.append((current_start, event_start - timedelta(minutes=30)))

        # Move current_start to after this event (with 30 min buffer)
        current_start = max(current_start, event_end + timedelta(minutes=30))

    # Convert local DAY_END to UTC
    naive_day_end = datetime.combine(day, DAY_END)
    day_end_dt = naive_day_end.replace(tzinfo=USER_TZ).astimezone(timezone.utc)

    # Add final free slot if any time remains after last event
    if current_start <= day_end_dt:
        free_slots.append((current_start, day_end_dt))

    return free_slots
