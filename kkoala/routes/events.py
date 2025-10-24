from flask import Blueprint, request, jsonify, current_app, session
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import uuid
import icalendar

from ..extensions import db
from ..models import Event, User, Settings, PrioritySetting
from ..utils import csrf_protect, login_required, str_to_bool
from ..algorithms import learning_time_algorithm

events_bp = Blueprint("events", __name__)

@events_bp.route("/", methods=["GET"])
@login_required
def get_events():
    """
    API endpoint to fetch all calendar events for the logged-in user.

    Returns:
        JSON: A list of all user events formatted for the calendar (FullCalendar).
    """
    logged_in_user = User.query.filter_by(username=session.get("username")).first()
    if not logged_in_user:
        return jsonify([])
    logged_in_user_id = logged_in_user.id
    user_events = Event.query.filter_by(user_id=logged_in_user_id).all()
    # Format events into a dictionary list for JSON response
    events = [
        {
            "id": event.id,
            "title": event.title,
            "start": event.start,
            "end": event.end,
            "color": event.color,
            "priority": event.priority,
            "recurrence": event.recurrence,
            "recurrence_id": event.recurrence_id,
            "allDay": event.all_day,
        }
        for event in user_events
    ]
    return jsonify(events), 200


@events_bp.route("/", methods=["POST"])
@csrf_protect
@login_required
def create_event():
    """
    API endpoint to create a new event.

    Handles creation of single events, or multiple events for a recurrence series
    ('daily', 'weekly', 'monthly'). Sets color for exams based on priority settings.

    Returns:
        JSON: A success message and status code 201.
    """
    data = request.json
    user = User.query.filter_by(username=session["username"]).first()
    all_day = str_to_bool(data.get("all_day", False))

    # Set event color if it's an exam based on user settings
    if int(data["priority"]) > 0:
        prio_setting = PrioritySetting.query.join(Settings).filter(
            Settings.user_id == user.id,
            PrioritySetting.priority_level == int(data["priority"])
        ).first()
        if prio_setting:
            data["color"] = prio_setting.color

    # Handle recurring events
    if data["recurrence"] != "none":
        recurrence_id = str(uuid.uuid4().int) # Generate a unique ID for the series
        start_dt = datetime.fromisoformat(data["start"])
        end_dt = datetime.fromisoformat(data["end"]) if data.get("end") else None
        duration = end_dt - start_dt if end_dt else None

        # Logic to create multiple instances for daily, weekly, or monthly recurrence
        num_instances = 365 if data["recurrence"] == "daily" else 52 if data["recurrence"] == "weekly" else 12
        for i in range(num_instances):
            if data["recurrence"] == "daily":
                offset = timedelta(days=i)
            elif data["recurrence"] == "weekly":
                offset = timedelta(weeks=i)
            elif data["recurrence"] == "monthly":
                offset = relativedelta(months=i)

            new_start = start_dt + offset
            new_end = new_start + duration if duration else None

            new_event = Event(
                title=data["title"],
                start=new_start.isoformat(),
                end=new_end.isoformat() if new_end else None,
                color=data["color"],
                user_id=user.id,
                priority=data["priority"],
                recurrence=data["recurrence"],
                recurrence_id=recurrence_id,
                all_day=all_day,
                locked=True, # Recurring events are locked by default
                exam_id=None,
            )
            db.session.add(new_event)

        db.session.commit()
        return jsonify({"message": "Recurring events created"}), 201

    # Create a single event
    new_event = Event(
        title=data["title"],
        start=data["start"],
        end=data.get("end"),
        color=data["color"],
        user_id=user.id,
        priority=data["priority"],
        recurrence="None",
        recurrence_id="0",
        all_day=all_day,
        locked=True, # Single, user-created events are locked by default
        exam_id=None,
    )
    db.session.add(new_event)
    db.session.commit()
    return jsonify({"message": "Event created"}), 201


