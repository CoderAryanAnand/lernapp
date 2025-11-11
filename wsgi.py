# WSGI entry point for the KantiKoala Flask application.
# This file is used by WSGI servers (e.g., Gunicorn, uWSGI) to run the app in production.

from kkoala import create_app  # Import the application factory function

# Specify the configuration to use for the Flask app.
# You can change this to another config class if needed (e.g., for production or testing).
config = "kkoala.config.ProdConfig"

# Create the Flask application instance using the factory pattern.
# The 'application' variable is recognized by most WSGI servers as the entry point.
application = create_app(config)