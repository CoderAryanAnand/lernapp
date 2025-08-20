# Import necessary libraries and modules
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_mailman import Mail, EmailMessage
import icalendar
import uuid
from datetime import datetime, timedelta
from itsdangerous import URLSafeTimedSerializer
from dateutil.relativedelta import relativedelta # for monthly recurrence
from dotenv import load_dotenv
import os   

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Configuration settings for the app
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db" # os.getenv("DATABASE_URL")  # SQLite database file
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False  # Disable modification tracking for performance
app.secret_key = os.getenv("SECRET_KEY")  # Secret key for session management

# Mail configuration settings
app.config["MAIL_SERVER"] = "smtp.gmail.com"  # Mail server
app.config["MAIL_PORT"] = 587  # Port for TLS
app.config["MAIL_USE_TLS"] = True  # Enable TLS
app.config["MAIL_USE_SSL"] = False  # Disable SSL
app.config["MAIL_USERNAME"] = "kantikoala@gmail.com"  # Email username
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")  # Email password

# Initialize database, bcrypt for password hashing, and mail for email functionality
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
mail = Mail(app)

# Define the User model for the database
class User(db.Model):
    """User model for storing authentication details."""
    id = db.Column(db.Integer, primary_key=True)  # Primary key
    username = db.Column(db.String(100), unique=True, nullable=False)  # Unique username
    password = db.Column(db.String(100), nullable=False)  # Hashed password
    email = db.Column(db.String(100), unique=True, nullable=False)  # Unique email address

    # Relationship to events with cascade delete
    events = db.relationship("Event", backref="user", lazy=True, cascade="all, delete-orphan")

# Define the Event model for the database
class Event(db.Model):
    """Event model for storing user events."""
    id = db.Column(db.Integer, primary_key=True)  # Primary key
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", onupdate="CASCADE"), nullable=False)  # User ID to associate events with users
    title = db.Column(db.String(100), nullable=False)  # Event title
    start = db.Column(db.String(50), nullable=False)  # Start datetime in ISO format
    end = db.Column(db.String(50), nullable=True)  # End datetime in ISO format
    color = db.Column(db.String(7), nullable=False)  # Event color (e.g., #ff0000)
    priority = db.Column(db.Integer, nullable=False)  # Event priority (1-3)
    recurrence = db.Column(db.String(50), nullable=True)  # Recurrence pattern (e.g., "daily", "weekly", etc.)
    recurrence_id = db.Column(db.String(50), nullable=True)  # ID for recurrence events
    all_day = db.Column(db.Boolean, nullable=False, default=False)  # Whether the event is all-day

# Ensure database tables are created
with app.app_context():
    db.create_all()
    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
        with db.engine.connect() as connection:
            connection.execute(db.text("PRAGMA foreign_keys=ON"))

# Function to convert Javascript string to boolean
def str_to_bool(val):
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() == "true"
    return False


# FullCalendar API route to fetch events
@app.route('/api/events', methods=['GET'])
def get_events():
    """Fetch events for the logged-in user."""
    logged_in_user = User.query.filter_by(username=session.get('username')).first()  # Get the logged-in user
    if not logged_in_user:
        return jsonify([])  # Return an empty list if no user is logged in
    logged_in_user_id = logged_in_user.id

    # Query the database for events belonging to the logged-in user
    user_events = Event.query.filter_by(user_id=logged_in_user_id).all()

    # Convert events to a format FullCalendar understands
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
            "allDay": event.all_day
        }
        for event in user_events
    ]

    # Return events as JSON
    return jsonify(events)

