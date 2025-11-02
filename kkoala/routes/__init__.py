from .auth import auth_bp
from .events import events_bp
from .grades import grades_bp
from .settings import settings_bp
from .main import main_bp


def register_blueprints(app):
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(events_bp, url_prefix="/api/events")
    app.register_blueprint(grades_bp, url_prefix="/api/noten")
    app.register_blueprint(settings_bp, url_prefix="/settings")
    app.register_blueprint(main_bp)
