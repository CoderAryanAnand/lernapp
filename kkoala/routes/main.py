from flask import Blueprint, render_template, session, current_app, abort
from datetime import datetime, timedelta
import os, json

from ..models import Settings, User, Semester, Event, ToDoCategory
from ..utils import login_required

main_bp = Blueprint(
    "main", __name__, template_folder="../templates", static_folder="../static"
)


@main_bp.route("/")
def index():
    """
    Home route: Handles the main landing page display.

    - Shows a daily tip (from file) for all users.
    - If logged in, displays dashboard with upcoming exams, today's events, and grade statistics.
    - If not logged in, shows login/register links and the daily tip.

    Returns:
        str: Rendered HTML template ('home.html').
    """
    # --- Daily Tip Logic (for both logged in and out) ---
    try:
        tips_file_path = os.path.join(current_app.root_path, "tips", "daily_tips.txt")
        with open(tips_file_path, "r", encoding="utf-8") as file:
            tips = file.readlines()
    except FileNotFoundError:
        tips = ["Keine Tipps verfügbar."]
    tip_of_the_day = tips[datetime.now().timetuple().tm_yday % len(tips)].strip()

    # --- Logged In Dashboard Logic ---
    if "username" in session:
        user = User.query.filter_by(username=session["username"]).first()
        if not user:
            session.clear()
            return render_template("home.html", logged_in=False, tip=tip_of_the_day)

        # --- Determine exam priorities from user settings ---
        settings = Settings.query.filter_by(user_id=user.id).first()
        exam_priorities = [1]  # Default exam priorities if no settings found

        if settings and settings.priority_settings:
            all_priorities = [p.priority_level for p in settings.priority_settings]
            if all_priorities:
                # An exam is any priority that is not the maximum (lowest) one
                lowest_priority = max(all_priorities) + 1
                exam_priorities = [p for p in all_priorities if p != lowest_priority]

        # 1. Get upcoming exams (within next 21 days)
        today = datetime.utcnow().date()
        future_date = today + timedelta(days=21)
        upcoming_exams_query = Event.query.filter(
            Event.user_id == user.id,
            Event.priority.in_(exam_priorities),
            Event.start >= today.isoformat(),
            Event.start <= future_date.isoformat()
        ).order_by(Event.start).all()

        # Convert string dates to datetime objects for the template
        upcoming_exams = []
        for exam in upcoming_exams_query:
            if isinstance(exam.start, str):
                exam.start = datetime.fromisoformat(exam.start)
            if isinstance(exam.end, str):
                exam.end = datetime.fromisoformat(exam.end)
            upcoming_exams.append(exam)

        # 2. Get today's events
        todays_events_query = Event.query.filter(
            Event.user_id == user.id,
            Event.start.like(f"{today.isoformat()}%")
        ).order_by(Event.start).all()

        todays_events = []
        for event in todays_events_query:
            if event.all_day:
                event.start = datetime.fromisoformat(event.start).date()
                if event.end:
                    event.end = datetime.fromisoformat(event.end).date()
                else:
                    event.end = event.start
            if isinstance(event.start, str):
                event.start = datetime.fromisoformat(event.start)
            if isinstance(event.end, str):
                event.end = datetime.fromisoformat(event.end)
            todays_events.append(event)

        # 3. Grade statistics for dashboard
        dashboard_stats = {
            "current_semester_name": None,
            "average": 0,
            "plus_points": 0,
            "best_subject": None,
            "worst_subject": None
        }
        current_semester = Semester.query.filter_by(user_id=user.id).order_by(Semester.id.asc()).first()

        if current_semester:
            dashboard_stats["current_semester_name"] = current_semester.name
            total_value_weight = 0
            total_weight = 0
            subject_averages = []
            total_plus_points = 0

            # Helper: round a grade to the nearest 0.5
            def round_to_half(n):
                return round(n * 2) / 2

            for subject in current_semester.subjects:
                if not subject.counts_towards_average:
                    continue
                subj_total_value_weight = 0
                subj_total_weight = 0
                for grade in subject.grades:
                    if grade.counts:
                        subj_total_value_weight += grade.value * grade.weight
                        subj_total_weight += grade.weight
                if subj_total_weight > 0:
                    subj_avg = subj_total_value_weight / subj_total_weight
                    subject_averages.append({"name": subject.name, "average": subj_avg})
                    rounded_avg = round_to_half(subj_avg)
                    if rounded_avg > 4.0:
                        total_plus_points += (rounded_avg - 4.0)
                    elif rounded_avg < 4.0:
                        total_plus_points += (rounded_avg - 4.0) * 2
                    total_value_weight += subj_avg
                    total_weight += 1

            if total_weight > 0:
                overall_avg = total_value_weight / total_weight
                dashboard_stats["average"] = round(overall_avg, 2)
                dashboard_stats["plus_points"] = round(total_plus_points, 2)

            if subject_averages:
                dashboard_stats["best_subject"] = max(subject_averages, key=lambda x: x["average"])
                dashboard_stats["worst_subject"] = min(subject_averages, key=lambda x: x["average"])

        return render_template(
            "home.html",
            username=session["username"],
            logged_in=True,
            tip=tip_of_the_day,
            upcoming_exams=upcoming_exams,
            todays_events=todays_events,
            stats=dashboard_stats,
            today=today
        )

    # --- Not logged in: show home page with tip ---
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


@main_bp.route("/hilfe")
def hilfe():
    """
    Help route: Displays the help page.

    Returns:
        str: Rendered HTML template ('hilfe.html').
    """
    return render_template("hilfe.html")


@main_bp.route("/todo")
@login_required
def todo_index(user):
    """
    To-Do List route: Displays the user's to-do categories and items.

    Returns:
        str: Rendered HTML template ('todo.html').
    """
    categories = ToDoCategory.query.filter_by(user_id=user.id).all()
    return render_template("todo.html", categories=categories)


@main_bp.route("/datenschutzerklaerung")
def datenschutzerklaerung():
    """
    Datenschutzerklärung route: Displays the privacy policy.

    Returns:
        str: Rendered HTML template ('datenschutzerklaerung.html').
    """
    return render_template("datenschutzerklaerung.html")