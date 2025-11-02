from .extensions import db


class User(db.Model):
    """
    SQLAlchemy model for storing user authentication details.

    Attributes:
        id (int): Primary key.
        username (str): Unique username.
        password (str): Hashed password.
        email (str): Unique email address.
        events (relationship): One-to-many relationship with Event model.
        semesters (relationship): One-to-many relationship with Semester model.
        settings (relationship): One-to-many relationship with Settings model.
    """

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)  # Hashed password
    email = db.Column(db.String(100), unique=True, nullable=False)

    # Relationships (enables easy retrieval of user data and cascade deletion)
    events = db.relationship(
        "Event", backref="user", lazy=True, cascade="all, delete-orphan"
    )
    semesters = db.relationship(
        "Semester", backref="user", lazy=True, cascade="all, delete-orphan"
    )
    settings = db.relationship(
        "Settings", backref="user", lazy=True, cascade="all, delete-orphan"
    )


class Settings(db.Model):
    """
    SQLAlchemy model for storing user-specific scheduling preferences.

    Attributes:
        id (int): Primary key.
        user_id (int): Foreign key to the User model.
        learn_on_saturday (bool): Flag for weekend study preference.
        learn_on_sunday (bool): Flag for weekend study preference.
        preferred_learning_time (str): User's preferred time of day for study blocks (HH:MM).
        study_block_color (str): Hex code for algorithm-generated study blocks.
        priority_settings (relationship): One-to-many relationship with PrioritySetting model.
    """

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    learn_on_saturday = db.Column(db.Boolean, default=False)
    learn_on_sunday = db.Column(db.Boolean, default=False)
    preferred_learning_time = db.Column(db.String(20), default="18:00")
    study_block_color = db.Column(db.String(7), default="#0000FF")

    # Relationship to detailed priority rules
    priority_settings = db.relationship(
        "PrioritySetting", backref="settings", lazy=True, cascade="all, delete-orphan"
    )


class PrioritySetting(db.Model):
    """
    SQLAlchemy model for storing user-specific priority rules (e.g., P1, P2, P3)
    used by the learning time algorithm.

    Attributes:
        id (int): Primary key.
        settings_id (int): Foreign key to the Settings model.
        priority_level (int): The numerical priority level (e.g., 1, 2, 3).
        color (str): Hex color code for exams of this priority.
        days_to_learn (int): The size of the scheduling window before the exam.
        max_hours_per_day (float): Maximum study time allowed per day for this priority.
        total_hours_to_learn (float): Total required study time for this priority's exams.
    """

    id = db.Column(db.Integer, primary_key=True)
    settings_id = db.Column(db.Integer, db.ForeignKey("settings.id"), nullable=False)
    priority_level = db.Column(db.Integer, nullable=False)  # e.g., 1, 2, 3
    color = db.Column(
        db.String(7), nullable=False
    )  # Color to display exams of this priority
    days_to_learn = db.Column(
        db.Integer, nullable=False
    )  # Scheduling window size before exam
    max_hours_per_day = db.Column(
        db.Float, nullable=False
    )  # Max study time per day for this priority
    total_hours_to_learn = db.Column(
        db.Float, nullable=False
    )  # Total required study time


class Event(db.Model):
    """
    SQLAlchemy model for storing user calendar entries (classes, exams, study blocks).

    Attributes:
        id (int): Primary key.
        user_id (int): Foreign key to the User model.
        title (str): Event title.
        start (str): Start datetime in ISO format.
        end (str): End datetime in ISO format.
        color (str): Hex color code for the event display.
        priority (int): 0 for study blocks; >0 for user events/exams.
        recurrence (str): Recurrence pattern ('daily', 'weekly', 'monthly', 'None').
        recurrence_id (str): Unique ID linking recurring events.
        all_day (bool): True if an all-day event.
        locked (bool): True if user-created (will not be deleted by the algorithm).
        exam_id (int): Links a study block (priority=0) to its parent exam.
    """

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id", onupdate="CASCADE"), nullable=False
    )
    title = db.Column(db.String(500), nullable=False)
    start = db.Column(db.String(50), nullable=False)  # ISO format datetime
    end = db.Column(db.String(50), nullable=True)  # ISO format datetime
    color = db.Column(db.String(7), nullable=False)
    priority = db.Column(
        db.Integer, nullable=False
    )  # 0 for algorithm-generated study blocks; >0 for user events/exams
    recurrence = db.Column(
        db.String(50), nullable=True
    )  # e.g., 'daily', 'weekly', 'monthly', 'None'
    recurrence_id = db.Column(
        db.String(50), nullable=True
    )  # Unique ID for linked recurring events
    all_day = db.Column(db.Boolean, nullable=False, default=False)

    # Fields specifically for the learning algorithm
    locked = db.Column(
        db.Boolean, default=True
    )  # True: user-created, False: algorithm-created (can be recycled)
    exam_id = db.Column(
        db.Integer, nullable=True
    )  # Links a study block (priority=0) back to its parent exam


class Semester(db.Model):
    """
    SQLAlchemy model for storing academic semesters (part of the Grades feature).

    Attributes:
        id (int): Primary key.
        user_id (int): Foreign key to the User model.
        name (str): Semester name (e.g., 'Fall 2023').
        subjects (relationship): One-to-many relationship with Subject model.
    """

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)

    # Relationship to subjects with cascade delete
    subjects = db.relationship(
        "Subject", backref="semester", lazy=True, cascade="all, delete-orphan"
    )


class Subject(db.Model):
    """
    SQLAlchemy model for storing subjects within a semester.

    Attributes:
        id (int): Primary key.
        semester_id (int): Foreign key to the Semester model.
        name (str): Subject name (e.g., 'Calculus I').
        grades (relationship): One-to-many relationship with Grade model.
    """

    id = db.Column(db.Integer, primary_key=True)
    semester_id = db.Column(db.Integer, db.ForeignKey("semester.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    counts_towards_average = db.Column(db.Boolean, nullable=False, default=True)

    # Relationship to grades with cascade delete
    grades = db.relationship(
        "Grade", backref="subject", lazy=True, cascade="all, delete-orphan"
    )


class Grade(db.Model):
    """
    SQLAlchemy model for storing individual grades for subjects (Noten).

    Attributes:
        id (int): Primary key.
        subject_id (int): Foreign key to the Subject model.
        name (str): Grade name (e.g., 'Midterm Exam').
        value (float): The grade score/value.
        weight (float): The weight/percentage of the grade.
        counts (bool): Whether the grade is included in the final calculation.
    """

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    value = db.Column(db.Float, nullable=False)
    weight = db.Column(db.Float, nullable=False)
    counts = db.Column(db.Boolean, nullable=False, default=True)
