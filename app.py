# Import necessary libraries and modules
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_mailman import Mail, EmailMessage
from functools import wraps
import icalendar
import uuid
from datetime import datetime, timedelta, time as dtime
from itsdangerous import URLSafeTimedSerializer
from dateutil.relativedelta import relativedelta  # for monthly recurrence
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# ---------------------- Flask App Configuration ----------------------

# Database configuration
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db"  # Use SQLite by default
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = (
    False  # Disable modification tracking for performance
)
app.secret_key = os.getenv("SECRET_KEY")  # Secret key for session management

# Mail configuration
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USE_SSL"] = False
app.config["MAIL_USERNAME"] = "kantikoala@gmail.com"
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")

# ---------------------- Initialize Extensions ----------------------

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
mail = Mail(app)

# ----------------------- Defaults -----------------------
DEFAULT_SETTINGS = {"learn_on_saturday": False, "learn_on_sunday": False, "preferred_learning_time": "18:00", "study_block_color": "#0000FF",
                    "priority_settings": {1: {"color": "#770000", "days_to_learn": 14, "max_hours_per_day": 2.0, "total_hours_to_learn": 14.0},
                                          2: {"color": "#ca8300", "days_to_learn": 7, "max_hours_per_day": 1.5, "total_hours_to_learn": 7.0},
                                          3: {"color": "#097200", "days_to_learn": 4, "max_hours_per_day": 1.0, "total_hours_to_learn": 4.0}
                    }
}

# ---------------------- Database Models ----------------------


class User(db.Model):
    """User model for storing authentication details."""

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)  # Hashed password
    email = db.Column(db.String(100), unique=True, nullable=False)

    # Relationships
    events = db.relationship(
        "Event", backref="user", lazy=True, cascade="all, delete-orphan"
    )
    semesters = db.relationship(
        "Semester", backref="user", lazy=True, cascade="all, delete-orphan"
    )
    settings = db.relationship(
        "Settings", backref="user", lazy=True, cascade="all, delete-orphan"
    )


class Settings(db.Model):
    """Settings model for storing user-specific settings."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    learn_on_saturday = db.Column(db.Boolean, default=False)
    learn_on_sunday = db.Column(db.Boolean, default=False)
    preferred_learning_time = db.Column(db.String(20), default="18:00")
    study_block_color = db.Column(db.String(7), default="#0000FF")

    priority_settings = db.relationship(
        "PrioritySetting", backref="settings", lazy=True, cascade="all, delete-orphan"
    )


class PrioritySetting(db.Model):
    """PrioritySetting model for storing user-specific priority settings."""
    id = db.Column(db.Integer, primary_key=True)
    settings_id = db.Column(db.Integer, db.ForeignKey("settings.id"), nullable=False)
    priority_level = db.Column(db.Integer, nullable=False)
    color = db.Column(db.String(7), nullable=False)
    days_to_learn = db.Column(db.Integer, nullable=False)
    max_hours_per_day = db.Column(db.Float, nullable=False)
    total_hours_to_learn = db.Column(db.Float, nullable=False)


class Event(db.Model):
    """Event model for storing user events."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id", onupdate="CASCADE"), nullable=False
    )
    title = db.Column(db.String(100), nullable=False)
    start = db.Column(db.String(50), nullable=False)  # ISO format
    end = db.Column(db.String(50), nullable=True)
    color = db.Column(db.String(7), nullable=False)
    priority = db.Column(db.Integer, nullable=False)
    recurrence = db.Column(db.String(50), nullable=True)
    recurrence_id = db.Column(db.String(50), nullable=True)
    all_day = db.Column(db.Boolean, nullable=False, default=False)

    # Following fields are for the algorithm
    locked = db.Column(db.Boolean, default=True)
    exam_id = db.Column(db.Integer, nullable=True)


