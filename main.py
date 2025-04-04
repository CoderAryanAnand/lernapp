# Import necessary libraries and modules
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_mailman import Mail, EmailMessage

# Initialize Flask app
app = Flask(__name__)

# Configuration settings for the app
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db"  # SQLite database file
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False  # Disable modification tracking for performance
app.secret_key = "your_secret_key"  # Secret key for session management

# Mail configuration settings
app.config["MAIL_SERVER"] = "smtp.gmail.com"  # Mail server
app.config["MAIL_PORT"] = 587  # Port for TLS
app.config["MAIL_USE_TLS"] = True  # Enable TLS
app.config["MAIL_USE_SSL"] = False  # Disable SSL
app.config["MAIL_USERNAME"] = "kantikoala@gmail.com"  # Email username
app.config["MAIL_PASSWORD"] = "your_password"  # Email password

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

# Ensure database tables are created
with app.app_context():
    db.create_all()
    db.engine.execute('PRAGMA foreign_keys=ON')

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
            "priority": event.priority
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
    new_event = Event(
        title=data['title'],
        start=data['start'],
        end=data.get('end'),
        color=data['color'],
        user_id=User.query.filter_by(username=session['username']).first().id,  # Associate with the logged-in user
        priority=1
    )
    db.session.add(new_event)  # Add the event to the database
    db.session.commit()  # Commit the changes
    return jsonify({"message": "Event created"}), 201

# API route to update an existing event
@app.route('/api/events', methods=['PUT'])
def update_event():
    """Update an existing event."""
    data = request.json  # Get updated event data from the request
    event = Event.query.get(data['id'])  # Find the event by ID
    event.title = data['title']  # Update title
    event.start = data['start']  # Update start time
    event.end = data.get('end')  # Update end time
    event.color = data['color']  # Update color
    db.session.commit()  # Commit the changes
    return jsonify({"message": "Event updated"}), 200

# API route to delete an event
@app.route('/api/events/<int:event_id>', methods=['DELETE'])
def delete_event(event_id):
    """Delete an event."""
    event = Event.query.get(event_id)  # Find the event by ID
    db.session.delete(event)  # Delete the event
    db.session.commit()  # Commit the changes
    return jsonify({"message": "Event deleted"}), 200

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
    if "username" in session:
        return render_template("home.html", username=session["username"], logged_in=True)
    return render_template("home.html", logged_in=False)

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

# Run the application
if __name__ == "__main__":
    app.run(debug=True)
