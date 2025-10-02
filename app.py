# Import necessary libraries and modules
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_mailman import Mail, EmailMessage
from functools import wraps
import icalendar
import uuid
from datetime import datetime, timedelta, to_dt, time as dtime
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

# ---------------------- Database Models ----------------------


class User(db.Model):
    """User model for storing authentication details."""

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)  # Hashed password
    email = db.Column(db.String(100), unique=True, nullable=False)
    priority1_color = db.Column(db.String(7), default="#770000")
    priority2_color = db.Column(db.String(7), default="#ca8300")
    priority3_color = db.Column(db.String(7), default="#097200")
    learn_on_saturday = db.Column(db.Boolean, default=False)
    learn_on_sunday = db.Column(db.Boolean, default=False)
    preferred_learning_time = db.Column(db.String(20), default="18:00")

    # Relationships
    events = db.relationship(
        "Event", backref="user", lazy=True, cascade="all, delete-orphan"
    )
    semesters = db.relationship(
        "Semester", backref="user", lazy=True, cascade="all, delete-orphan"
    )


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
    """Algorithm to determine optimal learning times based on user events."""
    sat_learn = user.learn_on_saturday
    sun_learn = user.learn_on_sunday
    preferred_time = datetime.strptime(user.preferred_learning_time, "%H:%M").time()

    # Fetch all exams
    exams = sorted(
        [event for event in events if int(event.priority) < 4],
        key=lambda event: (int(event.priority), datetime.fromisoformat(event.start))
    )

    summary = {"exams_processed": 0, "blocks_added": 0, "hours_added": 0.0}
    successes = {}

    for exam in exams:
        summary["exams_processed"] += 1
        total = TOTAL_H[int(exam.priority)]

        # All planner blocks for this exam (3-week window)
        window_start = to_dt(exam.start) - timedelta(days=21)
        window_end = to_dt(exam.start)

        all_blocks = [
            event for event in events if event.exam_id == exam.id
            and window_start <= to_dt(event.start) < window_end
        ]

        past_blocks = [block for block in all_blocks if to_dt(block.start) < datetime.now()]
        future_blocks = [block for block in all_blocks if to_dt(block.start) >= datetime.now()]

        hours_done = sum((to_dt(block.end) - to_dt(block.start)).total_seconds() / 3600 for block in past_blocks)
        hours_scheduled = sum((to_dt(block.end) - to_dt(block.start)).total_seconds() / 3600 for block in future_blocks)
        hours_left = max(0, total - hours_done - hours_scheduled)
        if hours_left == 0:
            continue  # This exam is already fully scheduled

        # Remove all future blocks (will re-add them)
        recyclable_blocks = [block for block in future_blocks if not block.locked]
        for block in recyclable_blocks:
            db.session.delete(block)
            events.remove(block)
        db.session.commit()

        # Refill going backwards from exam date
        new_scheduled = 0.0
        days_left = min(WINDOW_DAYS[int(exam.priority)], (window_end - datetime.now()).days)
        for day in range(days_left):
            current_day = window_end - timedelta(days=day+1)

            if current_day.date() <= (window_start.date() + timedelta(days=7)):
                break  # No more days left in the window
            if not sat_learn and current_day.weekday() == 5:
                continue
            if not sun_learn and current_day.weekday() == 6:
                continue
            if new_scheduled >= hours_left:
                break

            today_max = min(MAX_PER_DAY[int(exam.priority)], hours_left - new_scheduled)
            if today_max <= 0:
                continue
            
            events_today = [event for event in events if to_dt(event.start).date() == current_day]

            # First try the preferred time slot
            # Calculate preferred start and end times
            preferred_start = datetime.combine(current_day, preferred_time)
            preferred_end = preferred_start + timedelta(hours=today_max)
            if preferred_end.time() > DAY_END:
                preferred_end = datetime.combine(current_day, DAY_END)
                preferred_start = preferred_end - timedelta(hours=today_max)
            
            # Determine if the preferred slot is free (At least halfhour before and after)
            slot_free = True
            for event in events_today:
                event_start = to_dt(event.start)
                event_end = to_dt(event.end)
                if not (preferred_end <= event_start - timedelta(minutes=30) or preferred_start >= event_end + timedelta(minutes=30)):
                    slot_free = False
                    break
            if slot_free:
                new_block = Event(
                    title=f"Learning for {exam.title}",
                    start=to_iso(preferred_start),
                    end=to_iso(preferred_end),
                    color=STUDY_BLOCK_COLOR,
                    user_id=exam.user_id,
                    priority=4,
                    recurrence="None",
                    recurrence_id="0",
                    all_day=False,
                    locked=False,
                    exam_id=exam.id
                )
                db.session.add(new_block)
                db.session.commit()
                events.append(new_block)
                new_scheduled += (preferred_end - preferred_start).total_seconds() / 3600
                summary["blocks_added"] += 1
                summary["hours_added"] += (preferred_end - preferred_start).total_seconds() / 3600
                continue
        
            # If preferred slot not free, try to find other slots
            slots = free_slots(events, current_day)
            slots.sort(key=lambda slot: slot[1] - slots[0], reverse=True)  # Sort by duration descending
            for slot_start, slot_end in slots:
                slot_duration = (slot_end - slot_start).total_seconds() / 3600
                if slot_duration < SESSION:
                    continue  # Slot too small

                allocatable = min(slot_duration, hours_left - new_scheduled, today_max)
                if allocatable <= 0:
                    break

                block_start = slot_start
                block_end = slot_start + timedelta(hours=allocatable)

                new_block = Event(
                    title=f"Learning for {exam.title}",
                    start=to_iso(block_start),
                    end=to_iso(block_end),
                    color=STUDY_BLOCK_COLOR,
                    user_id=exam.user_id,
                    priority=4,
                    recurrence="None",
                    recurrence_id="0",
                    all_day=False,
                    locked=False,
                    exam_id=exam.id
                )
                db.session.add(new_block)
                db.session.commit()
                events.append(new_block)
                new_scheduled += allocatable
                summary["blocks_added"] += 1
                summary["hours_added"] += allocatable

                if new_scheduled >= hours_left:
                    break
            
        # Safety, extend up to 21 days (while >= today), if even possible
        while new_scheduled < hours_left:
            if (window_end - datetime.now()).days > 14:
                for day in range(15, 22):
                    current_day = window_end - timedelta(days=day)
            if not sat_learn and current_day.weekday() == 5:
                continue
            if not sun_learn and current_day.weekday() == 6:
                continue
            if new_scheduled >= hours_left:
                break

            today_max = min(MAX_PER_DAY[int(exam.priority)], hours_left - new_scheduled)
            if today_max <= 0:
                continue
            
            events_today = [event for event in events if to_dt(event.start).date() == current_day]

            # First try the preferred time slot
            # Calculate preferred start and end times
            preferred_start = datetime.combine(current_day, preferred_time)
            preferred_end = preferred_start + timedelta(hours=today_max)
            if preferred_end.time() > DAY_END:
                preferred_end = datetime.combine(current_day, DAY_END)
                preferred_start = preferred_end - timedelta(hours=today_max)
            
            # Determine if the preferred slot is free (At least halfhour before and after)
            slot_free = True
            for event in events_today:
                event_start = to_dt(event.start)
                event_end = to_dt(event.end)
                if not (preferred_end <= event_start - timedelta(minutes=30) or preferred_start >= event_end + timedelta(minutes=30)):
                    slot_free = False
                    break
            if slot_free:
                new_block = Event(
                    title=f"Learning for {exam.title}",
                    start=to_iso(preferred_start),
                    end=to_iso(preferred_end),
                    color=STUDY_BLOCK_COLOR,
                    user_id=exam.user_id,
                    priority=4,
                    recurrence="None",
                    recurrence_id="0",
                    all_day=False,
                    locked=False,
                    exam_id=exam.id
                )
                db.session.add(new_block)
                db.session.commit()
                events.append(new_block)
                new_scheduled += (preferred_end - preferred_start).total_seconds() / 3600
                summary["blocks_added"] += 1
                summary["hours_added"] += (preferred_end - preferred_start).total_seconds() / 3600
                continue
        
            # If preferred slot not free, try to find other slots
            slots = free_slots(events, current_day)
            slots.sort(key=lambda slot: slot[1] - slots[0], reverse=True)  # Sort by duration descending
            for slot_start, slot_end in slots:
                slot_duration = (slot_end - slot_start).total_seconds() / 3600
                if slot_duration < SESSION:
                    continue  # Slot too small

                allocatable = min(slot_duration, hours_left - new_scheduled, today_max)
                if allocatable <= 0:
                    break

                block_start = slot_start
                block_end = slot_start + timedelta(hours=allocatable)

                new_block = Event(
                    title=f"Learning for {exam.title}",
                    start=to_iso(block_start),
                    end=to_iso(block_end),
                    color=STUDY_BLOCK_COLOR,
                    user_id=exam.user_id,
                    priority=4,
                    recurrence="None",
                    recurrence_id="0",
                    all_day=False,
                    locked=False,
                    exam_id=exam.id
                )
                db.session.add(new_block)
                db.session.commit()
                events.append(new_block)
                new_scheduled += allocatable
                summary["blocks_added"] += 1
                summary["hours_added"] += allocatable

                if new_scheduled >= hours_left:
                    break

            else:
                break
        if new_scheduled >= hours_left:
            successes[exam.title] = [True, f"Successfully scheduled all {hours_left:.1f} hours."]
        else:
            successes[exam.title] = [False, f"Could only schedule {new_scheduled:.1f} out of {hours_left:.1f} hours."]
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
    if int(data["priority"]) != 4:
        match int(data["priority"]):
            case 1:
                data["color"] = user.priority1_color
            case 2:
                data["color"] = user.priority2_color
            case 3:
                data["color"] = user.priority3_color
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
            if int(data["priority"]) != 4:
                match int(data["priority"]):
                    case 1:
                        data["color"] = user.priority1_color
                    case 2:
                        data["color"] = user.priority2_color
                    case 3:
                        data["color"] = user.priority3_color
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


