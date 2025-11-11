# Import Flask modules for routing, request handling, session management, and rendering
from flask import (
    Blueprint,
    request,
    jsonify,
    current_app,
    session,
    redirect,
    render_template,
    url_for,
    flash,
)

# Import application extensions and models
from ..extensions import db, bcrypt
from ..models import User, Event, Settings, PrioritySetting
from ..utils import csrf_protect, login_required

# Define the blueprint for settings-related routes
settings_bp = Blueprint(
    "settings", __name__, template_folder="../templates", static_folder="../static"
)

@settings_bp.route("/", methods=["GET", "POST"])
@csrf_protect
@login_required
def settings_view(user):
    """
    Settings route: Allows the user to view and update their general and priority study settings.

    POST: Handles updating general settings, adding new priority levels, and
          removing/modifying existing priority rules.
    GET: Renders the settings form.

    Returns:
        str: Rendered HTML template ('settings.html') or a redirect.
    """
    settings = Settings.query.filter_by(user_id=user.id).first()

    if request.method == "POST":
        # Handle account deletion first as it's a terminal action
        if "delete_account" in request.form:
            db.session.delete(user)
            db.session.commit()
            session.clear()
            return redirect(url_for("main.index"))

        # Handle adding a new priority level
        if "add_priority" in request.form:
            # Determine the next priority level
            existing_levels = [p.priority_level for p in settings.priority_settings]
            next_level = max(existing_levels, default=0) + 1

            # Shift all events with current priority >= next_level up by 1
            user_events = Event.query.filter(
                Event.user_id == user.id, Event.priority >= next_level
            ).all()
            for event in user_events:
                event.priority += 1

            # Add the new priority setting with default values
            new_prio = PrioritySetting(
                settings_id=settings.id,
                priority_level=next_level,
                color="#000000",
                # days_to_learn=7,
                max_hours_per_day=2.0,
                total_hours_to_learn=7.0,
            )
            db.session.add(new_prio)
            db.session.commit()
            return redirect(url_for("settings.settings_view"))

        # Handle removing a priority level
        elif "remove_priority" in request.form:
            level_to_remove = int(request.form["remove_priority"])
            prio_setting = PrioritySetting.query.filter_by(
                settings_id=settings.id, priority_level=level_to_remove
            ).first()
            if prio_setting:
                db.session.delete(prio_setting)
                # Shift all higher priority levels down by 1
                higher_prios = (
                    PrioritySetting.query.filter(
                        PrioritySetting.settings_id == settings.id,
                        PrioritySetting.priority_level > level_to_remove,
                    )
                    .order_by(PrioritySetting.priority_level)
                    .all()
                )
                for p in higher_prios:
                    p.priority_level -= 1
                db.session.commit()
            
            # Shift all user events a priority down, if their priority was above the one deleted
            user_events = Event.query.filter(
                Event.user_id == user.id, Event.priority > level_to_remove
            ).all()
            for event in user_events:
                event.priority -= 1
            db.session.commit()
            return redirect(url_for("settings.settings_view"))

        # Update general settings
        settings.learn_on_saturday = "learn_on_saturday" in request.form
        settings.learn_on_sunday = "learn_on_sunday" in request.form
        settings.preferred_learning_time = request.form.get(
            "learning_time", settings.preferred_learning_time
        )
        settings.study_block_color = request.form.get(
            "study_block_color", settings.study_block_color
        )
        settings.import_color = request.form.get(
            "import_color", settings.import_color
        )
        settings.dark_mode = request.form.get("dark_mode", "system") # Save the dark mode setting

        # Update specific priority settings (color, max hours, total hours, etc.)
        for prio in settings.priority_settings:
            prio.color = request.form.get(
                f"priority{prio.priority_level}_color", prio.color
            )
            # prio.days_to_learn = int(
            #     request.form.get(
            #         f"priority{prio.priority_level}_days", prio.days_to_learn
            #     )
            # )
            prio.max_hours_per_day = float(
                request.form.get(
                    f"priority{prio.priority_level}_max_hours_per_day",
                    prio.max_hours_per_day,
                )
            )
            prio.total_hours_to_learn = float(
                request.form.get(
                    f"priority{prio.priority_level}_total_hours_to_learn",
                    prio.total_hours_to_learn,
                )
            )

        db.session.commit()
        return redirect(url_for("settings.settings_view"))

    # Prepare values for GET request (render the settings form)
    return render_template(
        "settings.html",
        learn_on_saturday=settings.learn_on_saturday,
        learn_on_sunday=settings.learn_on_sunday,
        preferred_learning_time=settings.preferred_learning_time,
        priority_settings=sorted(
            settings.priority_settings, key=lambda p: p.priority_level
        ),  # Ensure list is sorted
        study_block_color=settings.study_block_color,
        import_color=settings.import_color,
    )

@settings_bp.route("/change_password", methods=["GET", "POST"])
@csrf_protect
@login_required
def change_password(user):
    """
    Change password route: Allows a logged-in user to change their password.

    POST: Verifies the old password using bcrypt, validates the new password
          confirmation, hashes the new password, and updates the database.
    GET: Renders the change password form.

    Returns:
        str: Rendered HTML template ('change_password.html') or a redirect.
    """
    if request.method == "POST":
        old_password = request.form["ogpw"]
        new_password = request.form["newpw"]
        confirm_password = request.form["confirm"]

        # Check old password
        if not bcrypt.check_password_hash(user.password, old_password):
            flash("Altes Passwort ist falsch. Bitte versuche es erneut.", "error")
            return render_template("change_password.html")

        # Check new password confirmation
        if new_password != confirm_password:
            flash("Die Passwörter stimmen nicht überein. Bitte versuche es erneut.", "error")
            return render_template("change_password.html")

        # Hash and update new password
        hashed_password = bcrypt.generate_password_hash(new_password).decode("utf-8")
        user.password = hashed_password
        db.session.commit()
        flash("Passwort erfolgreich geändert.", "success")
        return render_template("change_password.html")

    return render_template("change_password.html")