# API route to create a new event
@app.route('/api/events', methods=['POST'])
def create_event():
    """Create a new event."""
    data = request.json  # Get event data from the request
    all_day = str_to_bool(data.get('all_day', False))

    if data["recurrence"] != "none":
        # Generate a unique recurrence ID for the event
        recurrence_id = str(uuid.uuid4().int)  # Use UUID to ensure uniqueness

        # Create recurring events based on the recurrence pattern
        if data["recurrence"] == "daily":
            for i in range(7):  # Create events for the next 7 days
                new_event = Event(
                    title=data['title'],
                    start=(datetime.fromisoformat(data['start']) + timedelta(days=i)).isoformat(),
                    end=(datetime.fromisoformat(data['end']) + timedelta(days=i)).isoformat() if data.get('end') else None,
                    color=data['color'],
                    user_id=User.query.filter_by(username=session['username']).first().id,
                    priority=data['priority'],
                    recurrence=data['recurrence'],
                    recurrence_id=recurrence_id,
                    all_day=all_day
                )
                db.session.add(new_event)
        elif data["recurrence"] == "weekly":
            for i in range(4):  # Create events for the next 4 weeks
                new_event = Event(
                    title=data['title'],
                    start=(datetime.fromisoformat(data['start']) + timedelta(weeks=i)).isoformat(),
                    end=(datetime.fromisoformat(data['end']) + timedelta(weeks=i)).isoformat() if data.get('end') else None,
                    color=data['color'],
                    user_id=User.query.filter_by(username=session['username']).first().id,
                    priority=data['priority'],
                    recurrence=data['recurrence'],
                    recurrence_id=recurrence_id,
                    all_day=all_day
                )
                db.session.add(new_event)
        elif data["recurrence"] == "monthly":
            for i in range(12):
                new_event = Event(
                    title=data['title'],
                    start=(datetime.fromisoformat(data['start']) + timedelta(weeks=i*4)).isoformat(),
                    end=(datetime.fromisoformat(data['end']) + timedelta(weeks=i*4)).isoformat() if data.get('end') else None,
                    color=data['color'],
                    user_id=User.query.filter_by(username=session['username']).first().id,
                    priority=data['priority'],
                    recurrence=data['recurrence'],
                    recurrence_id=recurrence_id,
                    all_day=all_day
                )
                db.session.add(new_event)
        db.session.commit()
        return jsonify({"message": "Recurring events created"}), 201

    new_event = Event(
        title=data['title'],
        start=data['start'],
        end=data.get('end'),
        color=data['color'],
        user_id=User.query.filter_by(username=session['username']).first().id,  # Associate with the logged-in user
        priority=data['priority'],
        recurrence="None",
        recurrence_id="0",
        all_day=all_day
    )
    db.session.add(new_event)  # Add the event to the database
    db.session.commit()  # Commit the changes
    return jsonify({"message": "Event created"}), 201

# API route to update an existing event
@app.route('/api/events', methods=['PUT'])
def update_event():
    """Update an existing event."""
    data = request.json  # Get updated event data from the request
    # Check if the event is a single event or part of a recurrence
    # If the event is not part of a recurrence or if it is the only event in the recurrence, which would happen if all other recurrences were deleted
    if data["edit-recurrence"] != "all" and data["recurrence-id"] == "0" or len(Event.query.filter_by(recurrence_id=data['recurrence-id']).all()) == 1:
        # Update a single event
        event = Event.query.get(data['id'])  # Find the event by ID
        event.title = data['title']  # Update title
        event.start = data['start']  # Update start time
        event.end = data.get('end')  # Update end time
        event.color = data['color']  # Update color
        event.priority = data['priority']  # Update priority
        event.recurrence = "None"  # Set recurrence to None, as it is not recurring anymore
        event.recurrence_id = "0"  # Set recurrence ID to 0, as it is not recurring anymore
        event.all_day = str_to_bool(data.get('all_day', False))  # Update all-day status
        db.session.commit()  # Commit the changes
        return jsonify({"message": "Event updated"}), 200
    else:
        # Update all events with the same recurrence ID
        events = Event.query.filter_by(recurrence_id=data['recurrence-id']).all() # Find all events with the same recurrence ID

        # Parse the new start time and date
        new_start_datetime = datetime.fromisoformat(data['start'])
        new_start_time = new_start_datetime.time()
        new_start_date = new_start_datetime.date()

        # Determine the recurrence pattern
        recurrence_pattern = events[0].recurrence

        for i, event in enumerate(events):
            # Update the title, color, and priority for all events
            event.title = data['title']
            event.color = data['color']
            event.priority = data['priority']
            event.all_day = str_to_bool(data.get('all_day', False))  # Update all-day status

            # Update the start time and date for each event based on the recurrence pattern
            current_start_datetime = datetime.fromisoformat(event.start)
            if recurrence_pattern == "daily":
                updated_start_datetime = datetime.combine(
                    new_start_date + timedelta(days=i),  # Adjust the date for daily recurrence
                    new_start_time
                )
            elif recurrence_pattern == "weekly":
                updated_start_datetime = datetime.combine(
                    new_start_date + timedelta(weeks=i),  # Adjust the date for weekly recurrence
                    new_start_time
                )
            elif recurrence_pattern == "monthly":
                updated_start_datetime = datetime.combine(
                    new_start_date + relativedelta(months=i),  # Adjust for monthly recurrence
                    new_start_time
                )
            else:
                return jsonify({"message": "Unsupported recurrence pattern"}), 400

            event.start = updated_start_datetime.isoformat()

            # Update the end time if provided
            if event.end:
                current_end_datetime = datetime.fromisoformat(event.end)
                duration = current_end_datetime - current_start_datetime
                updated_end_datetime = updated_start_datetime + duration
                event.end = updated_end_datetime.isoformat()

        db.session.commit()  # Commit the changes
        return jsonify({"message": "Recurring events updated"}), 200

