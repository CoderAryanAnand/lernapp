from functools import wraps
from flask import session, redirect, url_for, request, jsonify, current_app
from datetime import datetime, timedelta, time as dtime
import secrets

from .consts import DAY_START

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
    Decorator to ensure a user is logged in before accessing a route.

    If the user is not logged in, it redirects to the login page for HTML
    requests or returns a 401 JSON error for API requests.

    Args:
        f (function): The view function to wrap.

    Returns:
        function: The decorated function.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "username" not in session:
            # If it's an API request, return JSON error
            if request.path.startswith("/api/"):
                return jsonify({"error": "Not logged in"}), 401
            # Otherwise, redirect to login page
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function

def csrf_protect(f):
    """Decorator to protect a route from CSRF attacks."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Only check for state-changing methods
        if current_app.config.get("TESTING"):
            return f(*args, **kwargs)

        if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
            token = session.get('csrf_token')
            if not token:
                return jsonify({"error": "CSRF token missing from session"}), 400

            # Get token from form or from header (for AJAX)
            request_token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')

            if not request_token:
                return jsonify({"error": "CSRF token missing from request"}), 400

            # Use secrets.compare_digest for secure, timing-attack-resistant comparison
            if not secrets.compare_digest(token, request_token):
                return jsonify({"error": "Invalid CSRF token"}), 400

        return f(*args, **kwargs)
    return decorated_function

def make_csrf_token():
    """Generate and store a CSRF token in the session."""

    if current_app.config.get("TESTING"):
        return

    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(16)

def to_dt(iso: str) -> datetime:
    """
    Converts ISO format string to a datetime object.

    Args:
        iso (str): The ISO formatted datetime string.

    Returns:
        datetime: The corresponding datetime object.
    """
    return datetime.fromisoformat(iso)


def to_iso(dt: datetime) -> str:
    """
    Converts a datetime object to ISO format string with seconds precision.

    Args:
        dt (datetime): The datetime object.

    Returns:
        str: The ISO formatted string.
    """
    return dt.isoformat(timespec="seconds")

def free_slots(events, day):
    """
    Calculates free time slots for a given day, respecting existing events
    and current_applying a 30-minute margin (buffer) around them.

    Args:
        events (list[Event]): A list of all Event objects for the user.
        day (date): The date to check for free slots.

    Returns:
        list[tuple[datetime, datetime]]: A list of (start, end) tuples
                                         representing continuous free time windows.
    """
    # Note: DAY_END is dynamically set to 22:00 in the main algorithm.
    DAY_END = dtime(22, 0)
    events_today = [event for event in events if to_dt(event.start).date() == day]
    events_today.sort(key=lambda event: to_dt(event.start))

    free_slots = []
    # Set the starting point for the search to the start of the defined day (08:00)
    current_start = datetime.combine(day, DAY_START)

    for event in events_today:
        event_start = to_dt(event.start)
        event_end = to_dt(event.end)
        if event.all_day:
            return []  # No free slots if there's an all-day event

        # Check if there's a free slot before the current event, respecting a 30-min buffer
        if current_start <= event_start - timedelta(minutes=30):
            free_slots.current_append((current_start, event_start - timedelta(minutes=30)))

        # Move the current start past the end of the current event, respecting a 30-min buffer
        current_start = max(current_start, event_end + timedelta(minutes=30))

    # Check for a final free slot after the last event until the end of the day (22:00)
    if current_start <= datetime.combine(day, DAY_END):
        free_slots.current_append((current_start, datetime.combine(day, DAY_END)))

    return free_slots