@app.route("/api/populate", methods=["GET", "POST"])
@login_required
def populate_events():
    """Populate the database with example events."""
    event1 = Event(
        user_id=1,
        title="Meeting",
        start="2025-03-28T10:00:00",
        end="2025-03-28T12:00:00",
        color="#ff0000",
        priority=1,
    )
    event2 = Event(
        user_id=1,
        title="Workshop",
        start="2025-03-29T14:00:00",
        end="2025-03-29T16:00:00",
        color="#00ff00",
        priority=2,
    )
    event3 = Event(
        user_id=2,
        title="Conference",
        start="2025-03-30T09:00:00",
        end="2025-03-30T11:00:00",
        color="#0000ff",
        priority=3,
    )
    db.session.add_all([event1, event2, event3])
    db.session.commit()
    return "Events populated!", 201


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
    """Settings route: View and update user settings."""
    user = User.query.filter_by(username=session["username"]).first()
    if request.method == "POST":
        # Get data from form
        user.priority1_color = request.form.get("priority1_color", user.priority1_color)
        user.priority2_color = request.form.get("priority2_color", user.priority2_color)
        user.priority3_color = request.form.get("priority3_color", user.priority3_color)
        user.learn_on_saturday = "learn_on_saturday" in request.form
        user.learn_on_sunday = "learn_on_sunday" in request.form
        user.preferred_learning_time = request.form.get("learning_time", user.preferred_learning_time)
        db.session.commit()
        return redirect(url_for("settings"))
    return render_template(
        "settings.html",
        priority1_color=user.priority1_color,
        priority2_color=user.priority2_color,
        priority3_color=user.priority3_color,
        learn_on_saturday=user.learn_on_saturday,
        learn_on_sunday=user.learn_on_sunday,
        preferred_learning_time=user.preferred_learning_time
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
    return render_template("agenda.html")


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
