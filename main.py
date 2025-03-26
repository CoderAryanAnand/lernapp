from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_mailman import Mail, EmailMessage

# Initialize Flask app
app = Flask(__name__)

# Configuration settings
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db"  # SQLite database file
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False  # Disable modification tracking for performance
app.secret_key = "your_secret_key"  # Secret key for session management

# Mail configuration settings
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USE_SSL"] = False
app.config["MAIL_USERNAME"] = "kantikoala@gmail.com"
app.config["MAIL_PASSWORD"] = "your_password"

# Initialize database and bcrypt for password hashing
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
mail = Mail(app)

# Define the User model for the database
class User(db.Model):
    """User model for storing authentication details."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)

# Ensure database tables are created
with app.app_context():
    db.create_all()

@app.route("/")
def home():
    """Home route: Displays login/register buttons or welcome message if logged in."""
    if "username" in session:
        return render_template("home.html", username=session["username"], logged_in=True)
    return render_template("home.html", logged_in=False)

# User authentication routes
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

@app.route("/logout")
def logout():
    """Logout route: Removes user session data and redirects to home."""
    session.pop("username", None)
    return redirect(url_for("home"))

# Account settings routes
@app.route("/settings")
def settings():
    """Settings route: Goes to the general settings of the account and page."""
    return render_template("settings.html")

@app.route("/settings/delete_account")
def delete_account():
    """Delete account route: Deletes user account currently in session."""
    current_user = session["username"]
    db.session.delete(User.query.filter_by(username=current_user).first())
    db.session.commit()
    session.clear()
    return redirect(url_for("home"))

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


# Features
@app.route("/agenda")
def agenda():
    """Agenda route: Displays the agenda of the user currently in session."""
    return render_template("agenda.html")



# Run the application
if __name__ == "__main__":
    app.run(debug=True)
