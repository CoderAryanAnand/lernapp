from flask import Blueprint, render_template, session, current_app, abort
from datetime import datetime
import os, json

from ..models import Settings, User, Semester
from ..utils import login_required

main_bp = Blueprint(
    "main", __name__, template_folder="../templates", static_folder="../static"
)


@main_bp.route("/")
def index():
    """
    Home route: Handles the main landing page display.

    If the user is logged in, it shows a welcome message and a daily tip.
    Otherwise, it shows login/register links.

    Returns:
        str: Rendered HTML template ('home.html').
    """
    # Read tips from the file (assumes 'tips/tips.txt' exists)
    try:
        tips_file_path = os.path.join(current_app.root_path, "tips", "daily_tips.txt")
        with open(tips_file_path, "r", encoding="utf-8") as file:
            tips = file.readlines()
    except FileNotFoundError:
        tips = ["No tips available."]

    # Selects a tip based on the day of the year (ensures a different tip daily)
    tip_of_the_day = tips[datetime.now().timetuple().tm_yday % len(tips)].strip()

    if "username" in session:
        return render_template(
            "home.html",
            username=session["username"],
            logged_in=True,
            tip=tip_of_the_day,
        )
    return render_template("home.html", logged_in=False, tip=tip_of_the_day)


@main_bp.route("/agenda")
@login_required
def agenda(user):
    """
    Agenda route: Renders the calendar (FullCalendar) view.

    Passes the user's priority settings to the template for client-side display logic.

    Returns:
        str: Rendered HTML template ('agenda.html').
    """
    settings = Settings.query.filter_by(user_id=user.id).first()

    priority_levels = settings.priority_settings
    # Sort priority levels to display them correctly in the frontend
    priority_levels = sorted(priority_levels, key=lambda x: x.priority_level)

    return render_template("agenda.html", priority_levels=priority_levels)


@main_bp.route("/noten")
@login_required
def noten(user):
    """
    Noten route: Renders the grades management page.

    Returns:
        str: Rendered HTML template ('noten.html').
    """
    semesters = Semester.query.filter_by(user_id=user.id).all()
    return render_template("noten.html", semesters=semesters)


@main_bp.route("/lerntimer")
def lerntimer():
    """
    Pomodoro timer route: Renders the lerntimer page.

    Returns:
        str: Rendered HTML template ('lerntimer.html').
    """
    return render_template("lerntimer.html")


@main_bp.route("/lerntipps")
def lerntipps():
    """
    Learning tips route: Renders the lerntipps page.

    Returns:
        str: Rendered HTML template ('lerntipps.html').
    """

    tips_file_path = os.path.join(current_app.root_path, "tips", "learn_tips.json")
    with open(tips_file_path, "r", encoding="utf-8") as file:
        tips = json.load(file)

    return render_template("lerntipps.html", tips=tips)

@main_bp.route("/about")
def about():
    """
    About Us route: Displays information about Kanti Koala.

    Returns:
        str: Rendered HTML template ('about.html').
    """
    return render_template("about.html")