# API route to delete an event
@app.route('/api/events/<int:event_id>', methods=['DELETE'])
def delete_event(event_id):
    """Delete an event."""
    event = Event.query.get(event_id)  # Find the event by ID
    db.session.delete(event)  # Delete the event
    db.session.commit()  # Commit the changes
    return jsonify({"message": "Event deleted"}), 200

@app.route('/api/events/recurring/<recurrence_id>', methods=['DELETE'])
def delete_recurring_events(recurrence_id):
    """Delete all events with the same recurrence ID."""
    logged_in_user = User.query.filter_by(username=session.get('username')).first()
    if not logged_in_user:
        return jsonify({"error": "Unauthorized"}), 401

    # Delete all events with the given recurrence ID for the logged-in user
    Event.query.filter_by(recurrence_id=recurrence_id, user_id=logged_in_user.id).delete()
    db.session.commit()
    return jsonify({"message": "Recurring events deleted"}), 200

# Route to populate the database with example events
@app.route('/api/populate', methods=["GET", 'POST'])
def populate_events():
    """Populate the database with example events."""
    # Example events for user_id 1
    event1 = Event(user_id=1, title="Meeting", start="2025-03-28T10:00:00", end="2025-03-28T12:00:00", color="#ff0000", priority=1)
    event2 = Event(user_id=1, title="Workshop", start="2025-03-29T14:00:00", end="2025-03-29T16:00:00", color="#00ff00", priority=2)

    # Example events for user_id 2
    event3 = Event(user_id=2, title="Conference", start="2025-03-30T09:00:00", end="2025-03-30T11:00:00", color="#0000ff", priority=3)

    db.session.add_all([event1, event2, event3])  # Add events to the database
    db.session.commit()  # Commit the changes

    return "Events populated!", 201

# Home route
@app.route("/")
def home():
    """Home route: Displays login/register buttons or welcome message if logged in."""
    # Read tips from the file
    try:
        with open("tips/tips.txt", "r") as file:
            tips = file.readlines()
    except FileNotFoundError:  
        tips = ["No tips available."]

    tip_of_the_day = tips[datetime.now().timetuple().tm_yday % len(tips)].strip()  # Select a random tip based on the current day

    if "username" in session:
        return render_template("home.html", username=session["username"], logged_in=True, tip=tip_of_the_day)
    return render_template("home.html", logged_in=False, tip=tip_of_the_day)

# Login route
@app.route("/login", methods=["GET", "POST"])
def login():
    """Login route: Handles login form submission and user authentication."""
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()

        if user and bcrypt.check_password_hash(user.password, password):
            session["username"] = username  # Store session data
            return redirect(url_for("home"))
        return "Invalid credentials. Try again."

    return render_template("login.html")

# Forgot password route
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
            print(token)
            print(user.password)
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
    
