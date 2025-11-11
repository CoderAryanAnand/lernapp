# Import Flask modules for routing, request handling, and responses
from flask import Blueprint, request, jsonify, current_app, session, Response
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import uuid
import icalendar

# Import application extensions and models
from ..extensions import db
from ..models import Event, User, Settings, PrioritySetting
from ..utils import csrf_protect, login_required, str_to_bool
from ..algorithms import learning_time_algorithm
from ..consts import DEFAULT_IMPORT_COLOR

# Define the blueprint for event-related API routes
events_bp = Blueprint("events", __name__)

@events_bp.route("/", methods=["GET"])
@login_required
def get_events(user):
    """
    Fetch all calendar events for the logged-in user.

    Returns:
        JSON: List of all user events formatted for the calendar (FullCalendar).
    """
    user_events = Event.query.filter_by(user_id=user.id).all()
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
def create_event(user):
    """
    Create a new event (single or recurring).

    Handles creation of single events, or multiple events for a recurrence series
    ('daily', 'weekly', 'monthly'). Sets color for exams based on priority settings.

    Returns:
        JSON: Success message and status code 201.
    """
    data = request.json
    all_day = str_to_bool(data.get("all_day", False))
    end_str = data.get("end")

    # Adjust end date for all-day events (add one day)
    if all_day and end_str:
        end_dt = datetime.fromisoformat(end_str)
        end_dt += timedelta(days=1)
        end_str = end_dt.isoformat()

    # Set event color if it's an exam based on user settings
    if int(data["priority"]) > 0:
        prio_setting = (
            PrioritySetting.query.join(Settings)
            .filter(
                Settings.user_id == user.id,
                PrioritySetting.priority_level == int(data["priority"]),
            )
            .first()
        )

    # Handle recurring events
    if data["recurrence"] != "none":
        recurrence_id = str(uuid.uuid4().int)  # Generate a unique ID for the series
        start_dt = datetime.fromisoformat(data["start"])
        end_dt = datetime.fromisoformat(end_str) if end_str else None
        duration = end_dt - start_dt if end_dt else None

        # Determine number of instances based on recurrence pattern
        num_instances = (
            365
            if data["recurrence"] == "daily"
            else 52 if data["recurrence"] == "weekly" else 12
        )
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
                locked=True,  # Recurring events are locked by default
                exam_id=None,
            )
            db.session.add(new_event)

        db.session.commit()
        return jsonify({"message": "Recurring events created"}), 201

    # Create a single event
    new_event = Event(
        title=data["title"],
        start=data["start"],
        end=end_str,
        color=data["color"],
        user_id=user.id,
        priority=data["priority"],
        recurrence="None",
        recurrence_id="0",
        all_day=all_day,
        locked=True,  # Single, user-created events are locked by default
        exam_id=None,
    )
    db.session.add(new_event)
    db.session.commit()
    return jsonify({"message": "Event created"}), 201

@events_bp.route("/", methods=["PUT"])
@csrf_protect
@login_required
def update_event(user):
    """
    Update an existing event (single or entire recurrence series).

    Handles updating a single event instance, or updating the entire recurrence series.
    Adjusts dates/times for recurring events based on their pattern.

    Returns:
        JSON: Success message and status code 200.
    """
    data = request.json
    all_day = str_to_bool(data.get("all_day", False))
    end_str = data.get("end")

    # Adjust end date for all-day events (add one day)
    if all_day and end_str:
        end_dt = datetime.fromisoformat(end_str)
        end_dt += timedelta(days=1)
        end_str = end_dt.isoformat()

    # Case 1: Update a single event (or one that becomes a single event)
    if (
        data["edit-recurrence"] != "all"
        or len(Event.query.filter_by(recurrence_id=data["recurrence-id"]).all()) == 1
    ):
        event = Event.query.get(data["id"])
        if not event or event.user_id != user.id:
            return jsonify({"message": "Event not found or unauthorized"}), 404

        old_priority = event.priority
        # Update color if priority has changed (for exam events)
        if int(data["priority"]) != old_priority:
            if int(data["priority"]) > 0:
                prio_setting = (
                    PrioritySetting.query.join(Settings)
                    .filter(
                        Settings.user_id == user.id,
                        PrioritySetting.priority_level == int(data["priority"]),
                    )
                    .first()
                )

        event.title = data["title"]
        event.start = data["start"]
        event.end = end_str
        event.color = data["color"]
        event.priority = data["priority"]
        event.recurrence = "None"  # Update a recurring event instance to a single event
        event.recurrence_id = "0"
        event.all_day = all_day
        event.locked = True
        db.session.commit()
        return jsonify({"message": "Event updated"}), 200
    else:
        # Case 2: Update all events in recurrence series
        events = Event.query.filter_by(
            recurrence_id=data["recurrence-id"], user_id=user.id
        ).all()
        if not events:
            return (
                jsonify({"message": "Recurring events not found or unauthorized"}),
                404,
            )

        new_start_datetime = datetime.fromisoformat(data["start"])
        new_end_datetime = datetime.fromisoformat(end_str) if end_str else None
        new_duration = (
            new_end_datetime - new_start_datetime if new_end_datetime else None
        )

        new_start_time = new_start_datetime.time()
        new_start_date = new_start_datetime.date()
        recurrence_pattern = events[0].recurrence

        # Iterate over all events in the series and adjust their date/time based on the pattern
        for i, event in enumerate(events):
            event.title = data["title"]
            event.color = data["color"]
            event.priority = data["priority"]
            event.all_day = all_day
            event.locked = True  # Lock recurring events on update

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
            # Adjust the end time based on the new duration
            if new_duration is not None:
                updated_end_datetime = updated_start_datetime + new_duration
                event.end = updated_end_datetime.isoformat()
            else:
                event.end = None

        db.session.commit()
        return jsonify({"message": "Recurring events updated"}), 200