class Semester(db.Model):
    """Semester model for storing academic semesters."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)

    # Relationship to subjects with cascade delete
    subjects = db.relationship(
        "Subject", backref="semester", lazy=True, cascade="all, delete-orphan"
    )


class Subject(db.Model):
    """Subject model for storing subjects within a semester."""

    id = db.Column(db.Integer, primary_key=True)
    semester_id = db.Column(db.Integer, db.ForeignKey("semester.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)

    # Relationship to grades with cascade delete
    grades = db.relationship(
        "Grade", backref="subject", lazy=True, cascade="all, delete-orphan"
    )


class Grade(db.Model):
    """Grade model for storing grades for subjects."""

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    value = db.Column(db.Float, nullable=False)
    weight = db.Column(db.Float, nullable=False)
    counts = db.Column(db.Boolean, nullable=False, default=True)


# ---------------------- Database Initialization ----------------------

with app.app_context():
    db.create_all()
    # Enable foreign key support for SQLite
    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
        with db.engine.connect() as connection:
            connection.execute(db.text("PRAGMA foreign_keys=ON"))

# ---------------------- Utility Functions ----------------------


def str_to_bool(val):
    """Convert a string or boolean value to a boolean."""
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() == "true"
    return False


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "username" not in session:
            # If it's an API request (e.g., starts with /api/), return JSON error
            if request.path.startswith("/api/"):
                return jsonify({"error": "Not logged in"}), 401
            # Otherwise, redirect to login page
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


# ---------------------- Learning Time Algorithm ----------------------

# ---------- CONFIG ----------
TOTAL_H     = {1: 14, 2: 7, 3: 4}   # hours
MAX_PER_DAY = {1: 3,  2: 2, 3: 1}   # per-day ceiling
WINDOW_DAYS = {1: 14, 2: 7,  3: 4}  # ideal look-back
DAY_START   = dtime(8, 0)
DAY_END     = dtime(21, 0)
SESSION     = 1.0                     # smallest block (hours)
STUDY_BLOCK_COLOR = "#0000FF"

def to_dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso)

def to_iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")

def free_slots(events, day):
    """Calculate free time slots in a day given existing events. Free slots have a margin of 30 minutes between events."""
    events_today = [event for event in events if to_dt(event.start).date() == day]
    events_today.sort(key=lambda event: to_dt(event.start))

    free_slots = []
    current_start = datetime.combine(day, DAY_START)

    for event in events_today:
        event_start = to_dt(event.start)
        event_end = to_dt(event.end)
        if event.all_day:
            free_slots = []  # No free slots if there's an all-day event
            return free_slots

        # Check if there's a free slot before the current event
        if current_start <= event_start - timedelta(minutes=30):
            free_slots.append((current_start, event_start - timedelta(minutes=30)))

        # Move the current start to the end of the current event
        current_start = max(current_start, event_end + timedelta(minutes=30))

    # Check for a free slot after the last event until the end of the day
    if current_start <= datetime.combine(day, DAY_END):
        free_slots.append((current_start, datetime.combine(day, DAY_END)))

    return free_slots

def learning_time_algorithm(events, user):
    """
    Determines and schedules optimal learning times for a user based on their exams,
    existing events, and personalized study settings.

    The algorithm iterates through exams by priority, calculates the required study
    hours, deletes existing non-locked study blocks (recycling), and attempts to
    re-schedule the required hours. It prioritizes the user's preferred learning time
    and respects daily maximum hours and existing event conflicts.

    Args:
        events (list): A list of all calendar Event objects (including exams, sports,
                       and existing study blocks) for the user. This list is updated
                       in-place as new study blocks are created.
        user (User): The current user object, used to fetch settings.

    Returns:
        tuple: A dictionary summary of scheduling activity and a dictionary of
               exam-specific success/failure messages.
    """

    # --- Configuration and Initialization ---

    # Fetch user settings and priority configurations
    settings = Settings.query.filter_by(user_id=user.id).first()
    priority_settings = {p.priority_level: p for p in settings.priority_settings}
    if not priority_settings:
        return {"error": "No priority settings found"}, {}

    max_exam_priority = max(priority_settings.keys())

    # Load scheduling preferences from settings
    sat_learn = settings.learn_on_saturday
    sun_learn = settings.learn_on_sunday
    preferred_time = datetime.strptime(settings.preferred_learning_time, "%H:%M").time()
    study_block_color = settings.study_block_color if settings.study_block_color else "#0000FF"

    # Define constants (assuming these are defined elsewhere in app.py)
    # DAY_END: The latest time a block can end (e.g., 22:00)
    # SESSION: The minimum session duration in hours (e.g., 0.5 hours or 30 mins)
    DAY_END = dtime(22, 0)
    SESSION = 0.5

    # Identify all events flagged as exams (priority > 0)
    exams = sorted(
        [event for event in events if int(event.priority) > 0 and int(event.priority) <= max_exam_priority],
        key=lambda event: (int(event.priority), datetime.fromisoformat(event.start)) # Sort by priority, then date
    )

    summary = {"exams_processed": 0, "blocks_added": 0, "hours_added": 0.0}
    successes = {}

    # --- Main Exam Loop: Process each exam by priority ---

    for exam in exams:
        prio = int(exam.priority)
        prio_setting = priority_settings.get(prio)
        if not prio_setting:
            continue

        summary["exams_processed"] += 1
        total = prio_setting.total_hours_to_learn

        # Define the learning window
        window_days = prio_setting.days_to_learn
        max_per_day = prio_setting.max_hours_per_day

        window_start = to_dt(exam.start) - timedelta(days=window_days)
        window_end = to_dt(exam.start)

        # Separate study blocks related to this exam
        exam_blocks = [event for event in events if event.exam_id == exam.id]
        past_blocks = [block for block in exam_blocks if to_dt(block.start) < datetime.now()]
        future_blocks = [
            block for block in exam_blocks
            if to_dt(block.start) >= datetime.now()
            and window_start <= to_dt(block.start) < window_end
        ]

        # Calculate hours completed in the past
        hours_done = sum((to_dt(block.end) - to_dt(block.start)).total_seconds() / 3600 for block in past_blocks)

        # ------------------------------------------------------------------
        # Recycling Logic (Ensure non-locked blocks are always deleted first)
        # ------------------------------------------------------------------
        
        # 1. Separate locked and recyclable future blocks
        locked_future_blocks = [block for block in future_blocks if block.locked]
        recyclable_blocks = [block for block in future_blocks if not block.locked]
        
        # 2. Delete all recyclable blocks from the database and the global event list.
        for block in recyclable_blocks:
            db.session.delete(block)
            events.remove(block) # Crucial: Keeps the global list up-to-date
        db.session.commit()
        
        # 3. Recalculate hours_scheduled based ONLY on remaining locked blocks
        hours_scheduled_locked = sum(
            (to_dt(block.end) - to_dt(block.start)).total_seconds() / 3600 for block in locked_future_blocks
        )
        
        # 4. Calculate final hours_left for scheduling
        hours_left = max(0, total - hours_done - hours_scheduled_locked)
        
        if hours_left == 0:
            # If all required hours are covered by past or locked blocks, skip this exam.
            continue
        # ------------------------------------------------------------------

        # --- Scheduling Loop: Schedule remaining hours backwards from exam date ---
        
        new_scheduled = 0.0
        days_left_until_exam = (window_end.date() - datetime.now().date()).days
        
        # Iterate backwards day by day within the learning window
        for day_offset in range(1, days_left_until_exam + 1):
            current_day = window_end - timedelta(days=day_offset)

            if current_day.date() < window_start.date():
                continue # Outside the user-defined learning window
            
            # Check weekend settings
            if (not sat_learn and current_day.weekday() == 5) or (not sun_learn and current_day.weekday() == 6):
                continue
            
            if new_scheduled >= hours_left:
                break # Stop if all required hours have been scheduled

            # Calculate hours scheduled *for this specific exam* on current_day
            # This ensures the daily max for the exam is respected, even with new blocks added.
            scheduled_today_for_exam = sum(
                (to_dt(block.end) - to_dt(block.start)).total_seconds() / 3600
                for block in events
                if block.exam_id == exam.id and to_dt(block.start).date() == current_day.date()
            )

            # Determine max time to schedule today
            today_max = min(max_per_day - scheduled_today_for_exam, hours_left - new_scheduled)
            if today_max <= SESSION:
                continue # Not enough time for a minimum session

            # Filter today's events dynamically from the updated 'events' list
            events_today = [event for event in events if to_dt(event.start).date() == current_day.date()]

            # 1. Attempt to schedule in the preferred time slot
            preferred_start = datetime.combine(current_day.date(), preferred_time)
            preferred_end = preferred_start + timedelta(hours=today_max)
            if preferred_end.time() > DAY_END:
                preferred_end = datetime.combine(current_day.date(), DAY_END)

            preferred_slot_duration = (preferred_end - preferred_start).total_seconds() / 3600
            slot_free = True
            
            if preferred_slot_duration >= SESSION:
                # Check for overlap against all events_today (including newly scheduled study blocks)
                for event in events_today:
                    event_start = to_dt(event.start)
                    event_end = to_dt(event.end)
                    # Overlap condition: Checks if the preferred slot overlaps with any event,
                    # leaving at least a 30-minute buffer (SESSION / 2) on either side.
                    if not (preferred_end <= event_start - timedelta(minutes=30) or preferred_start >= event_end + timedelta(minutes=30)):
                        slot_free = False
                        break
            else:
                 slot_free = False

            if slot_free:
                # Create and save the new study block
                new_block = Event(
                    title=f"Learning for {exam.title}",
                    start=to_iso(preferred_start),
                    end=to_iso(preferred_end),
                    color=study_block_color,
                    user_id=exam.user_id,
                    exam_id=exam.id,
                    all_day=False,
                    priority=0,
                    locked=False,
                    recurrence="None",
                    recurrence_id="0",
                )
                db.session.add(new_block)
                db.session.commit()
                events.append(new_block) # Update global list
                new_scheduled += preferred_slot_duration
                summary["blocks_added"] += 1
                summary["hours_added"] += preferred_slot_duration
                continue # Move to next day
        
            # 2. If preferred slot is busy, search for the largest available free slot
            
            # The 'free_slots' helper function should use the current (updated) 'events' list
            slots = free_slots(events, current_day.date())
            slots.sort(key=lambda slot: slot[1] - slot[0], reverse=True) # Sort by duration descending

            for slot_start, slot_end in slots:
                slot_duration = (slot_end - slot_start).total_seconds() / 3600
                if slot_duration < SESSION:
                    continue

                # Allocate the maximum possible time (limited by slot duration, hours_left, and today_max)
                allocatable = min(slot_duration, hours_left - new_scheduled, today_max)
                if allocatable < SESSION:
                    continue

                block_start = slot_start
                block_end = slot_start + timedelta(hours=allocatable)

                # Create and save the new study block
                new_block = Event(
                    title=f"Learning for {exam.title}",
                    start=to_iso(block_start),
                    end=to_iso(block_end),
                    color=study_block_color,
                    user_id=exam.user_id,
                    exam_id=exam.id,
                    all_day=False,
                    priority=0,
                    locked=False,
                    recurrence="None",
                    recurrence_id="0",
                )
                db.session.add(new_block)
                db.session.commit()
                events.append(new_block) # Update global list
                new_scheduled += allocatable
                summary["blocks_added"] += 1
                summary["hours_added"] += allocatable

                if new_scheduled >= hours_left:
                    break
                
                break
            
        # --- Safety / Extra Days Extension (Beyond Initial Window) ---

        if new_scheduled < hours_left:
            # Check days outside the initial window (e.g., from day 15 up to day 21 back)
            for day_offset in range(window_days + 1, min(22, days_left_until_exam + 1)): 
                current_day = window_end - timedelta(days=day_offset)

                if new_scheduled >= hours_left:
                    break
                
                # ... (Scheduling logic mirrors the main loop for preferred and free slots) ...
                # (Includes dynamic recalculation of scheduled_today_for_exam and events_today)

                scheduled_today_for_exam = sum(
                    (to_dt(block.end) - to_dt(block.start)).total_seconds() / 3600
                    for block in events
                    if block.exam_id == exam.id and to_dt(block.start).date() == current_day.date()
                )
                
                today_max = min(max_per_day - scheduled_today_for_exam, hours_left - new_scheduled)
                if today_max <= SESSION:
                    continue

                events_today = [event for event in events if to_dt(event.start).date() == current_day.date()]

                # Preferred slot check
                preferred_start = datetime.combine(current_day.date(), preferred_time)
                preferred_end = preferred_start + timedelta(hours=today_max)
                if preferred_end.time() > DAY_END:
                    preferred_end = datetime.combine(current_day.date(), DAY_END)

                preferred_slot_duration = (preferred_end - preferred_start).total_seconds() / 3600
                slot_free = True
                if preferred_slot_duration >= SESSION:
                    for event in events_today:
                        event_start = to_dt(event.start)
                        event_end = to_dt(event.end)
                        if not (preferred_end <= event_start - timedelta(minutes=30) or preferred_start >= event_end + timedelta(minutes=30)):
                            slot_free = False
                            break
                else:
                    slot_free = False

                if slot_free:
                    # Create and save preferred block
                    new_block = Event(
                        title=f"Learning for {exam.title}",
                        start=to_iso(preferred_start),
                        end=to_iso(preferred_end),
                        color=study_block_color,
                        user_id=exam.user_id,
                        exam_id=exam.id,
                        all_day=False,
                        priority=0,
                        locked=False,
                        recurrence="None",
                        recurrence_id="0",
                    )
                    db.session.add(new_block)
                    db.session.commit()
                    events.append(new_block) # Update global list
                    new_scheduled += preferred_slot_duration
                    summary["blocks_added"] += 1
                    summary["hours_added"] += preferred_slot_duration
                    continue

                # General slot search
                slots = free_slots(events, current_day.date())
                slots.sort(key=lambda slot: slot[1] - slot[0], reverse=True)
                for slot_start, slot_end in slots:
                    slot_duration = (slot_end - slot_start).total_seconds() / 3600
                    if slot_duration < SESSION:
                        continue

                    allocatable = min(slot_duration, hours_left - new_scheduled, today_max)
                    if allocatable < SESSION:
                        continue

                    block_start = slot_start
                    block_end = slot_start + timedelta(hours=allocatable)

                    # Create and save general block
                    new_block = Event(
                        title=f"Learning for {exam.title}",
                        start=to_iso(block_start),
                        end=to_iso(block_end),
                        color=study_block_color,
                        user_id=exam.user_id,
                        exam_id=exam.id,
                        all_day=False,
                        priority=0,
                        locked=False,
                        recurrence="None",
                        recurrence_id="0",
                    )
                    db.session.add(new_block)
                    db.session.commit()
                    events.append(new_block) # Update global list
                    new_scheduled += allocatable
                    summary["blocks_added"] += 1
                    summary["hours_added"] += allocatable

                    if new_scheduled >= hours_left:
                        break
                    break # Move to next day after filling one slot
        
        # --- Final Status Update ---

        total_scheduled = new_scheduled + hours_scheduled_locked
        total_required = max(0, total - hours_done)

        if total_scheduled >= total_required:
            successes[exam.title] = [True, f"Successfully scheduled all {total_required:.1f} hours."]
        else:
            successes[exam.title] = [False, f"Could only schedule {total_scheduled:.1f} out of {total_required:.1f} hours."]
    
    return summary, successes
# ---------------------- API Endpoints for Events ----------------------


@app.route("/api/events", methods=["GET"])
@login_required
def get_events():
    """Fetch events for the logged-in user."""
    logged_in_user = User.query.filter_by(username=session.get("username")).first()
    if not logged_in_user:
        return jsonify([])
    logged_in_user_id = logged_in_user.id
    user_events = Event.query.filter_by(user_id=logged_in_user_id).all()
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
    return jsonify(events)


@app.route("/api/events", methods=["POST"])
@login_required
def create_event():
    """Create a new event."""
    data = request.json
    user = User.query.filter_by(username=session["username"]).first()
    all_day = str_to_bool(data.get("all_day", False))
    if int(data["priority"]) > 0:
        prio_setting = PrioritySetting.query.join(Settings).filter(
            Settings.user_id == user.id,
            PrioritySetting.priority_level == int(data["priority"])
        ).first()
        if prio_setting:
            data["color"] = prio_setting.color
    # Handle recurring events
    if data["recurrence"] != "none":
        recurrence_id = str(uuid.uuid4().int)
        if data["recurrence"] == "daily":
            for i in range(7):
                new_event = Event(
                    title=data["title"],
                    start=(
                        datetime.fromisoformat(data["start"]) + timedelta(days=i)
                    ).isoformat(),
                    end=(
                        (
                            datetime.fromisoformat(data["end"]) + timedelta(days=i)
                        ).isoformat()
                        if data.get("end")
                        else None
                    ),
                    color=data["color"],
                    user_id=user.id,
                    priority=data["priority"],
                    recurrence=data["recurrence"],
                    recurrence_id=recurrence_id,
                    all_day=all_day,
                    locked=True,
                    exam_id=None,
                )
                db.session.add(new_event)
        elif data["recurrence"] == "weekly":
            for i in range(4):
                new_event = Event(
                    title=data["title"],
                    start=(
                        datetime.fromisoformat(data["start"]) + timedelta(weeks=i)
                    ).isoformat(),
                    end=(
                        (
                            datetime.fromisoformat(data["end"]) + timedelta(weeks=i)
                        ).isoformat()
                        if data.get("end")
                        else None
                    ),
                    color=data["color"],
                    user_id=user.id,
                    priority=data["priority"],
                    recurrence=data["recurrence"],
                    recurrence_id=recurrence_id,
                    all_day=all_day,
                    locked=True,
                    exam_id=None,
                )
                db.session.add(new_event)
        elif data["recurrence"] == "monthly":
            for i in range(12):
                new_event = Event(
                    title=data["title"],
                    start=(
                        datetime.fromisoformat(data["start"]) + timedelta(weeks=i * 4)
                    ).isoformat(),
                    end=(
                        (
                            datetime.fromisoformat(data["end"]) + timedelta(weeks=i * 4)
                        ).isoformat()
                        if data.get("end")
                        else None
                    ),
                    color=data["color"],
                    user_id=user.id,
                    priority=data["priority"],
                    recurrence=data["recurrence"],
                    recurrence_id=recurrence_id,
                    all_day=all_day,
                    locked=True,
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
        locked=True,
        exam_id=None,
    )
    db.session.add(new_event)
    db.session.commit()
    return jsonify({"message": "Event created"}), 201


@app.route("/api/events", methods=["PUT"])
@login_required
def update_event():
    """Update an existing event."""
    data = request.json
    user = User.query.filter_by(username=session["username"]).first()
    # Single event or only one left in recurrence
    if (
        data["edit-recurrence"] != "all"
        and data["recurrence-id"] == "0"
        or len(Event.query.filter_by(recurrence_id=data["recurrence-id"]).all()) == 1
    ):
        event = Event.query.get(data["id"])
        old_priority = event.priority
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
        event.recurrence = "None"
        event.recurrence_id = "0"
        event.all_day = str_to_bool(data.get("all_day", False))
        event.locked = True
        db.session.commit()
        return jsonify({"message": "Event updated"}), 200
    else:
        # Update all events in recurrence
        events = Event.query.filter_by(recurrence_id=data["recurrence-id"]).all()
        new_start_datetime = datetime.fromisoformat(data["start"])
        new_start_time = new_start_datetime.time()
        new_start_date = new_start_datetime.date()
        recurrence_pattern = events[0].recurrence
        for i, event in enumerate(events):
            event.title = data["title"]
            event.color = data["color"]
            event.priority = data["priority"]
            event.all_day = str_to_bool(data.get("all_day", False))
            event.locked = True
            current_start_datetime = datetime.fromisoformat(event.start)
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
            if event.end:
                current_end_datetime = datetime.fromisoformat(event.end)
                duration = current_end_datetime - current_start_datetime
                updated_end_datetime = updated_start_datetime + duration
                event.end = updated_end_datetime.isoformat()
        db.session.commit()
        return jsonify({"message": "Recurring events updated"}), 200


@app.route("/api/events/<int:event_id>", methods=["DELETE"])
@login_required
def delete_event(event_id):
    """Delete an event."""
    event = Event.query.get(event_id)
    db.session.delete(event)
    db.session.commit()
    return jsonify({"message": "Event deleted"}), 200


@app.route("/api/events/recurring/<recurrence_id>", methods=["DELETE"])
@login_required
def delete_recurring_events(recurrence_id):
    """Delete all events with the same recurrence ID."""
    logged_in_user = User.query.filter_by(username=session.get("username")).first()
    if not logged_in_user:
        return jsonify({"error": "Unauthorized"}), 401
    Event.query.filter_by(
        recurrence_id=recurrence_id, user_id=logged_in_user.id
    ).delete()
    db.session.commit()
    return jsonify({"message": "Recurring events deleted"}), 200


@app.route('/api/run-learning-algorithm', methods=['POST'])
@login_required
def run_learning_algorithm():
    user = User.query.filter_by(username=session["username"]).first()
    events = Event.query.filter_by(user_id=user.id).all()
    summary, successes = learning_time_algorithm(events, user)
    return jsonify({"status": "success", 
                    "summary": summary, 
                    "results": successes
                    })


@app.route("/api/populate_test_algorithm", methods=["GET", "POST"])
@login_required
def populate_test_algorithm():
    """Populate the database with a good set of events to test the learning time algorithm."""
    user = User.query.filter_by(username=session["username"]).first()
    user_id = user.id

    # Clear all existing events for this user
    Event.query.filter_by(user_id=user_id).delete()
    db.session.commit()

    # Today and future dates
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    # Exams: priority 1 (in 10 days), priority 2 (in 7 days), priority 3 (in 4 days)
    exam1 = Event(
        user_id=user_id,
        title="Math Exam",
        start=(today + timedelta(days=10, hours=9)).isoformat(),
        end=(today + timedelta(days=10, hours=11)).isoformat(),
        color="#770000",
        priority=1,
        recurrence="None",
        recurrence_id="0",
        all_day=False,
        locked=True,
        exam_id=None,
    )
    exam2 = Event(
        user_id=user_id,
        title="History Exam",
        start=(today + timedelta(days=7, hours=13)).isoformat(),
        end=(today + timedelta(days=7, hours=15)).isoformat(),
        color="#ca8300",
        priority=2,
        recurrence="None",
        recurrence_id="0",
        all_day=False,
        locked=True,
        exam_id=None,
    )
    exam3 = Event(
        user_id=user_id,
        title="Biology Exam",
        start=(today + timedelta(days=4, hours=8)).isoformat(),
        end=(today + timedelta(days=4, hours=10)).isoformat(),
        color="#097200",
        priority=3,
        recurrence="None",
        recurrence_id="0",
        all_day=False,
        locked=True,
        exam_id=None,
    )

    # Add some busy events (classes, appointments)
    busy1 = Event(
        user_id=user_id,
        title="Class: English",
        start=(today + timedelta(days=1, hours=10)).isoformat(),
        end=(today + timedelta(days=1, hours=12)).isoformat(),
        color="#4287f5",
        priority=5,
        recurrence="None",
        recurrence_id="0",
        all_day=False,
        locked=True,
        exam_id=None,
    )
    busy2 = Event(
        user_id=user_id,
        title="Doctor Appointment",
        start=(today + timedelta(days=2, hours=15)).isoformat(),
        end=(today + timedelta(days=2, hours=16)).isoformat(),
        color="#8e44ad",
        priority=5,
        recurrence="None",
        recurrence_id="0",
        all_day=False,
        locked=True,
        exam_id=None,
    )
    busy3 = Event(
        user_id=user_id,
        title="Class: Chemistry",
        start=(today + timedelta(days=5, hours=9)).isoformat(),
        end=(today + timedelta(days=5, hours=11)).isoformat(),
        color="#16a085",
        priority=5,
        recurrence="None",
        recurrence_id="0",
        all_day=False,
        locked=True,
        exam_id=None,
    )
    busy4 = Event(
        user_id=user_id,
        title="Sports Practice",
        start=(today + timedelta(days=6, hours=17)).isoformat(),
        end=(today + timedelta(days=6, hours=19)).isoformat(),
        color="#e67e22",
        priority=5,
        recurrence="None",
        recurrence_id="0",
        all_day=False,
        locked=True,
        exam_id=None,
    )

    # Add a non-exam event with priority 0 (should be ignored by the algorithm)
    non_exam = Event(
        user_id=user_id,
        title="Read a book",
        start=(today + timedelta(days=3, hours=18)).isoformat(),
        end=(today + timedelta(days=3, hours=19)).isoformat(),
        color="#888888",
        priority=0,
        recurrence="None",
        recurrence_id="0",
        all_day=False,
        locked=True,
        exam_id=None,
    )

    db.session.add_all([exam1, exam2, exam3, busy1, busy2, busy3, busy4, non_exam])
    db.session.commit()
    return "Test events for the learning time algorithm have been populated!", 201


# ---------------------- Main Routes ----------------------


@app.route("/")
def home():
    """Home route: Displays login/register buttons or welcome message if logged in."""
    # Read tips from the file
    try:
        with open("tips/tips.txt", "r") as file:
            tips = file.readlines()
    except FileNotFoundError:
        tips = ["No tips available."]

    tip_of_the_day = tips[
        datetime.now().timetuple().tm_yday % len(tips)
    ].strip()  # Select a random tip based on the current day

    if "username" in session:
        return render_template(
            "home.html",
            username=session["username"],
            logged_in=True,
            tip=tip_of_the_day,
        )
    return render_template("home.html", logged_in=False, tip=tip_of_the_day)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Login route: Handles login form submission and user authentication."""
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()

        if user and bcrypt.check_password_hash(user.password, password):
            session["username"] = username
            return redirect(url_for("home"))
        return "Invalid credentials. Try again."
    return render_template("login.html")