@events_bp.route("/", methods=["PUT"])
@csrf_protect
@login_required
def update_event():
    """
    API endpoint to update an existing event.

    Handles updating a single event instance, or updating the entire recurrence series.
    Adjusts dates/times for recurring events based on their pattern.

    Returns:
        JSON: A success message and status code 200.
    """
    data = request.json
    user = User.query.filter_by(username=session["username"]).first()

    # Case 1: Update a single event (or one that becomes a single event)
    if (
        data["edit-recurrence"] != "all"
        and data["recurrence-id"] == "0"
        or len(Event.query.filter_by(recurrence_id=data["recurrence-id"]).all()) == 1
    ):
        event = Event.query.get(data["id"])
        old_priority = event.priority
        # Update color if priority has changed (for exam events)
        if int(data["priority"]) != old_priority:
            if int(data["priority"]) > 0:
                prio_setting = PrioritySetting.query.join(Settings).filter(
                    Settings.user_id == user.id,
                    PrioritySetting.priority_level == int(data["priority"])
                ).first()
                if prio_setting:
                    data["color"] = prio_setting.color

        event.title = data["title"]
        event.start = data["start"]
        event.end = data.get("end")
        event.color = data["color"]
        event.priority = data["priority"]
        event.recurrence = "None" # Update a recurring event instance to a single event
        event.recurrence_id = "0"
        event.all_day = str_to_bool(data.get("all_day", False))
        event.locked = True
        db.session.commit()
        return jsonify({"message": "Event updated"}), 200
    else:
        # Case 2: Update all events in recurrence series
        events = Event.query.filter_by(recurrence_id=data["recurrence-id"]).all()
        new_start_datetime = datetime.fromisoformat(data["start"])
        new_start_time = new_start_datetime.time()
        new_start_date = new_start_datetime.date()
        recurrence_pattern = events[0].recurrence

        # Iterate over all events in the series and adjust their date/time based on the pattern
        for i, event in enumerate(events):
            event.title = data["title"]
            event.color = data["color"]
            event.priority = data["priority"]
            event.all_day = str_to_bool(data.get("all_day", False))
            event.locked = True # Lock recurring events on update
            current_start_datetime = datetime.fromisoformat(event.start)

            # Calculate the new start datetime based on the recurrence pattern and index
            if recurrence_pattern == "daily":
                updated_start_datetime = datetime.combine(
                    new_start_date + timedelta(days=i), new_start_time
                )
            elif recurrence_pattern == "weekly":
                updated_start_datetime = datetime.combine(
                    new_start_date + timedelta(weeks=i), new_start_time
                )
            elif recurrence_pattern == "monthly":
                updated_start_datetime = datetime.combine(
                    new_start_date + relativedelta(months=i), new_start_time
                )
            else:
                return jsonify({"message": "Unsupported recurrence pattern"}), 400

            event.start = updated_start_datetime.isoformat()
            if event.end: # Adjust the end time based on the original duration
                current_end_datetime = datetime.fromisoformat(event.end)
                duration = current_end_datetime - current_start_datetime
                updated_end_datetime = updated_start_datetime + duration
                event.end = updated_end_datetime.isoformat()

        db.session.commit()
        return jsonify({"message": "Recurring events updated"}), 200


@events_bp.route("/<int:event_id>", methods=["DELETE"])
@csrf_protect
@login_required
def delete_event(event_id):
    """
    API endpoint to delete a single event by its ID.

    Args:
        event_id (int): The ID of the event to delete.

    Returns:
        JSON: A success message and status code 200, or a 404 error.
    """
    event = Event.query.get(event_id)
    if event:
        db.session.delete(event)
        db.session.commit()
        return jsonify({"message": "Event deleted"}), 200
    return jsonify({"message": "Event not found"}), 404


@events_bp.route("/recurring/<recurrence_id>", methods=["DELETE"])
@csrf_protect
@login_required
def delete_recurring_events(recurrence_id):
    """
    API endpoint to delete all events associated with a specific recurrence ID.

    Args:
        recurrence_id (str): The unique ID of the recurrence series to delete.

    Returns:
        JSON: A success message and status code 200, or a 401 error.
    """
    logged_in_user = User.query.filter_by(username=session.get("username")).first()
    if not logged_in_user:
        return jsonify({"error": "Unauthorized"}), 401
    Event.query.filter_by(
        recurrence_id=recurrence_id, user_id=logged_in_user.id
    ).delete() # Mass delete
    db.session.commit()
    return jsonify({"message": "Recurring events deleted"}), 200


@events_bp.route("/run-learning-algorithm", methods=["POST"])
@csrf_protect
@login_required
def run_learning_algorithm():
    """
    API endpoint to trigger the study scheduling algorithm.

    Fetches all user events, runs the algorithm, and returns the scheduling results.

    Returns:
        JSON: A dictionary containing the scheduling summary and results per exam.
    """
    user = User.query.filter_by(username=session["username"]).first()
    # Get all events for the user (this list is modified/updated by the algorithm)
    events = Event.query.filter_by(user_id=user.id).all()
    summary, successes = learning_time_algorithm(events, user)
    return jsonify({"status": "success",
                    "summary": summary,
                    "results": successes
                    })


