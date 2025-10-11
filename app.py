# Import necessary libraries and modules
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_mailman import Mail, EmailMessage
from functools import wraps
import icalendar # Used for importing events from .ics files
import uuid # Used to generate unique recurrence IDs
from datetime import datetime, timedelta, time as dtime
from itsdangerous import URLSafeTimedSerializer # Used for generating secure, time-sensitive tokens (e.g., password reset)
from dateutil.relativedelta import relativedelta  # Used for monthly recurrence calculations
from dotenv import load_dotenv # Used to load environment variables from a .env file
import os
import json

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# ---------------------- Flask App Configuration ----------------------

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL")  # Use SQLite by default

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    # Fix for Heroku/Railway's older 'postgres' scheme not supported by SQLAlchemy
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = (
    False  # Disable modification tracking for performance
)
app.secret_key = os.getenv("SECRET_KEY")  # Secret key for session management and token generation

# Mail configuration (for password reset emails)
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 465
app.config["MAIL_USE_TLS"] = False
app.config["MAIL_USE_SSL"] = True
app.config["MAIL_USERNAME"] = "kantikoala@gmail.com"
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")

# ---------------------- Initialize Extensions ----------------------

db = SQLAlchemy(app) # Initializes the SQLAlchemy ORM
bcrypt = Bcrypt(app) # Initializes Bcrypt for password hashing
mail = Mail(app) # Initializes the mail extension

# ----------------------- Defaults -----------------------
# Default settings for a new user, defining preferred study times and initial priority rules
DEFAULT_SETTINGS = {"learn_on_saturday": False, "learn_on_sunday": False, "preferred_learning_time": "18:00", "study_block_color": "#0000FF",
                    "priority_settings": {1: {"color": "#770000", "days_to_learn": 14, "max_hours_per_day": 2.0, "total_hours_to_learn": 14.0},
                                          2: {"color": "#ca8300", "days_to_learn": 7, "max_hours_per_day": 1.5, "total_hours_to_learn": 7.0},
                                          3: {"color": "#097200", "days_to_learn": 4, "max_hours_per_day": 1.0, "total_hours_to_learn": 4.0}
                    }
}

# ---------------------- Database Models ----------------------