@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    """Forgot password route: Handles password reset requests."""
    if request.method == "POST":
        email = request.form["email"]
        user = User.query.filter_by(email=email).first()

        if user:
            # Generate a password reset token
            serializer = URLSafeTimedSerializer(app.secret_key)
            token = serializer.dumps(email, salt=user.password)  # Generate token
            reset_link = url_for("reset_password", token=token, _external=True)
            # Send email with reset link (using Flask-Mailman)
            msg = EmailMessage(
                subject="Password Reset Request",
                body=f"Click the link to reset your password: {reset_link}",
                to=[email],
                from_email=app.config["MAIL_USERNAME"],
            )
            msg.send()  # Send the email
            return "Password reset link sent to your email."
        return "Email not found. Try again."
    else:
        return render_template("forgot_password.html")


@app.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    """Reset password route: Handles password reset form submission."""
    serializer = URLSafeTimedSerializer(app.secret_key)

    if request.method == "POST":
        try:
            user = User.query.filter_by(username=request.form["username"]).first()
            email = serializer.loads(
                request.form["token"], salt=user.password, max_age=900
            )  # Validate token
        except Exception as e:
            return "Invalid or expired token."
        if request.form["new_password"] == request.form["confirm_password"]:
            # Update the user's password in the database
            new_password = request.form["new_password"]
            user = User.query.filter_by(email=email).first()
            if user:
                hashed_password = bcrypt.generate_password_hash(new_password).decode(
                    "utf-8"
                )
                user.password = hashed_password
                db.session.commit()  # Commit the changes
                return redirect(
                    url_for("login")
                )  # Redirect to login after password reset
            return "User not found. Try again."
        else:
            return "Passwords do not match. Try again."
    else:
        return render_template("reset_password.html", token=token)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register route: Handles user registration with password hashing."""
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        email = request.form["email"]

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return "User already exists. Choose another username."

        hashed_password = bcrypt.generate_password_hash(password).decode(
            "utf-8"
        )  # Securely hash password
        new_user = User(username=username, password=hashed_password, email=email)
        db.session.add(new_user)
        db.session.commit()

        # Create default settings for the new user
        default_settings = Settings(
            user_id=new_user.id,
            learn_on_saturday=DEFAULT_SETTINGS["learn_on_saturday"],
            learn_on_sunday=DEFAULT_SETTINGS["learn_on_sunday"],
            preferred_learning_time=DEFAULT_SETTINGS["preferred_learning_time"],
            study_block_color=DEFAULT_SETTINGS["study_block_color"],
        )
        db.session.add(default_settings)
        db.session.flush()
        for level in [1, 2, 3]:
            priority = DEFAULT_SETTINGS["priority_settings"][level]
            db.session.add(PrioritySetting(
                settings_id=default_settings.id,
                priority_level=level,
                color=priority["color"],
                days_to_learn=priority["days_to_learn"],
                max_hours_per_day=priority["max_hours_per_day"],
                total_hours_to_learn=priority["total_hours_to_learn"],   
            ))
        db.session.commit()

        session["username"] = username  # Store session data
        return redirect(url_for("home"))

    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    """Logout route: Removes user session data and redirects to home."""
    session.pop("username", None)
    return redirect(url_for("home"))


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    user = User.query.filter_by(username=session["username"]).first()
    settings = Settings.query.filter_by(user_id=user.id).first()
    if request.method == "POST":
        # Handle add/remove priority
        if "add_priority" in request.form:
            # Find the next available priority level (highest + 1)
            existing_levels = [p.priority_level for p in settings.priority_settings]
            next_level = max(existing_levels, default=0) + 1

            # Move up all events with priority >= next_level (but not 0, which is reserved for learning blocks)
            user_events = Event.query.filter(
                Event.user_id == user.id,
                Event.priority >= next_level
            ).all()
            for event in user_events:
                event.priority += 1

            # Now add the new priority at next_level
            new_prio = PrioritySetting(
                settings_id=settings.id,
                priority_level=next_level,
                color="#000000",
                days_to_learn=7,
                max_hours_per_day=2.0,
                total_hours_to_learn=7.0,
            )
            db.session.add(new_prio)
            db.session.commit()
            return redirect(url_for("settings"))
        elif "remove_priority" in request.form:
            level_to_remove = int(request.form["remove_priority"])
            prio_setting = PrioritySetting.query.filter_by(settings_id=settings.id, priority_level=level_to_remove).first()
            if prio_setting:
                db.session.delete(prio_setting)
                # Shift down all higher priorities
                higher_prios = PrioritySetting.query.filter(
                    PrioritySetting.settings_id == settings.id,
                    PrioritySetting.priority_level > level_to_remove
                ).order_by(PrioritySetting.priority_level).all()
                for p in higher_prios:
                    p.priority_level -= 1
                db.session.commit()
            return redirect(url_for("settings"))
        # Update general and priority settings as before
        settings.learn_on_saturday = "learn_on_saturday" in request.form
        settings.learn_on_sunday = "learn_on_sunday" in request.form
        settings.preferred_learning_time = request.form.get("learning_time", settings.preferred_learning_time)
        for prio in settings.priority_settings:
            prio.color = request.form.get(f"priority{prio.priority_level}_color", prio.color)
            prio.days_to_learn = int(request.form.get(f"priority{prio.priority_level}_days", prio.days_to_learn))
            prio.max_hours_per_day = float(request.form.get(f"priority{prio.priority_level}_max_hours_per_day", prio.max_hours_per_day))
            prio.total_hours_to_learn = float(request.form.get(f"priority{prio.priority_level}_total_hours_to_learn", prio.total_hours_to_learn))
        db.session.commit()
        return redirect(url_for("settings"))
    # Prepare values for template
    return render_template(
        "settings.html",
        learn_on_saturday=settings.learn_on_saturday,
        learn_on_sunday=settings.learn_on_sunday,
        preferred_learning_time=settings.preferred_learning_time,
        priority_settings=settings.priority_settings,
    )


@app.route("/settings/delete_account")
@login_required
def delete_account():
    """Delete account route: Deletes user account currently in session."""
    current_user = session["username"]
    db.session.delete(User.query.filter_by(username=current_user).first())
    db.session.commit()
    session.clear()
    return redirect(url_for("home"))


@app.route("/settings/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    """Change password route: Changes the password of the user currently in session."""
    if request.method == "POST":
        old_password = request.form["ogpw"]
        new_password = request.form["newpw"]
        confirm_password = request.form["confirm"]

        if not bcrypt.check_password_hash(
            User.query.filter_by(username=session["username"]).first().password,
            old_password,
        ):
            return "Incorrect old password. Try again."

        if new_password != confirm_password:
            return "Passwords do not match. Try again."

        hashed_password = bcrypt.generate_password_hash(new_password).decode("utf-8")
        User.query.filter_by(username=session["username"]).first().password = (
            hashed_password
        )
        db.session.commit()
        return redirect(url_for("home"))

    return render_template("change_password.html")


@app.route("/agenda")
@login_required
def agenda():
    """Agenda route: Displays the agenda of the user currently in session."""
    user = User.query.filter_by(username=session["username"]).first()
    settings = Settings.query.filter_by(user_id=user.id).first()

    priority_levels = settings.priority_settings
    priority_levels = sorted(priority_levels, key=lambda x: x.priority_level)

    return render_template("agenda.html", priority_levels=priority_levels)


@app.route("/api/import-ics", methods=["POST"])
@login_required
def import_ics():
    """Import events from an .ics file."""
    data = request.json
    ics_content = data.get("ics")
    if not ics_content:
        return jsonify({"message": "No .ics content provided"}), 400
    try:
        calendar = icalendar.Calendar.from_ical(ics_content)
        for component in calendar.walk():
            if component.name == "VEVENT":
                title = str(component.get("SUMMARY", "Untitled Event"))
                start = component.get("DTSTART").dt
                end = component.get("DTEND").dt if component.get("DTEND") else None
                color = "#fcba03"
                logged_in_user = User.query.filter_by(
                    username=session.get("username")
                ).first()
                if not logged_in_user:
                    return jsonify({"message": "No logged-in user found"}), 400
                new_event = Event(
                    title=title,
                    start=start.isoformat(),
                    end=end.isoformat() if end else None,
                    color=color,
                    user_id=logged_in_user.id,
                    priority=4,
                    recurrence="None",
                    recurrence_id=0,
                )
                db.session.add(new_event)
        db.session.commit()
        return jsonify({"message": "Events imported successfully"}), 200
    except Exception as e:
        return jsonify({"message": "Failed to import .ics file"}), 500


# ---------------------- Noten (Grades) API ----------------------


@app.route("/noten")
@login_required
def noten():
    """Noten route: Displays the noten (grades) page."""
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("noten.html")


@app.route("/api/noten", methods=["GET"])
@login_required
def get_noten():
    """API endpoint to get all semesters, subjects, and grades for the user."""
    if "username" not in session:
        return jsonify({"error": "Not logged in"}), 401
    user = User.query.filter_by(username=session["username"]).first()
    semesters = Semester.query.filter_by(user_id=user.id).all()
    data = []
    for sem in semesters:
        sem_data = {"id": sem.id, "name": sem.name, "subjects": []}
        for subj in sem.subjects:
            subj_data = {"id": subj.id, "name": subj.name, "grades": []}
            for grade in subj.grades:
                subj_data["grades"].append(
                    {
                        "id": grade.id,
                        "name": grade.name,
                        "value": grade.value,
                        "weight": grade.weight,
                        "counts": grade.counts,
                    }
                )
            sem_data["subjects"].append(subj_data)
        data.append(sem_data)
    return jsonify(data)


@app.route("/api/noten", methods=["POST"])
@login_required
def save_noten():
    """API endpoint to save all semesters, subjects, and grades for the user."""
    if "username" not in session:
        return jsonify({"error": "Not logged in"}), 401
    data = request.json
    user = User.query.filter_by(username=session["username"]).first()
    if not user:
        return jsonify({"error": "User not found"}), 404
    # Remove all existing semesters, subjects, and grades for this user
    semesters = Semester.query.filter_by(user_id=user.id).all()
    for sem in semesters:
        db.session.delete(sem)
    db.session.commit()
    # Re-create all semesters, subjects, and grades from the posted data
    for sem in data:
        semester = Semester(user_id=user.id, name=sem["name"])
        db.session.add(semester)
        db.session.flush()
        for subj in sem.get("subjects", []):
            subject = Subject(semester_id=semester.id, name=subj["name"])
            db.session.add(subject)
            db.session.flush()
            for grade in subj.get("grades", []):
                db.session.add(
                    Grade(
                        subject_id=subject.id,
                        name=grade["name"],
                        value=grade["value"],
                        weight=grade["weight"],
                        counts=grade["counts"],
                    )
                )
    db.session.commit()
    return jsonify({"status": "success"})


@app.route("/lerntimer")
def lerntimer():
    """Pomodoro timer route."""
    return render_template("lerntimer.html")


# ---------------------- Run the Application ----------------------

if __name__ == "__main__":
    app.run(debug=True)