@events_bp.route("/import-ics", methods=["POST"])
@csrf_protect
@login_required
def import_ics():
    """
    API endpoint to import events from an .ics file using the icalendar library.

    Parses the ICS content and creates new Event records for each VEVENT found.
    Imported events are given a default priority (4) and color.

    Returns:
        JSON: A success message and status code 200, or a 400/500 error.
    """
    data = request.json
    ics_content = data.get("ics")
    if not ics_content:
        return jsonify({"message": "No .ics content provided"}), 400

    try:
        calendar = icalendar.Calendar.from_ical(ics_content)
        logged_in_user = User.query.filter_by(username=session.get("username")).first()
        if not logged_in_user:
            return jsonify({"message": "No logged-in user found"}), 400

        for component in calendar.walk():
            if component.name == "VEVENT":
                title = str(component.get("SUMMARY", "Untitled Event"))
                # DTSTART/DTEND objects are converted to datetime objects
                start = component.get("DTSTART").dt
                end = component.get("DTEND").dt if component.get("DTEND") else None
                color = "#fcba03" # Default color for imported events

                new_event = Event(
                    title=title,
                    start=start.isoformat(),
                    end=end.isoformat() if end else None,
                    color=color,
                    user_id=logged_in_user.id,
                    priority=4, # Assigns a default priority of 4 to imported events
                    recurrence="None",
                    recurrence_id="0",
                    locked=True,
                )
                db.session.add(new_event)

        db.session.commit()
        return jsonify({"message": "Events imported successfully"}), 200
    except Exception as e:
        return jsonify({"message": f"Failed to import .ics file: {str(e)}"}), 500


@events_bp.route("/populate_test_algorithm", methods=["POST", "GET"])
@csrf_protect
@login_required
def populate_test_algorithm():
    """
    Utility route to clear all existing events and populate the database
    with a standard set of test exams (P1, P2, P3) and busy events.

    This is intended for development and testing of the algorithm.

    Returns:
        str: A confirmation message and status code 201.
    """
    user = User.query.filter_by(username=session["username"]).first()
    user_id = user.id

    # Clear all existing events for this user before populating
    Event.query.filter_by(user_id=user_id).delete()
    db.session.commit()

    # Define test data relative to today
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # ... (event creation code omitted for brevity) ...
    # Events are created here: exam1 (P1, 10 days out), exam2 (P2, 7 days out), exam3 (P3, 4 days out), and busy events.

    exam1 = Event(
        user_id=user_id, title="Math Exam", start=(today + timedelta(days=10, hours=9)).isoformat(),
        end=(today + timedelta(days=10, hours=11)).isoformat(), color="#770000", priority=1,
        recurrence="None", recurrence_id="0", all_day=False, locked=True, exam_id=None,
    )
    exam2 = Event(
        user_id=user_id, title="History Exam", start=(today + timedelta(days=7, hours=13)).isoformat(),
        end=(today + timedelta(days=7, hours=15)).isoformat(), color="#ca8300", priority=2,
        recurrence="None", recurrence_id="0", all_day=False, locked=True, exam_id=None,
    )
    exam3 = Event(
        user_id=user_id, title="Biology Exam", start=(today + timedelta(days=4, hours=8)).isoformat(),
        end=(today + timedelta(days=4, hours=10)).isoformat(), color="#097200", priority=3,
        recurrence="None", recurrence_id="0", all_day=False, locked=True, exam_id=None,
    )

    busy1 = Event(
        user_id=user_id, title="Class: English", start=(today + timedelta(days=1, hours=10)).isoformat(),
        end=(today + timedelta(days=1, hours=12)).isoformat(), color="#4287f5", priority=5,
        recurrence="None", recurrence_id="0", all_day=False, locked=True, exam_id=None,
    )
    busy2 = Event(
        user_id=user_id, title="Doctor Appointment", start=(today + timedelta(days=2, hours=15)).isoformat(),
        end=(today + timedelta(days=2, hours=16)).isoformat(), color="#8e44ad", priority=5,
        recurrence="None", recurrence_id="0", all_day=False, locked=True, exam_id=None,
    )
    busy3 = Event(
        user_id=user_id, title="Class: Chemistry", start=(today + timedelta(days=5, hours=9)).isoformat(),
        end=(today + timedelta(days=5, hours=11)).isoformat(), color="#16a085", priority=5,
        recurrence="None", recurrence_id="0", all_day=False, locked=True, exam_id=None,
    )
    busy4 = Event(
        user_id=user_id, title="Sports Practice", start=(today + timedelta(days=6, hours=17)).isoformat(),
        end=(today + timedelta(days=6, hours=19)).isoformat(), color="#e67e22", priority=5,
        recurrence="None", recurrence_id="0", all_day=False, locked=True, exam_id=None,
    )

    non_exam = Event(
        user_id=user_id, title="Read a book", start=(today + timedelta(days=3, hours=18)).isoformat(),
        end=(today + timedelta(days=3, hours=19)).isoformat(), color="#888888", priority=0,
        recurrence="None", recurrence_id="0", all_day=False, locked=True, exam_id=None,
    )

    db.session.add_all([exam1, exam2, exam3, busy1, busy2, busy3, busy4, non_exam])
    db.session.commit()
    return "Test events for the learning time algorithm have been populated!", 201

