from .extensions import db

# -------------------------------
# User authentication and profile
# -------------------------------

class User(db.Model):
    """
    Stores user authentication and profile information.

    Attributes:
        id (int): Primary key.
        username (str): Unique username for login.
        password (str): Hashed password.
        email (str): Unique email address.
        events (relationship): All calendar events for the user.
        semesters (relationship): All semesters for the user (grades).
        settings (relationship): User's settings (one-to-one).
        todo_categories (relationship): User's to-do list categories.
    """
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)  # Hashed password
    email = db.Column(db.String(100), unique=True, nullable=False)

    # Relationships
    events = db.relationship(
        "Event", backref="user", lazy=True, cascade="all, delete-orphan"
    )
    semesters = db.relationship(
        "Semester", backref="user", lazy=True, cascade="all, delete-orphan"
    )
    settings = db.relationship(
        "Settings", backref="user", uselist=False, lazy=True, cascade="all, delete-orphan"
    )
    todo_categories = db.relationship(
        "ToDoCategory", backref="user", lazy=True, cascade="all, delete-orphan"
    )

# -------------------------------
# User settings and priorities
# -------------------------------

class Settings(db.Model):
    """
    Stores user-specific scheduling and display preferences.

    Attributes:
        id (int): Primary key.
        user_id (int): Foreign key to User.
        learn_on_saturday (bool): Allow learning on Saturday.
        learn_on_sunday (bool): Allow learning on Sunday.
        preferred_learning_time (str): Preferred start time for learning blocks (HH:MM).
        study_block_color (str): Color for algorithm-generated study blocks.
        import_color (str): Color for imported events.
        dark_mode (str): User's dark mode preference.
        priority_settings (relationship): Priority rules for learning algorithm.
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    learn_on_saturday = db.Column(db.Boolean, default=False)
    learn_on_sunday = db.Column(db.Boolean, default=False)
    preferred_learning_time = db.Column(db.String(20), default="18:00")
    study_block_color = db.Column(db.String(7), default="#0000FF")
    import_color = db.Column(db.String(7), default="#6C757D")
    dark_mode = db.Column(db.String(10), default="system")

    # Priority settings for learning algorithm
    priority_settings = db.relationship(
        "PrioritySetting", backref="settings", lazy=True, cascade="all, delete-orphan"
    )

class PrioritySetting(db.Model):
    """
    Stores user-specific rules for each exam priority level.

    Attributes:
        id (int): Primary key.
        settings_id (int): Foreign key to Settings.
        priority_level (int): Priority (e.g., 1, 2, 3).
        color (str): Color for exams of this priority.
        max_hours_per_day (float): Max learning hours per day.
        total_hours_to_learn (float): Total hours to schedule for this priority.
    """
    id = db.Column(db.Integer, primary_key=True)
    settings_id = db.Column(db.Integer, db.ForeignKey("settings.id"), nullable=False)
    priority_level = db.Column(db.Integer, nullable=False)  # e.g., 1, 2, 3
    color = db.Column(db.String(7), nullable=False)
    max_hours_per_day = db.Column(db.Float, nullable=False)
    total_hours_to_learn = db.Column(db.Float, nullable=False)

# -------------------------------
# Calendar events (agenda)
# -------------------------------

class Event(db.Model):
    """
    Stores calendar entries (classes, exams, study blocks).

    Attributes:
        id (int): Primary key.
        user_id (int): Foreign key to User.
        title (str): Event title.
        start (str): Start datetime (ISO format).
        end (str): End datetime (ISO format).
        color (str): Display color.
        priority (int): 0 for study blocks, >0 for user events/exams.
        recurrence (str): Recurrence pattern.
        recurrence_id (str): ID for recurring events.
        all_day (bool): All-day event flag.
        locked (bool): True if user-created (not deleted by algorithm).
        exam_id (int): Links a study block to its parent exam.
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id", onupdate="CASCADE"), nullable=False
    )
    title = db.Column(db.String(500), nullable=False)
    start = db.Column(db.String(50), nullable=False)  # ISO format datetime
    end = db.Column(db.String(50), nullable=True)     # ISO format datetime
    color = db.Column(db.String(7), nullable=False)
    priority = db.Column(db.Integer, nullable=False)  # 0: study block, >0: exam/event
    recurrence = db.Column(db.String(50), nullable=True)
    recurrence_id = db.Column(db.String(50), nullable=True)
    all_day = db.Column(db.Boolean, nullable=False, default=False)
    locked = db.Column(db.Boolean, default=True)      # True: user-created, False: algorithm
    exam_id = db.Column(db.Integer, nullable=True)    # Link to parent exam

# -------------------------------
# Grades (Noten) feature
# -------------------------------

class Semester(db.Model):
    """
    Stores academic semesters for the grades feature.

    Attributes:
        id (int): Primary key.
        user_id (int): Foreign key to User.
        name (str): Semester name.
        subjects (relationship): All subjects in this semester.
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)

    # Subjects in this semester
    subjects = db.relationship(
        "Subject", backref="semester", lazy=True, cascade="all, delete-orphan"
    )

class Subject(db.Model):
    """
    Stores subjects within a semester.

    Attributes:
        id (int): Primary key.
        semester_id (int): Foreign key to Semester.
        name (str): Subject name.
        counts_towards_average (bool): Whether subject counts for average.
        grades (relationship): All grades for this subject.
    """
    id = db.Column(db.Integer, primary_key=True)
    semester_id = db.Column(db.Integer, db.ForeignKey("semester.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    counts_towards_average = db.Column(db.Boolean, nullable=False, default=True)

    # Grades for this subject
    grades = db.relationship(
        "Grade", backref="subject", lazy=True, cascade="all, delete-orphan"
    )

class Grade(db.Model):
    """
    Stores individual grades for subjects.

    Attributes:
        id (int): Primary key.
        subject_id (int): Foreign key to Subject.
        name (str): Grade name (e.g., 'Midterm Exam').
        value (float): Grade value.
        weight (float): Weight of the grade.
        counts (bool): Whether grade is included in calculation.
    """
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    value = db.Column(db.Float, nullable=False)
    weight = db.Column(db.Float, nullable=False)
    counts = db.Column(db.Boolean, nullable=False, default=True)

# -------------------------------
# ToDo list feature
# -------------------------------

class ToDoCategory(db.Model):
    """
    Stores user-specific to-do list categories.

    Attributes:
        id (int): Primary key.
        user_id (int): Foreign key to User.
        name (str): Category name.
        items (relationship): All to-do items in this category.
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)

    # To-do items in this category
    items = db.relationship(
        "ToDoItem", backref="category", lazy=True, cascade="all, delete-orphan"
    )

class ToDoItem(db.Model):
    """
    Stores individual to-do list items.

    Attributes:
        id (int): Primary key.
        category_id (int): Foreign key to ToDoCategory.
        description (str): Description of the to-do item.
        completed (bool): Completion status.
    """
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("to_do_category.id"), nullable=False)
    description = db.Column(db.String(500), nullable=False)