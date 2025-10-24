from flask import Blueprint, session, current_app, jsonify, request
from datetime import datetime
import os

from ..models import Subject, Grade, User, Semester
from ..utils import login_required, csrf_protect
from ..extensions import db

grades_bp = Blueprint("grades", __name__, template_folder="../templates", static_folder="../static")

@grades_bp.route("/", methods=["GET"])
@login_required
def get_noten():
    """
    API endpoint to get all semesters, subjects, and grades for the user.

    Returns:
        JSON: A nested data structure representing the user's academic records.
    """
    user = User.query.filter_by(username=session["username"]).first()
    semesters = Semester.query.filter_by(user_id=user.id).all()
    data = []
    # Structure the database objects into a nested dictionary/list for JSON output
    for sem in semesters:
        sem_data = {"id": sem.id, "name": sem.name, "subjects": []}
        for subj in sem.subjects:
            subj_data = {"id": subj.id, "name": subj.name, "counts_towards_average": subj.counts_towards_average, "grades": []}
            for grade in subj.grades:
                subj_data["grades"].append(
                    {
                        "id": grade.id,
                        "name": grade.name,
                        "value": grade.value,
                        "weight": grade.weight,
                        "counts": grade.counts,
                    }
                )
            sem_data["subjects"].append(subj_data)
        data.append(sem_data)
    return jsonify(data)


@grades_bp.route("/", methods=["POST"])
@csrf_protect
@login_required
def save_noten():
    """
    API endpoint to save all semesters, subjects, and grades for the user.

    This implements a destructive save: all existing academic records (Semester,
    Subject, Grade) are deleted and then recreated from the incoming JSON data.

    Returns:
        JSON: A status message confirming the successful save.
    """
    data = request.json
    user = User.query.filter_by(username=session["username"]).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Remove all existing semesters, subjects, and grades for this user
    semesters = Semester.query.filter_by(user_id=user.id).all()
    for sem in semesters:
        db.session.delete(sem)
    db.session.commit()

    # Re-create all semesters, subjects, and grades from the posted data
    for sem in data:
        semester = Semester(user_id=user.id, name=sem["name"])
        db.session.add(semester)
        db.session.flush() # Flush to get semester.id before adding subjects

        for subj in sem.get("subjects", []):
            subject = Subject(semester_id=semester.id, name=subj["name"], counts_towards_average=subj.get("counts_towards_average", True))
            db.session.add(subject)
            db.session.flush() # Flush to get subject.id before adding grades

            for grade in subj.get("grades", []):
                db.session.add(
                    Grade(
                        subject_id=subject.id,
                        name=grade["name"],
                        value=grade["value"],
                        weight=grade["weight"],
                        counts=grade["counts"],
                    )
                )

    db.session.commit()
    return jsonify({"status": "success"})