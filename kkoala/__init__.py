from flask import Flask
from dotenv import load_dotenv
import resend

from .routes import register_blueprints
from .extensions import db, bcrypt, migrate
from .utils import make_csrf_token

load_dotenv()

def create_app(config_class="config.ProdConfig"):
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(config_class)

    db.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)

    resend_key = app.config.get("RESEND_API_KEY")
    if resend_key:
        resend.api_key = resend_key

    app.before_request(make_csrf_token)

    register_blueprints(app)

    if app.config.get("CREATE_DB"):
        with app.app_context():
            db.create_all()
    
    # Ensure SQLite PRAGMA runs inside an application context so db.engine can access current_app
    if app.config.get("SQLALCHEMY_DATABASE_URI", "").startswith("sqlite"):
        with app.app_context():
            with db.engine.connect() as connection:
                connection.execute(db.text("PRAGMA foreign_keys=ON"))

    return app