# Reset password route
@app.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    """Reset password route: Handles password reset form submission."""
    serializer = URLSafeTimedSerializer(app.secret_key)

    if request.method == "POST":
        try:
            user = User.query.filter_by(username=request.form["username"]).first()
            print(user.password)
            email = serializer.loads(request.form["token"], salt=user.password, max_age=900)  # Validate token
        except Exception as e:
            return "Invalid or expired token."
        if request.form["new_password"] == request.form["confirm_password"]:
            # Update the user's password in the database
            new_password = request.form["new_password"]
            user = User.query.filter_by(email=email).first()
            if user:
                hashed_password = bcrypt.generate_password_hash(new_password).decode("utf-8")
                user.password = hashed_password
                db.session.commit()  # Commit the changes
                return redirect(url_for("login"))  # Redirect to login after password reset
            return "User not found. Try again."
        else:
            return "Passwords do not match. Try again."
    else:  
        return render_template("reset_password.html", token=token)

# Register route
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

        hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")  # Securely hash password
        new_user = User(username=username, password=hashed_password, email=email)
        db.session.add(new_user)
        db.session.commit()
        session["username"] = username  # Store session data
        return redirect(url_for("home"))

    return render_template("register.html")

# Logout route
@app.route("/logout")
def logout():
    """Logout route: Removes user session data and redirects to home."""
    session.pop("username", None)
    return redirect(url_for("home"))

# Settings route
@app.route("/settings")
def settings():
    """Settings route: Goes to the general settings of the account and page."""
    return render_template("settings.html")

# Delete account route
@app.route("/settings/delete_account")
def delete_account():
    """Delete account route: Deletes user account currently in session."""
    current_user = session["username"]
    db.session.delete(User.query.filter_by(username=current_user).first())
    db.session.commit()
    session.clear()
    return redirect(url_for("home"))

# Change password route
@app.route("/settings/change_password", methods=["GET", "POST"])
def change_password():
    """Change password route: Changes the password of the user currently in session."""
    if request.method == "POST":
        old_password = request.form["ogpw"]
        new_password = request.form["newpw"]
        confirm_password = request.form["confirm"]

        if not bcrypt.check_password_hash(User.query.filter_by(username=session["username"]).first().password, old_password):
            return "Incorrect old password. Try again."

        if new_password != confirm_password:
            return "Passwords do not match. Try again."
        
        hashed_password = bcrypt.generate_password_hash(new_password).decode("utf-8")
        User.query.filter_by(username=session["username"]).first().password = hashed_password
        db.session.commit()
        return redirect(url_for("home"))

    return render_template("change_password.html")    

# Agenda route
@app.route("/agenda")
def agenda():
    """Agenda route: Displays the agenda of the user currently in session."""
    return render_template("agenda.html")

# API route to import events from an .ics file
@app.route('/api/import-ics', methods=['POST'])
def import_ics():
    """Import events from an .ics file."""
    data = request.json
    ics_content = data.get('ics')

    if not ics_content:
        return jsonify({"message": "No .ics content provided"}), 400

    try:
        calendar = icalendar.Calendar.from_ical(ics_content)
        for component in calendar.walk():
            if component.name == "VEVENT":
                title = str(component.get('SUMMARY', 'Untitled Event'))
                start = component.get('DTSTART').dt
                end = component.get('DTEND').dt if component.get('DTEND') else None
                color = "#fcba03"  # Default color for imported events

                # Save the event to the database
                logged_in_user = User.query.filter_by(username=session.get('username')).first()
                if not logged_in_user:
                    return jsonify({"message": "No logged-in user found"}), 400

                new_event = Event(
                    title=title,
                    start=start.isoformat(),
                    end=end.isoformat() if end else None,
                    color=color,
                    user_id=logged_in_user.id,  # Use the logged-in user's ID
                    priority=1,
                    recurrence="None",
                    recurrence_id=0
                )
                db.session.add(new_event)


        db.session.commit()
        return jsonify({"message": "Events imported successfully"}), 200
    except Exception as e:
        print("Error importing .ics file:", e)
        return jsonify({"message": "Failed to import .ics file"}), 500

# Run the application
if __name__ == "__main__":
    app.run(debug=True)
