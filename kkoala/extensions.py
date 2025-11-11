# Import Flask extensions for database, password hashing, and migrations
from flask_sqlalchemy import SQLAlchemy      # ORM for database models and queries
from flask_bcrypt import Bcrypt              # Secure password hashing
from flask_migrate import Migrate            # Database schema migrations

# Instantiate the extensions (to be initialized with the Flask app in the factory)
db = SQLAlchemy()    # Handles all database operations and models
bcrypt = Bcrypt()    # Provides methods for hashing and checking passwords
migrate = Migrate()  # Manages database migrations (schema changes)
