# Import standard libraries for date and time handling
from datetime import datetime, timedelta, time as dtime, timezone
from zoneinfo import ZoneInfo

# Import utility functions and extensions from the application
from .utils import to_dt, to_iso, free_slots
from .extensions import db
from .models import Settings, Event


def learning_time_algorithm(events, user):
    """
    Core algorithm to schedule optimal learning blocks for upcoming exams.

    This function:
    - Reads user settings and priorities.
    - Removes previously generated (non-locked) learning blocks.
    - Schedules new learning blocks for each upcoming exam, respecting user preferences and constraints.
    - Commits all changes in a single database transaction.

    Args:
        events (list): List of all Event objects for the user (including exams and existing learning blocks).
        user (User): The user object for whom the scheduling is performed.

    Returns:
        tuple: (summary dict, successes dict)
            summary: Statistics about the scheduling process.
            successes: Per-exam status (success/failure and message).
    """

    # --- Configuration and Initialization ---
    # Load user settings from the database
    settings = Settings.query.filter_by(user_id=user.id).first()
    if not settings:
        # No settings found for user; return empty results
        return {}, {}

    # Build a dictionary of priority settings for quick lookup
    priority_settings = {p.priority_level: p for p in settings.priority_settings}
    max_exam_priority = max(priority_settings.keys()) if priority_settings else 0

    # Prepare a settings dictionary for easy access
    settings_dict = {
        "sat_learn": settings.learn_on_saturday,
        "sun_learn": settings.learn_on_sunday,
        "preferred_time": datetime.strptime(
            settings.preferred_learning_time, "%H:%M"
        ).time(),
        "study_block_color": settings.study_block_color or "#0000FF",
        "DAY_END": dtime(22, 0),
        "SESSION": 0.5,  # Minimum session length in hours
        "user_tz": ZoneInfo("Europe/Zurich"),  # User's timezone
    }

    # Filter out past exams and sort remaining exams by priority and date
    now = datetime.now(timezone.utc)
    exams = sorted(
        [
            e
            for e in events
            if int(e.priority) > 0 
            and int(e.priority) <= max_exam_priority
            and to_dt(e.start) > now  # Only include future exams
        ],
        key=lambda e: (int(e.priority), to_dt(e.start)),
    )

    # --- GLOBAL CLEANUP PHASE ---
    # Find all non-locked learning blocks created by the algorithm (to be replaced)
    all_recyclable_blocks = [
        event
        for event in events
        if not event.locked and event.title.startswith("Learning for")
    ]

    # Stage all recyclable blocks for deletion
    if all_recyclable_blocks:
        for block in all_recyclable_blocks:
            db.session.delete(block)

    # Prepare a clean list of events for scheduling (locked/user-created only)
    events_for_scheduling = [e for e in events if e not in all_recyclable_blocks]

    summary = {"exams_processed": 0, "blocks_added": 0, "hours_added": 0.0}
    successes = {}

    # --- Main Exam Loop ---
    for exam in exams:
        prio = int(exam.priority)
        prio_setting = priority_settings.get(prio)
        if not prio_setting:
            continue  # Skip if no settings for this priority

        summary["exams_processed"] += 1
        total = prio_setting.total_hours_to_learn
        max_per_day = prio_setting.max_hours_per_day
        window_end = to_dt(exam.start)

        # Calculate hours already done from past or locked blocks
        exam_blocks = [e for e in events_for_scheduling if e.exam_id == exam.id]
        past_blocks = [
            b for b in exam_blocks if to_dt(b.start) < now
        ]
        locked_future_blocks = [
            b
            for b in exam_blocks
            if to_dt(b.start) >= now and b.locked
        ]

        hours_done = sum(
            (to_dt(b.end) - to_dt(b.start)).total_seconds() / 3600 for b in past_blocks
        )
        hours_scheduled_locked = sum(
            (to_dt(b.end) - to_dt(b.start)).total_seconds() / 3600
            for b in locked_future_blocks
        )
        hours_left = max(0, total - hours_done - hours_scheduled_locked)

        if hours_left <= 0:
            # All required hours are already scheduled
            successes[exam.title] = [True, f"All required hours are scheduled."]
            continue

        # --- Scheduling Loop ---
        new_scheduled = 0.0
        days_left_until_exam = (window_end.date() - datetime.now().date()).days

        # Try to schedule learning blocks on each day before the exam
        for day_offset in range(1, min(22, days_left_until_exam + 1)):
            if new_scheduled >= hours_left:
                break
            current_day = window_end - timedelta(days=day_offset)

            # Skip if current_day is in the past
            if current_day.date() < datetime.now().date():
                continue

            # --- Day Pre-Checks ---
            # Skip if the day is blocked by an all-day event
            is_day_blocked = any(
                e.all_day
                and to_dt(e.start).date()
                <= current_day.date()
                <= (
                    to_dt(e.end).date() - timedelta(days=1)
                    if e.end
                    else to_dt(e.start).date()
                )
                for e in events_for_scheduling
            )
            if is_day_blocked:
                continue
            # Skip if learning on this day is not allowed by user settings
            if (not settings_dict["sat_learn"] and current_day.weekday() == 5) or (
                not settings_dict["sun_learn"] and current_day.weekday() == 6
            ):
                continue

            # Calculate how many hours are already scheduled for this exam on this day
            scheduled_today_for_exam = sum(
                (to_dt(b.end) - to_dt(b.start)).total_seconds() / 3600
                for b in events_for_scheduling
                if b.exam_id == exam.id and to_dt(b.start).date() == current_day.date()
            )
            today_max = min(
                max_per_day - scheduled_today_for_exam, hours_left - new_scheduled
            )

            if today_max < settings_dict["SESSION"]:
                continue

            # --- Preferred Slot Check ---
            # Try to schedule at the user's preferred learning time
            naive_preferred_start = datetime.combine(
                current_day.date(), settings_dict["preferred_time"]
            )
            # Localize to user timezone, then convert to UTC
            local_preferred_start = naive_preferred_start.replace(tzinfo=settings_dict["user_tz"])
            preferred_start = local_preferred_start.astimezone(timezone.utc)
            preferred_end = preferred_start + timedelta(hours=today_max)

            naive_day_end = datetime.combine(
                current_day.date(), settings_dict["DAY_END"]
            )
            local_day_end = naive_day_end.replace(tzinfo=settings_dict["user_tz"])
            day_end_utc = local_day_end.astimezone(timezone.utc)

            if preferred_end > day_end_utc:
                preferred_end = day_end_utc

            preferred_slot_duration = (
                preferred_end - preferred_start
            ).total_seconds() / 3600
            is_preferred_slot_free = True
            if preferred_slot_duration >= settings_dict["SESSION"]:
                for event in events_for_scheduling:
                    if to_dt(event.start).date() != current_day.date():
                        continue
                    
                    # Handle events without end times
                    event_start = to_dt(event.start)
                    event_end = to_dt(event.end) if event.end else event_start
                    
                    # Check for overlap (with 30 min buffer)
                    if not (
                        preferred_end <= event_start - timedelta(minutes=30)
                        or preferred_start >= event_end + timedelta(minutes=30)
                    ):
                        is_preferred_slot_free = False
                        break
            else:
                is_preferred_slot_free = False

            if is_preferred_slot_free:
                # Schedule a new learning block at the preferred time
                new_block = Event(
                    title=f"Learning for {exam.title}",
                    start=to_iso(preferred_start),  # UTC
                    end=to_iso(preferred_end),      # UTC
                    color=settings_dict["study_block_color"],
                    user_id=exam.user_id,
                    exam_id=exam.id,
                    priority=0,
                    locked=False,
                    recurrence="None",
                    recurrence_id="0",
                    all_day=False,
                )
                db.session.add(new_block)  # Stage for addition
                events_for_scheduling.append(new_block)
                new_scheduled += preferred_slot_duration
                summary["blocks_added"] += 1
                summary["hours_added"] += preferred_slot_duration
                continue

            # --- General Free Slot Search ---
            # If preferred slot is not available, find any free slot that fits
            slots = free_slots(events_for_scheduling, current_day.date())
            slots.sort(key=lambda s: s[1] - s[0], reverse=True)
            if slots:
                slot_start, slot_end = slots[0]
                slot_duration = (slot_end - slot_start).total_seconds() / 3600
                allocatable = min(slot_duration, hours_left - new_scheduled, today_max)
                if allocatable >= settings_dict["SESSION"]:
                    block_end = slot_start + timedelta(hours=allocatable)
                    new_block = Event(
                        title=f"Learning for {exam.title}",
                        start=to_iso(slot_start),   # UTC
                        end=to_iso(block_end),      # UTC
                        color=settings_dict["study_block_color"],
                        user_id=exam.user_id,
                        exam_id=exam.id,
                        priority=0,
                        locked=False,
                        recurrence="None",
                        recurrence_id="0",
                        all_day=False,
                    )
                    db.session.add(new_block)  # Stage for addition
                    events_for_scheduling.append(new_block)
                    new_scheduled += allocatable
                    summary["blocks_added"] += 1
                    summary["hours_added"] += allocatable

        # --- Final Status Update ---
        total_scheduled = new_scheduled + hours_scheduled_locked
        total_required = max(0, total - hours_done)
        if total_scheduled >= total_required:
            successes[exam.title] = [
                True,
                f"Successfully scheduled all {total_required:.1f} hours.",
            ]
        else:
            successes[exam.title] = [
                False,
                f"Could only schedule {total_scheduled:.1f} out of {total_required:.1f} hours.",
            ]

    # --- FINAL COMMIT ---
    # Commit all staged deletions and additions in a single transaction
    db.session.commit()

    return summary, successes
