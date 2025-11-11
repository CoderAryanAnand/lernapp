from flask import Flask, render_template, session
from kkoala.models import User
from dotenv import load_dotenv
import resend

from .routes import register_blueprints
from .extensions import db, bcrypt, migrate
from .utils import make_csrf_token

load_dotenv()


def create_app(config_class="config.ProdConfig"):
    """
    Application factory function for creating and configuring the Flask app.
    This pattern allows flexible configuration and easier testing.
    """
    # Create the Flask application instance
    app = Flask(__name__, static_folder="static", template_folder="templates")
    # Load configuration from the given config class
    app.config.from_object(config_class)

    # Initialize Flask extensions with the app
    db.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)

    # Configure Resend API key for email sending, if set
    resend_key = app.config.get("RESEND_API_KEY")
    if resend_key:
        resend.api_key = resend_key

    # Register a CSRF token generator to run before each request
    app.before_request(make_csrf_token)

    # Custom error handler for 404 Not Found
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template("404.html"), 404

    # Custom error handler for 500 Internal Server Error
    @app.errorhandler(500)
    def internal_error(error):
        # Roll back the database session to avoid invalid states
        db.session.rollback()
        return render_template("500.html"), 500

    # Custom error handler for 403 Forbidden
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template("403.html"), 403

    # Register all application blueprints (routes)
    register_blueprints(app)

    @app.context_processor
    def inject_dark_mode_setting():
        """
        Injects the user's dark mode preference into all templates.
        Defaults to 'system' if the user is not logged in or has no setting.
        """
        dark_mode = 'system'  # Default value
        if 'username' in session:
            user = User.query.filter_by(username=session['username']).first()
            if user and user.settings:
                dark_mode = user.settings.dark_mode
        return dict(dark_mode_setting=dark_mode)

    # Optionally create all database tables if CREATE_DB is set in config
    if app.config.get("CREATE_DB"):
        with app.app_context():
            db.create_all()

    # For SQLite: ensure foreign key constraints are enforced
    # This PRAGMA must be set for every new connection
    if app.config.get("SQLALCHEMY_DATABASE_URI", "").startswith("sqlite"):
        with app.app_context():
            with db.engine.connect() as connection:
                connection.execute(db.text("PRAGMA foreign_keys=ON"))

    # Return the configured Flask app instance
    return app
