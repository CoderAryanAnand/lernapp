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
    Replace all semesters/subjects/grades for the current user with the provided payload.
    Payload: [{ name, subjects: [{ name, counts_average, grades: [{ name, value, weight, counts }] }] }]
    """
    payload = request.get_json(silent=True)
    if not isinstance(payload, list):
        return jsonify({"error": "Invalid payload, expected a list of semesters"}), 400

    username = session.get("username")
    if not username:
        return jsonify({"error": "Unauthorized"}), 401

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Validate payload structure before touching DB
    try:
        for sem in payload:
            if not isinstance(sem, dict) or not isinstance(sem.get("name", ""), str):
                raise ValueError("Invalid semester entry")
            if "subjects" in sem and not isinstance(sem["subjects"], list):
                raise ValueError("subjects must be a list")
            for subj in sem.get("subjects", []):
                if not isinstance(subj, dict) or not isinstance(subj.get("name", ""), str):
                    raise ValueError("Invalid subject entry")
                if "grades" in subj and not isinstance(subj["grades"], list):
                    raise ValueError("grades must be a list")
                for grd in subj.get("grades", []):
                    # attempt to coerce values to check types
                    float(grd.get("value", 0))
                    float(grd.get("weight", 1.0))
    except Exception as e:
        return jsonify({"error": f"Invalid payload: {str(e)}"}), 400

    # Now perform DB replace inside a transaction; rollback on error
    try:
        # Delete existing semesters (cascade should remove subjects/grades)
        existing_semesters = Semester.query.filter_by(user_id=user.id).all()
        for s in existing_semesters:
            db.session.delete(s)
        db.session.flush()

        # Recreate from payload
        for sem in payload:
            sem_name = sem.get("name", "Unnamed Semester")
            new_sem = Semester(user_id=user.id, name=sem_name)
            db.session.add(new_sem)
            db.session.flush()  # ensure new_sem.id available for FK relations

            for subj in sem.get("subjects", []):
                subj_name = subj.get("name", "Unnamed Subject")
                counts_avg = subj.get("counts_average", True)
                new_subj = Subject(semester_id=new_sem.id, name=subj_name, counts_towards_average=bool(counts_avg))
                db.session.add(new_subj)
                db.session.flush()

                for grd in subj.get("grades", []):
                    try:
                        value = float(grd.get("value", 0))
                        weight = float(grd.get("weight", 1.0))
                    except Exception:
                        value = 0.0
                        weight = 1.0
                    new_grade = Grade(
                        subject_id=new_subj.id,
                        name=grd.get("name", ""),
                        value=value,
                        weight=weight,
                        counts=bool(grd.get("counts", True)),
                    )
                    db.session.add(new_grade)

        db.session.commit()
        return jsonify({"status": "ok"}), 201
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("Failed saving semesters")
        return jsonify({"error": "Database error saving semesters"}), 500