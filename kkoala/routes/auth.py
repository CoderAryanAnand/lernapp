from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    current_app,
    flash,
)
from ..extensions import db, bcrypt
from ..models import User, Settings, PrioritySetting
from ..utils import csrf_protect, login_required
from ..consts import DEFAULT_SETTINGS, FROM_EMAIL
from itsdangerous import URLSafeTimedSerializer
import resend

auth_bp = Blueprint(
    "auth", __name__, template_folder="../templates", static_folder="../static"
)


@auth_bp.route("/login", methods=["GET", "POST"])
@csrf_protect
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
            return redirect(url_for("main.index"))
        flash("Invalid credentials. Try again.", "error")
        return render_template("login.html")
    return render_template("login.html")


@auth_bp.route("/forgot_password", methods=["GET", "POST"])
@csrf_protect
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
            serializer = URLSafeTimedSerializer(current_app.secret_key)
            token = serializer.dumps(email, salt=user.password)
            reset_link = url_for("auth.reset_password", token=token, _external=True)

            params = {
                "from": FROM_EMAIL,
                "to": [email],
                "subject": "Password Reset Request",
                "html": f"<strong>Click the link to reset your password: {reset_link}</strong>",
            }

            email = resend.Emails.send(params)

            flash("Password reset link sent to your email.", "info")
        else:
            flash("Email not found. Try again.", "error")
        return render_template("forgot_password.html")
    else:
        return render_template("forgot_password.html")


@auth_bp.route("/reset_password/<token>", methods=["GET", "POST"])
@csrf_protect
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
    serializer = URLSafeTimedSerializer(current_app.secret_key)

    if request.method == "POST":
        try:
            # Requires the username from the form to correctly retrieve the user and their password hash (salt)
            user = User.query.filter_by(username=request.form["username"]).first()
            # Loads email from token, validating signature (salt) and max age (e.g., 15 min)
            email = serializer.loads(
                request.form["token"], salt=user.password, max_age=900
            )
        except Exception:
            # FIX: Replace string return with flash and redirect
            flash(
                "Invalid or expired token. Please request a new password reset link.",
                "error",
            )
            return redirect(url_for("auth.forgot_password"))

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
                flash(
                    "Your password has been reset successfully. Please log in.",
                    "success",
                )
                return redirect(url_for("auth.login"))

            # FIX: Replace string return with flash and redirect
            flash("An unexpected error occurred. Please try again.", "error")
            return redirect(url_for("auth.forgot_password"))
        else:
            # FIX: Replace string return with flash and re-render
            flash("Passwords do not match. Please try again.", "error")
            return render_template("reset_password.html", token=token)
    else:
        return render_template("reset_password.html", token=token)


@auth_bp.route("/register", methods=["GET", "POST"])
@csrf_protect
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
            flash("User already exists. Choose another username.", "error")
            return render_template("register.html")

        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            flash("Email already registered. Use another email.", "error")
            return render_template("register.html")

        # Hash password and create new user
        hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")
        new_user = User(username=username, password=hashed_password, email=email)
        db.session.add(new_user)
        db.session.commit()  # Commit to get new_user.id

        # Create default settings for the new user
        default_settings = Settings(
            user_id=new_user.id,
            learn_on_saturday=DEFAULT_SETTINGS["learn_on_saturday"],
            learn_on_sunday=DEFAULT_SETTINGS["learn_on_sunday"],
            preferred_learning_time=DEFAULT_SETTINGS["preferred_learning_time"],
            study_block_color=DEFAULT_SETTINGS["study_block_color"],
        )
        db.session.add(default_settings)
        db.session.flush()  # Flush to get default_settings.id

        # Create default PrioritySetting entries (P1, P2, P3)
        for level in [1, 2, 3]:
            priority = DEFAULT_SETTINGS["priority_settings"][level]
            db.session.add(
                PrioritySetting(
                    settings_id=default_settings.id,
                    priority_level=level,
                    color=priority["color"],
                    # days_to_learn=priority["days_to_learn"],
                    max_hours_per_day=priority["max_hours_per_day"],
                    total_hours_to_learn=priority["total_hours_to_learn"],
                )
            )
        db.session.commit()

        session["username"] = username
        return redirect(url_for("main.index"))

    return render_template("register.html")


@auth_bp.route("/logout")
@login_required
def logout(user):
    """
    Logout route: Clears the user session and redirects to the home page.

    Returns:
        redirect: Redirects to the home route.
    """
    session.pop("username", None)
    return redirect(url_for("main.index"))