@events_bp.route("/<int:event_id>", methods=["DELETE"])
@csrf_protect
@login_required
def delete_event(user, event_id):
    """
    Delete a single event by its ID.

    Args:
        event_id (int): The ID of the event to delete.

    Returns:
        JSON: Success message and status code 200, or a 404 error.
    """
    event = Event.query.get(event_id)
    if event and event.user_id == user.id:
        db.session.delete(event)
        db.session.commit()
        return jsonify({"message": "Event deleted"}), 200
    return jsonify({"message": "Event not found or unauthorized"}), 404

@events_bp.route("/recurring/<recurrence_id>", methods=["DELETE"])
@csrf_protect
@login_required
def delete_recurring_events(user, recurrence_id):
    """
    Delete all events associated with a specific recurrence ID.

    Args:
        recurrence_id (str): The unique ID of the recurrence series to delete.

    Returns:
        JSON: Success message and status code 200.
    """
    Event.query.filter_by(
        recurrence_id=recurrence_id, user_id=user.id
    ).delete()  # Mass delete
    db.session.commit()
    return jsonify({"message": "Recurring events deleted"}), 200

@events_bp.route("/run-learning-algorithm", methods=["POST"])
@csrf_protect
@login_required
def run_learning_algorithm(user):
    """
    Trigger the study scheduling algorithm for the user.

    Fetches all user events, runs the algorithm, and returns the scheduling results.

    Returns:
        JSON: Dictionary containing the scheduling summary and results per exam.
    """
    try:
        events = Event.query.filter_by(user_id=user.id).all()
        summary, successes = learning_time_algorithm(events, user)
        return (
            jsonify({"status": "success", "summary": summary, "results": successes}),
            200,
        )
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Error running learning_time_algorithm")
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

@events_bp.route("/import-ics", methods=["POST"])
@csrf_protect
@login_required
def import_ics(user):
    """
    Import events from an .ics file using the icalendar library.

    Parses the ICS content and creates new Event records for each VEVENT found.
    Imported events are given a default priority (4) and color.

    Returns:
        JSON: Success message and status code 200, or a 400/500 error.
    """
    data = request.json
    ics_content = data.get("ics")
    user_settings = Settings.query.filter_by(user_id=user.id).first()
    if not ics_content:
        return jsonify({"message": "No .ics content provided"}), 400

    try:
        calendar = icalendar.Calendar.from_ical(ics_content)

        for component in calendar.walk():
            if component.name == "VEVENT":
                title = str(component.get("summary"))
                start = component.get("dtstart").dt
                end = component.get("dtend").dt if component.get("dtend") else None
                is_all_day = not isinstance(start, datetime)
                # Read custom Kanti Koala tags if present
                priority = component.get("X-KKOALA-PRIORITY")
                color = component.get("X-KKOALA-COLOR")

                settings = Settings.query.filter_by(user_id=user.id).first()

                if settings and settings.priority_settings:
                    all_priorities = [p.priority_level for p in settings.priority_settings]
                    if all_priorities:
                        # An exam is any priority that is not the maximum (lowest) one
                        lowest_priority = max(all_priorities) + 1

                if priority is not None:
                    priority = int(priority)
                else:
                    priority = lowest_priority
                if color is None:
                    color = DEFAULT_IMPORT_COLOR

                new_event = Event(
                    title=title,
                    start=start.isoformat(),
                    end=end.isoformat() if end else None,
                    color=color,
                    user_id=user.id,
                    priority=priority,
                    recurrence="None",
                    recurrence_id="0",
                    locked=True,
                    all_day=is_all_day,
                )
                db.session.add(new_event)

        db.session.commit()
        return jsonify({"message": "Events imported successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Failed to import .ics file: {str(e)}"}), 500

@events_bp.route("/export-ics", methods=["GET"])
@login_required
def export_ics(user):
    """
    Export all user events as an .ics file.

    Returns:
        Response: A downloadable .ics file containing all user events.
    """
    user_events = Event.query.filter_by(user_id=user.id).all()
    
    # Create a new iCalendar object
    cal = icalendar.Calendar()
    cal.add('prodid', '-//Kanti Koala//kantikoala.com//')
    cal.add('version', '2.0')
    
    for event in user_events:
        vevent = icalendar.Event()
        vevent.add('summary', event.title)
        if event.all_day:
            # Use only the date part for all-day events
            vevent.add('dtstart', datetime.fromisoformat(event.start).date())
            if event.end:
                vevent.add('dtend', datetime.fromisoformat(event.end).date())
        else:
            vevent.add('dtstart', datetime.fromisoformat(event.start))
            if event.end:
                vevent.add('dtend', datetime.fromisoformat(event.end))
        vevent.add('uid', f'{event.id}@kantikoala.com')
        vevent.add('description', f'Priority: {event.priority}')
        vevent.add('color', event.color)
        vevent.add('X-KKOALA-PRIORITY', str(event.priority))
        vevent.add('X-KKOALA-COLOR', event.color)
        cal.add_component(vevent)
    
    # Generate the .ics file content
    ics_content = cal.to_ical()
    
    # Return as a downloadable file
    return Response(
        ics_content,
        mimetype='text/calendar',
        headers={
            'Content-Disposition': 'attachment; filename=kantikoala_events.ics'
        }
    )