class User(db.Model):
    """
    SQLAlchemy model for storing user authentication details.

    Attributes:
        id (int): Primary key.
        username (str): Unique username.
        password (str): Hashed password.
        email (str): Unique email address.
        events (relationship): One-to-many relationship with Event model.
        semesters (relationship): One-to-many relationship with Semester model.
        settings (relationship): One-to-many relationship with Settings model.
    """

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)  # Hashed password
    email = db.Column(db.String(100), unique=True, nullable=False)

    # Relationships (enables easy retrieval of user data and cascade deletion)
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
    """
    SQLAlchemy model for storing user-specific scheduling preferences.

    Attributes:
        id (int): Primary key.
        user_id (int): Foreign key to the User model.
        learn_on_saturday (bool): Flag for weekend study preference.
        learn_on_sunday (bool): Flag for weekend study preference.
        preferred_learning_time (str): User's preferred time of day for study blocks (HH:MM).
        study_block_color (str): Hex code for algorithm-generated study blocks.
        priority_settings (relationship): One-to-many relationship with PrioritySetting model.
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    learn_on_saturday = db.Column(db.Boolean, default=False)
    learn_on_sunday = db.Column(db.Boolean, default=False)
    preferred_learning_time = db.Column(db.String(20), default="18:00")
    study_block_color = db.Column(db.String(7), default="#0000FF")

    # Relationship to detailed priority rules
    priority_settings = db.relationship(
        "PrioritySetting", backref="settings", lazy=True, cascade="all, delete-orphan"
    )


class PrioritySetting(db.Model):
    """
    SQLAlchemy model for storing user-specific priority rules (e.g., P1, P2, P3)
    used by the learning time algorithm.

    Attributes:
        id (int): Primary key.
        settings_id (int): Foreign key to the Settings model.
        priority_level (int): The numerical priority level (e.g., 1, 2, 3).
        color (str): Hex color code for exams of this priority.
        days_to_learn (int): The size of the scheduling window before the exam.
        max_hours_per_day (float): Maximum study time allowed per day for this priority.
        total_hours_to_learn (float): Total required study time for this priority's exams.
    """
    id = db.Column(db.Integer, primary_key=True)
    settings_id = db.Column(db.Integer, db.ForeignKey("settings.id"), nullable=False)
    priority_level = db.Column(db.Integer, nullable=False) # e.g., 1, 2, 3
    color = db.Column(db.String(7), nullable=False) # Color to display exams of this priority
    days_to_learn = db.Column(db.Integer, nullable=False) # Scheduling window size before exam
    max_hours_per_day = db.Column(db.Float, nullable=False) # Max study time per day for this priority
    total_hours_to_learn = db.Column(db.Float, nullable=False) # Total required study time


class Event(db.Model):
    """
    SQLAlchemy model for storing user calendar entries (classes, exams, study blocks).

    Attributes:
        id (int): Primary key.
        user_id (int): Foreign key to the User model.
        title (str): Event title.
        start (str): Start datetime in ISO format.
        end (str): End datetime in ISO format.
        color (str): Hex color code for the event display.
        priority (int): 0 for study blocks; >0 for user events/exams.
        recurrence (str): Recurrence pattern ('daily', 'weekly', 'monthly', 'None').
        recurrence_id (str): Unique ID linking recurring events.
        all_day (bool): True if an all-day event.
        locked (bool): True if user-created (will not be deleted by the algorithm).
        exam_id (int): Links a study block (priority=0) to its parent exam.
    """

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id", onupdate="CASCADE"), nullable=False
    )
    title = db.Column(db.String(100), nullable=False)
    start = db.Column(db.String(50), nullable=False)  # ISO format datetime
    end = db.Column(db.String(50), nullable=True) # ISO format datetime
    color = db.Column(db.String(7), nullable=False)
    priority = db.Column(db.Integer, nullable=False) # 0 for algorithm-generated study blocks; >0 for user events/exams
    recurrence = db.Column(db.String(50), nullable=True) # e.g., 'daily', 'weekly', 'monthly', 'None'
    recurrence_id = db.Column(db.String(50), nullable=True) # Unique ID for linked recurring events
    all_day = db.Column(db.Boolean, nullable=False, default=False)

    # Fields specifically for the learning algorithm
    locked = db.Column(db.Boolean, default=True) # True: user-created, False: algorithm-created (can be recycled)
    exam_id = db.Column(db.Integer, nullable=True) # Links a study block (priority=0) back to its parent exam


class Semester(db.Model):
    """
    SQLAlchemy model for storing academic semesters (part of the Grades feature).

    Attributes:
        id (int): Primary key.
        user_id (int): Foreign key to the User model.
        name (str): Semester name (e.g., 'Fall 2023').
        subjects (relationship): One-to-many relationship with Subject model.
    """

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)

    # Relationship to subjects with cascade delete
    subjects = db.relationship(
        "Subject", backref="semester", lazy=True, cascade="all, delete-orphan"
    )


class Subject(db.Model):
    """
    SQLAlchemy model for storing subjects within a semester.

    Attributes:
        id (int): Primary key.
        semester_id (int): Foreign key to the Semester model.
        name (str): Subject name (e.g., 'Calculus I').
        grades (relationship): One-to-many relationship with Grade model.
    """

    id = db.Column(db.Integer, primary_key=True)
    semester_id = db.Column(db.Integer, db.ForeignKey("semester.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    counts_towards_average = db.Column(db.Boolean, nullable=False, default=True)

    # Relationship to grades with cascade delete
    grades = db.relationship(
        "Grade", backref="subject", lazy=True, cascade="all, delete-orphan"
    )


class Grade(db.Model):
    """
    SQLAlchemy model for storing individual grades for subjects (Noten).

    Attributes:
        id (int): Primary key.
        subject_id (int): Foreign key to the Subject model.
        name (str): Grade name (e.g., 'Midterm Exam').
        value (float): The grade score/value.
        weight (float): The weight/percentage of the grade.
        counts (bool): Whether the grade is included in the final calculation.
    """

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    value = db.Column(db.Float, nullable=False)
    weight = db.Column(db.Float, nullable=False)
    counts = db.Column(db.Boolean, nullable=False, default=True)


# ---------------------- Database Initialization ----------------------

with app.app_context():
    db.create_all() # Creates all defined tables in the database
    # Enable foreign key support for SQLite (necessary for cascade delete to work reliably)
    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
        with db.engine.connect() as connection:
            connection.execute(db.text("PRAGMA foreign_keys=ON"))

# ---------------------- Utility Functions ----------------------


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
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


# ---------------------- Learning Time Algorithm Utilities ----------------------

# Define constants (used in the algorithm)
DAY_START   = dtime(8, 0)         # Day earliest start time (08:00)

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
    and applying a 30-minute margin (buffer) around them.

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
            free_slots.append((current_start, event_start - timedelta(minutes=30)))

        # Move the current start past the end of the current event, respecting a 30-min buffer
        current_start = max(current_start, event_end + timedelta(minutes=30))

    # Check for a final free slot after the last event until the end of the day (22:00)
    if current_start <= datetime.combine(day, DAY_END):
        free_slots.append((current_start, datetime.combine(day, DAY_END)))

    return free_slots

def learning_time_algorithm(events, user):
    """
    The core algorithm to schedule optimal learning blocks for upcoming exams.
    It identifies exams, calculates required study hours, recycles (deletes)
    previous non-locked study blocks, and schedules new blocks backward from
    the exam date, respecting daily max hours and existing event conflicts.

    Args:
        events (list[Event]): All calendar Event objects for the user (passed by
                              reference and potentially modified/updated).
        user (User): The current user object.

    Returns:
        tuple[dict, dict]: A tuple containing:
                           1. A summary dictionary of total blocks/hours added.
                           2. A dictionary of success messages for each exam processed.
    """

    # --- Configuration and Initialization ---

    # Fetch user-specific settings
    settings = Settings.query.filter_by(user_id=user.id).first()
    priority_settings = {p.priority_level: p for p in settings.priority_settings}
    if not priority_settings:
        return {"error": "No priority settings found"}, {}

    max_exam_priority = max(priority_settings.keys())

    # Load scheduling preferences
    sat_learn = settings.learn_on_saturday
    sun_learn = settings.learn_on_sunday
    preferred_time = datetime.strptime(settings.preferred_learning_time, "%H:%M").time()
    study_block_color = settings.study_block_color if settings.study_block_color else "#0000FF"

    # Define constants
    DAY_END = dtime(22, 0) # Allows blocks to run until 22:00 (10 PM)
    SESSION = 0.5 # Minimum session duration is 30 minutes (0.5 hours)

    # Identify and sort all events flagged as exams
    exams = sorted(
        [event for event in events if int(event.priority) > 0 and int(event.priority) <= max_exam_priority],
        key=lambda event: (int(event.priority), datetime.fromisoformat(event.start))
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

        # Recycling Logic: Delete all *non-locked* future study blocks
        locked_future_blocks = [block for block in future_blocks if block.locked]
        recyclable_blocks = [block for block in future_blocks if not block.locked]

        for block in recyclable_blocks:
            db.session.delete(block)
            events.remove(block) # Update in-memory list
        db.session.commit()

        # Recalculate remaining hours
        hours_scheduled_locked = sum(
            (to_dt(block.end) - to_dt(block.start)).total_seconds() / 3600 for block in locked_future_blocks
        )
        hours_left = max(0, total - hours_done - hours_scheduled_locked)

        if hours_left == 0:
            continue

        # --- Scheduling Loop: Schedule remaining hours backwards ---

        new_scheduled = 0.0
        days_left_until_exam = (window_end.date() - datetime.now().date()).days

        for day_offset in range(1, days_left_until_exam + 1):
            current_day = window_end - timedelta(days=day_offset)

            if current_day.date() < window_start.date():
                continue

            # Check weekend restrictions
            if (not sat_learn and current_day.weekday() == 5) or (not sun_learn and current_day.weekday() == 6):
                continue

            if new_scheduled >= hours_left:
                break

            # ... (Rest of the scheduling logic, including preferred slot and general free slot search) ...
            
            # The scheduling logic checks conflicts against the updated 'events' list, 
            # prioritizes the user's preferred time, and then finds the largest free slot,
            # ensuring blocks are at least SESSION (0.5 hours) long and do not exceed today_max.

            scheduled_today_for_exam = sum(
                (to_dt(block.end) - to_dt(block.start)).total_seconds() / 3600
                for block in events
                if block.exam_id == exam.id and to_dt(block.start).date() == current_day.date()
            )

            today_max = min(max_per_day - scheduled_today_for_exam, hours_left - new_scheduled)
            if today_max <= SESSION:
                continue

            events_today = [event for event in events if to_dt(event.start).date() == current_day.date()]

            # 1. Preferred time slot check
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
                events.append(new_block)
                new_scheduled += preferred_slot_duration
                summary["blocks_added"] += 1
                summary["hours_added"] += preferred_slot_duration
                continue

            # 2. General free slot search
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
                events.append(new_block)
                new_scheduled += allocatable
                summary["blocks_added"] += 1
                summary["hours_added"] += allocatable

                if new_scheduled >= hours_left:
                    break
                
                break # Only schedule one block per day in the general search

        # --- Safety / Extra Days Extension (Beyond Initial Window) ---
        # The logic below repeats the scheduling process outside the window_days boundary 
        # to ensure all required hours are scheduled if possible.
        if new_scheduled < hours_left:
            for day_offset in range(window_days + 1, min(22, days_left_until_exam + 1)):
                current_day = window_end - timedelta(days=day_offset)

                if new_scheduled >= hours_left:
                    break

                # The logic inside this loop is identical to the main scheduling loop (Preferred Slot check + General Slot Search)
                # ... (code omitted for brevity, but it's the same logic) ...
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
                    events.append(new_block)
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
                    events.append(new_block)
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
    return jsonify(events)


@app.route("/api/events", methods=["POST"])
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
        num_instances = 7 if data["recurrence"] == "daily" else 4 if data["recurrence"] == "weekly" else 12
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


@app.route("/api/events", methods=["PUT"])
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


@app.route("/api/events/<int:event_id>", methods=["DELETE"])
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


@app.route("/api/events/recurring/<recurrence_id>", methods=["DELETE"])
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


@app.route('/api/run-learning-algorithm', methods=['POST'])
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


@app.route("/api/populate_test_algorithm", methods=["GET", "POST"])
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


# ---------------------- Main Routes ----------------------


@app.route("/")
def home():
    """
    Home route: Handles the main landing page display.

    If the user is logged in, it shows a welcome message and a daily tip.
    Otherwise, it shows login/register links.

    Returns:
        str: Rendered HTML template ('home.html').
    """
    # Read tips from the file (assumes 'tips/tips.txt' exists)
    try:
        with open("tips/daily_tips.txt", "r", encoding="utf-8") as file:
            tips = file.readlines()
    except FileNotFoundError:
        tips = ["No tips available."]

    # Selects a tip based on the day of the year (ensures a different tip daily)
    tip_of_the_day = tips[
        datetime.now().timetuple().tm_yday % len(tips)
    ].strip()

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
    """
    Login route: Handles user sign-in and session management.

    POST: Authenticates user credentials using bcrypt. If successful, sets the
          'username' in the session and redirects to home.
    GET: Renders the login page.

    Returns:
        str: Rendered HTML template ('login.html') or a redirect.
    """
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()

        # Check if user exists and password hash matches
        if user and bcrypt.check_password_hash(user.password, password):
            session["username"] = username
            return redirect(url_for("home"))
        return "Invalid credentials. Try again."
    return render_template("login.html")


@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    """
    Forgot password route: Handles password reset requests.

    POST: Finds the user by email, generates a secure, time-sensitive token,
          and sends a password reset link via email using Flask-Mailman.
    GET: Renders the request form.

    Returns:
        str: A confirmation message or error message.
    """
    if request.method == "POST":
        email = request.form["email"]
        user = User.query.filter_by(email=email).first()

        if user:
            # Generate a password reset token, signed with a salt (user's password hash) for security
            serializer = URLSafeTimedSerializer(app.secret_key)
            token = serializer.dumps(email, salt=user.password)
            reset_link = url_for("reset_password", token=token, _external=True)

            # Send email with reset link
            msg = EmailMessage(
                subject="Password Reset Request",
                body=f"Click the link to reset your password: {reset_link}",
                to=[email],
                from_email=app.config["MAIL_USERNAME"],
            )
            msg.send()  # Sends the email
            return "Password reset link sent to your email."
        return "Email not found. Try again."
    else:
        return render_template("forgot_password.html")


@app.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    """
    Reset password route: Allows a user to set a new password using a valid token.

    POST: Validates the token and salt, verifies matching passwords, hashes the
          new password, and updates the user's record.
    GET: Renders the password reset form.

    Args:
        token (str): The URLSafeTimedSerializer token from the reset email.

    Returns:
        str: Rendered HTML template ('reset_password.html') or a redirect/error message.
    """
    serializer = URLSafeTimedSerializer(app.secret_key)

    if request.method == "POST":
        try:
            # Requires the username from the form to correctly retrieve the user and their password hash (salt)
            user = User.query.filter_by(username=request.form["username"]).first()
            # Loads email from token, validating signature (salt) and max age (e.g., 15 min)
            email = serializer.loads(
                request.form["token"], salt=user.password, max_age=900
            )
        except Exception:
            return "Invalid or expired token."

        if request.form["new_password"] == request.form["confirm_password"]:
            new_password = request.form["new_password"]
            # Find user again by the email verified by the token
            user = User.query.filter_by(email=email).first()
            if user:
                # Hash and update the password
                hashed_password = bcrypt.generate_password_hash(new_password).decode(
                    "utf-8"
                )
                user.password = hashed_password
                db.session.commit()
                return redirect(
                    url_for("login")
                )
            return "User not found. Try again."
        else:
            return "Passwords do not match. Try again."
    else:
        return render_template("reset_password.html", token=token)


@app.route("/register", methods=["GET", "POST"])
def register():
    """
    Register route: Handles new user sign-up.

    POST: Creates a new User record with a hashed password, and initializes
          the corresponding default Settings and PrioritySetting records.
    GET: Renders the registration form.

    Returns:
        str: Rendered HTML template ('register.html') or a redirect/error message.
    """
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        email = request.form["email"]

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return "User already exists. Choose another username."

        # Hash password and create new user
        hashed_password = bcrypt.generate_password_hash(password).decode(
            "utf-8"
        )
        new_user = User(username=username, password=hashed_password, email=email)
        db.session.add(new_user)
        db.session.commit() # Commit to get new_user.id

        # Create default settings for the new user
        default_settings = Settings(
            user_id=new_user.id,
            learn_on_saturday=DEFAULT_SETTINGS["learn_on_saturday"],
            learn_on_sunday=DEFAULT_SETTINGS["learn_on_sunday"],
            preferred_learning_time=DEFAULT_SETTINGS["preferred_learning_time"],
            study_block_color=DEFAULT_SETTINGS["study_block_color"],
        )
        db.session.add(default_settings)
        db.session.flush() # Flush to get default_settings.id

        # Create default PrioritySetting entries (P1, P2, P3)
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

        session["username"] = username
        return redirect(url_for("home"))

    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    """
    Logout route: Clears the user session and redirects to the home page.

    Returns:
        redirect: Redirects to the home route.
    """
    session.pop("username", None)
    return redirect(url_for("home"))


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    """
    Settings route: Allows the user to view and update their general and priority study settings.

    POST: Handles updating general settings, adding new priority levels, and
          removing/modifying existing priority rules.
    GET: Renders the settings form.

    Returns:
        str: Rendered HTML template ('settings.html') or a redirect.
    """
    user = User.query.filter_by(username=session["username"]).first()
    settings = Settings.query.filter_by(user_id=user.id).first()

    if request.method == "POST":
        # Handle adding a new priority level
        if "add_priority" in request.form:
            # ... (priority addition logic, including shifting existing events/settings) ...
            existing_levels = [p.priority_level for p in settings.priority_settings]
            next_level = max(existing_levels, default=0) + 1

            # Shift all events with current priority >= next_level up by 1
            user_events = Event.query.filter(
                Event.user_id == user.id,
                Event.priority >= next_level
            ).all()
            for event in user_events:
                event.priority += 1

            # Add the new priority setting
            new_prio = PrioritySetting(
                settings_id=settings.id, priority_level=next_level, color="#000000",
                days_to_learn=7, max_hours_per_day=2.0, total_hours_to_learn=7.0,
            )
            db.session.add(new_prio)
            db.session.commit()
            return redirect(url_for("settings"))

        # Handle removing a priority level
        elif "remove_priority" in request.form:
            level_to_remove = int(request.form["remove_priority"])
            prio_setting = PrioritySetting.query.filter_by(settings_id=settings.id, priority_level=level_to_remove).first()
            if prio_setting:
                db.session.delete(prio_setting)
                # Shift all higher priority levels down by 1
                higher_prios = PrioritySetting.query.filter(
                    PrioritySetting.settings_id == settings.id,
                    PrioritySetting.priority_level > level_to_remove
                ).order_by(PrioritySetting.priority_level).all()
                for p in higher_prios:
                    p.priority_level -= 1
                db.session.commit()
            return redirect(url_for("settings"))

        # Update general settings
        settings.learn_on_saturday = "learn_on_saturday" in request.form
        settings.learn_on_sunday = "learn_on_sunday" in request.form
        settings.preferred_learning_time = request.form.get("learning_time", settings.preferred_learning_time)
        settings.study_block_color = request.form.get("study_block_color", settings.study_block_color)

        # Update specific priority settings (color, days_to_learn, etc.)
        for prio in settings.priority_settings:
            prio.color = request.form.get(f"priority{prio.priority_level}_color", prio.color)
            prio.days_to_learn = int(request.form.get(f"priority{prio.priority_level}_days", prio.days_to_learn))
            prio.max_hours_per_day = float(request.form.get(f"priority{prio.priority_level}_max_hours_per_day", prio.max_hours_per_day))
            prio.total_hours_to_learn = float(request.form.get(f"priority{prio.priority_level}_total_hours_to_learn", prio.total_hours_to_learn))

        db.session.commit()
        return redirect(url_for("settings"))

    # Prepare values for GET request (render the settings form)
    return render_template(
        "settings.html",
        learn_on_saturday=settings.learn_on_saturday,
        learn_on_sunday=settings.learn_on_sunday,
        preferred_learning_time=settings.preferred_learning_time,
        priority_settings=sorted(settings.priority_settings, key=lambda p: p.priority_level), # Ensure list is sorted
        study_block_color=settings.study_block_color,
    )


@app.route("/settings/delete_account")
@login_required
def delete_account():
    """
    Delete account route: Deletes the user account and all associated data
    due to cascade delete relationships in the SQLAlchemy models.

    Returns:
        redirect: Redirects to the home route.
    """
    current_user = session["username"]
    db.session.delete(User.query.filter_by(username=current_user).first())
    db.session.commit()
    session.clear()
    return redirect(url_for("home"))


@app.route("/settings/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    """
    Change password route: Allows a logged-in user to change their password.

    POST: Verifies the old password using bcrypt, validates the new password
          confirmation, hashes the new password, and updates the database.
    GET: Renders the change password form.

    Returns:
        str: Rendered HTML template ('change_password.html') or a redirect/error message.
    """
    if request.method == "POST":
        old_password = request.form["ogpw"]
        new_password = request.form["newpw"]
        confirm_password = request.form["confirm"]

        user = User.query.filter_by(username=session["username"]).first()

        # Check old password
        if not bcrypt.check_password_hash(user.password, old_password):
            return "Incorrect old password. Try again."

        # Check new password confirmation
        if new_password != confirm_password:
            return "Passwords do not match. Try again."

        # Hash and update new password
        hashed_password = bcrypt.generate_password_hash(new_password).decode("utf-8")
        user.password = hashed_password
        db.session.commit()
        return redirect(url_for("home"))

    return render_template("change_password.html")


@app.route("/agenda")
@login_required
def agenda():
    """
    Agenda route: Renders the calendar (FullCalendar) view.

    Passes the user's priority settings to the template for client-side display logic.

    Returns:
        str: Rendered HTML template ('agenda.html').
    """
    user = User.query.filter_by(username=session["username"]).first()
    settings = Settings.query.filter_by(user_id=user.id).first()

    priority_levels = settings.priority_settings
    # Sort priority levels to display them correctly in the frontend
    priority_levels = sorted(priority_levels, key=lambda x: x.priority_level)

    return render_template("agenda.html", priority_levels=priority_levels)


@app.route("/api/import-ics", methods=["POST"])
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


# ---------------------- Noten (Grades) API ----------------------


@app.route("/noten")
@login_required
def noten():
    """
    Noten route: Renders the grades management page.

    Returns:
        str: Rendered HTML template ('noten.html').
    """
    return render_template("noten.html")


@app.route("/api/noten", methods=["GET"])
@login_required
def get_noten():
    """
    API endpoint to get all semesters, subjects, and grades for the user.

    Returns:
        JSON: A nested data structure representing the user's academic records.
    """
    user = User.query.filter_by(username=session["username"]).first()
    semesters = Semester.query.filter_by(user_id=user.id).all()
    data = []
    # Structure the database objects into a nested dictionary/list for JSON output
    for sem in semesters:
        sem_data = {"id": sem.id, "name": sem.name, "subjects": []}
        for subj in sem.subjects:
            subj_data = {"id": subj.id, "name": subj.name, "counts_towards_average": subj.counts_towards_average, "grades": []}
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
    """
    API endpoint to save all semesters, subjects, and grades for the user.

    This implements a destructive save: all existing academic records (Semester,
    Subject, Grade) are deleted and then recreated from the incoming JSON data.

    Returns:
        JSON: A status message confirming the successful save.
    """
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
        db.session.flush() # Flush to get semester.id before adding subjects

        for subj in sem.get("subjects", []):
            subject = Subject(semester_id=semester.id, name=subj["name"], counts_towards_average=subj.get("counts_towards_average", True))
            db.session.add(subject)
            db.session.flush() # Flush to get subject.id before adding grades

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
    """
    Pomodoro timer route: Renders the lerntimer page.

    Returns:
        str: Rendered HTML template ('lerntimer.html').
    """
    return render_template("lerntimer.html")


@app.route("/lerntipps")
def lerntipps():
    """
    Learning tips route: Renders the lerntipps page.

    Returns:
        str: Rendered HTML template ('lerntipps.html').
    """

    with open("tips/learn_tips.json", "r", encoding="utf-8") as file:
        tips = json.load(file)

    return render_template("lerntipps.html", tips=tips)


# ---------------------- Run the Application ----------------------

if __name__ == "__main__":
    # Runs the Flask application. debug=True enables the reloader and debugger.
    app.run()