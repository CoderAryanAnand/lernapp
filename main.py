from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt

# Initialize Flask app
app = Flask(__name__)

# Configuration settings
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db"  # SQLite database file
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False  # Disable modification tracking for performance
app.secret_key = "your_secret_key"  # Secret key for session management

# Initialize database and bcrypt for password hashing
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# Define the User model for the database
class User(db.Model):
    """User model for storing authentication details."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

# Ensure database tables are created
with app.app_context():
    db.create_all()

@app.route("/")
def home():
    """Home route: Displays login/register buttons or welcome message if logged in."""
    if "username" in session:
        return render_template("home.html", username=session["username"], logged_in=True)
    return render_template("home.html", logged_in=False)

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

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return "User already exists. Choose another username."

        hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")  # Securely hash password
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/logout")
def logout():
    """Logout route: Removes user session data and redirects to home."""
    session.pop("username", None)
    return redirect(url_for("home"))

# Run the application
if __name__ == "__main__":
    app.run(debug=True)
