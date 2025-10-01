# Import necessary libraries and modules
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_mailman import Mail, EmailMessage
from functools import wraps
import icalendar
import uuid
from datetime import datetime, timedelta
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


def learning_time_algorithm(events):
    """
    Analyze the user's events and suggest optimal learning times before exams.
    """
    now = datetime.now()
    exams = {}
    for event in events:
        event_start = datetime.fromisoformat(event.start)
        if event_start < now:
            continue
        if "test" in event.title.lower():
            event_date = datetime.fromisoformat(event.start).date()
            event_priority = event.priority
            event_name = event.title
            exams[event_name] = {"date": event_date, "priority": event_priority}
    # Sort exams by priority (1 is highest)
    sorted_exams = dict(sorted(exams.items(), key=lambda item: item[1]["priority"]))
    learn_time_based_on_priority = {
        "1": 14,
        "2": 7,
        "3": 3,
    }  # Hours to learn before the exam based on priority
    learning_slots = []
    for exam, details in sorted_exams.items():
        exam_date = details["date"]
        priority = str(details["priority"])
        hours_to_learn = learn_time_based_on_priority.get(priority)
        average_daily_learning = hours_to_learn // 7  # Spread learning over a week
        if not average_daily_learning:
            average_daily_learning = 0.5  # Minimum of 30 minutes if less than 1 hour
        for day in range(7):
            learn_date = exam_date - timedelta(days=day)
            day_events = [
                e
                for e in events
                if datetime.fromisoformat(e.start).date() == learn_date
            ]
            extra_hours = 0
            if day_events:
                busy_times = [
                    (
                        datetime.fromisoformat(e.start),
                        (
                            datetime.fromisoformat(e.end)
                            if e.end
                            else datetime.fromisoformat(e.start) + timedelta(hours=1)
                        ),
                    )
                    for e in day_events
                ]
                busy_times.sort()
                free_start = datetime.combine(
                    learn_date, datetime.min.time()
                ) + timedelta(
                    hours=8
                )  # 8 AM
                free_end = datetime.combine(
                    learn_date, datetime.min.time()
                ) + timedelta(
                    hours=22
                )  # 10 PM
                for start, end in busy_times:
                    if free_start < start:
                        free_slot_duration = (start - free_start).total_seconds() / 3600
                        if free_slot_duration >= average_daily_learning + extra_hours:
                            learning_slots.append(
                                {
                                    "title": f"Study for {exam}",
                                    "start": free_start.isoformat(),
                                    "end": (
                                        free_start
                                        + timedelta(
                                            hours=average_daily_learning + extra_hours
                                        )
                                    ).isoformat(),
                                    "color": "#03fcba",
                                    "priority": details["priority"],
                                    "all_day": False,
                                }
                            )
                            break
                        elif free_slot_duration >= 0.5:
                            learning_slots.append(
                                {
                                    "title": f"Study for {exam}",
                                    "start": free_start.isoformat(),
                                    "end": (
                                        free_start + timedelta(hours=free_slot_duration)
                                    ).isoformat(),
                                    "color": "#03fcba",
                                    "priority": details["priority"],
                                    "all_day": False,
                                }
                            )
                            extra_hours += average_daily_learning - free_slot_duration


# ---------------------- API Endpoints for Events ----------------------


@login_required
@app.route("/api/events", methods=["GET"])
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


@login_required
@app.route("/api/events", methods=["POST"])
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
    )
    db.session.add(new_event)
    db.session.commit()
    return jsonify({"message": "Event created"}), 201


@login_required
@app.route("/api/events", methods=["PUT"])
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


@login_required
@app.route("/api/events/<int:event_id>", methods=["DELETE"])
def delete_event(event_id):
    """Delete an event."""
    event = Event.query.get(event_id)
    db.session.delete(event)
    db.session.commit()
    return jsonify({"message": "Event deleted"}), 200


@login_required
@app.route("/api/events/recurring/<recurrence_id>", methods=["DELETE"])
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


@login_required
@app.route("/api/populate", methods=["GET", "POST"])
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


@login_required
@app.route("/logout")
def logout():
    """Logout route: Removes user session data and redirects to home."""
    session.pop("username", None)
    return redirect(url_for("home"))


@login_required
@app.route("/settings", methods=["GET", "POST"])
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


@login_required
@app.route("/settings/delete_account")
def delete_account():
    """Delete account route: Deletes user account currently in session."""
    current_user = session["username"]
    db.session.delete(User.query.filter_by(username=current_user).first())
    db.session.commit()
    session.clear()
    return redirect(url_for("home"))


@login_required
@app.route("/settings/change_password", methods=["GET", "POST"])
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


@login_required
@app.route("/agenda")
def agenda():
    """Agenda route: Displays the agenda of the user currently in session."""
    return render_template("agenda.html")


@login_required
@app.route("/api/import-ics", methods=["POST"])
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


@login_required
@app.route("/noten")
def noten():
    """Noten route: Displays the noten (grades) page."""
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("noten.html")


@login_required
@app.route("/api/noten", methods=["GET"])
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


@login_required
@app.route("/api/noten", methods=["POST"])
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
