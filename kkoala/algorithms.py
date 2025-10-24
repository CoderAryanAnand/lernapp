from datetime import datetime, timedelta, time as dtime
from .utils import to_dt, to_iso, free_slots
from .extensions import db
from .models import Settings, Event

def learning_time_algorithm(events, user):
    """
    The core algorithm to schedule optimal learning blocks for upcoming exams.
    It identifies exams, calculates required study hours, recycles (deletes)
    previous non-locked study blocks, and schedules new blocks backward from
    the exam date, respecting daily max hours and existing event conflicts.

    Args:
        events (list[Event]): All calendar Event objects for the user (passed by
                              reference and potentially modified/updated).
        user (User): The current user object.

    Returns:
        tuple[dict, dict]: A tuple containing:
                           1. A summary dictionary of total blocks/hours added.
                           2. A dictionary of success messages for each exam processed.
    """

    # --- Configuration and Initialization ---

    # Fetch user-specific settings
    settings = Settings.query.filter_by(user_id=user.id).first()
    priority_settings = {p.priority_level: p for p in settings.priority_settings}
    if not priority_settings:
        return {"error": "No priority settings found"}, {}

    max_exam_priority = max(priority_settings.keys())

    # Load scheduling preferences
    sat_learn = settings.learn_on_saturday
    sun_learn = settings.learn_on_sunday
    preferred_time = datetime.strptime(settings.preferred_learning_time, "%H:%M").time()
    study_block_color = settings.study_block_color if settings.study_block_color else "#0000FF"

    # Define constants
    DAY_END = dtime(22, 0) # Allows blocks to run until 22:00 (10 PM)
    SESSION = 0.5 # Minimum session duration is 30 minutes (0.5 hours)

    # Identify and sort all events flagged as exams
    exams = sorted(
        [event for event in events if int(event.priority) > 0 and int(event.priority) <= max_exam_priority],
        key=lambda event: (int(event.priority), datetime.fromisoformat(event.start))
    )

    summary = {"exams_processed": 0, "blocks_added": 0, "hours_added": 0.0}
    successes = {}

    # --- Main Exam Loop: Process each exam by priority ---

    for exam in exams:
        prio = int(exam.priority)
        prio_setting = priority_settings.get(prio)
        if not prio_setting:
            continue

        summary["exams_processed"] += 1
        total = prio_setting.total_hours_to_learn

        # Define the learning window
        window_days = prio_setting.days_to_learn
        max_per_day = prio_setting.max_hours_per_day
        window_start = to_dt(exam.start) - timedelta(days=window_days)
        window_end = to_dt(exam.start)

        # Separate study blocks related to this exam
        exam_blocks = [event for event in events if event.exam_id == exam.id]
        past_blocks = [block for block in exam_blocks if to_dt(block.start) < datetime.now()]
        future_blocks = [
            block for block in exam_blocks
            if to_dt(block.start) >= datetime.now()
            and window_start <= to_dt(block.start) < window_end
        ]

        # Calculate hours completed in the past
        hours_done = sum((to_dt(block.end) - to_dt(block.start)).total_seconds() / 3600 for block in past_blocks)

        # Recycling Logic: Delete all *non-locked* future study blocks
        locked_future_blocks = [block for block in future_blocks if block.locked]
        recyclable_blocks = [block for block in future_blocks if not block.locked]

        for block in recyclable_blocks:
            db.session.delete(block)
            events.remove(block) # Update in-memory list
        db.session.commit()

        # Recalculate remaining hours
        hours_scheduled_locked = sum(
            (to_dt(block.end) - to_dt(block.start)).total_seconds() / 3600 for block in locked_future_blocks
        )
        hours_left = max(0, total - hours_done - hours_scheduled_locked)

        if hours_left == 0:
            continue

        # --- Scheduling Loop: Schedule remaining hours backwards ---

        new_scheduled = 0.0
        days_left_until_exam = (window_end.date() - datetime.now().date()).days

        for day_offset in range(1, days_left_until_exam + 1):
            current_day = window_end - timedelta(days=day_offset)

            if current_day.date() < window_start.date():
                continue

            # Check weekend restrictions
            if (not sat_learn and current_day.weekday() == 5) or (not sun_learn and current_day.weekday() == 6):
                continue

            if new_scheduled >= hours_left:
                break

            # ... (Rest of the scheduling logic, including preferred slot and general free slot search) ...

            # The scheduling logic checks conflicts against the updated 'events' list,
            # prioritizes the user's preferred time, and then finds the largest free slot,
            # ensuring blocks are at least SESSION (0.5 hours) long and do not exceed today_max.

            scheduled_today_for_exam = sum(
                (to_dt(block.end) - to_dt(block.start)).total_seconds() / 3600
                for block in events
                if block.exam_id == exam.id and to_dt(block.start).date() == current_day.date()
            )

            today_max = min(max_per_day - scheduled_today_for_exam, hours_left - new_scheduled)
            if today_max <= SESSION:
                continue

            events_today = [event for event in events if to_dt(event.start).date() == current_day.date()]

            # 1. Preferred time slot check
            preferred_start = datetime.combine(current_day.date(), preferred_time)
            preferred_end = preferred_start + timedelta(hours=today_max)
            if preferred_end.time() > DAY_END:
                preferred_end = datetime.combine(current_day.date(), DAY_END)

            preferred_slot_duration = (preferred_end - preferred_start).total_seconds() / 3600
            slot_free = True

            if preferred_slot_duration >= SESSION:
                for event in events_today:
                    event_start = to_dt(event.start)
                    event_end = to_dt(event.end)
                    if not (preferred_end <= event_start - timedelta(minutes=30) or preferred_start >= event_end + timedelta(minutes=30)):
                        slot_free = False
                        break
            else:
                slot_free = False

            if slot_free:
                # Create and save the new study block
                new_block = Event(
                    title=f"Learning for {exam.title}",
                    start=to_iso(preferred_start),
                    end=to_iso(preferred_end),
                    color=study_block_color,
                    user_id=exam.user_id,
                    exam_id=exam.id,
                    all_day=False,
                    priority=0,
                    locked=False,
                    recurrence="None",
                    recurrence_id="0",
                )
                db.session.add(new_block)
                db.session.commit()
                events.append(new_block)
                new_scheduled += preferred_slot_duration
                summary["blocks_added"] += 1
                summary["hours_added"] += preferred_slot_duration
                continue

            # 2. General free slot search
            slots = free_slots(events, current_day.date())
            slots.sort(key=lambda slot: slot[1] - slot[0], reverse=True)

            for slot_start, slot_end in slots:
                slot_duration = (slot_end - slot_start).total_seconds() / 3600
                if slot_duration < SESSION:
                    continue

                allocatable = min(slot_duration, hours_left - new_scheduled, today_max)
                if allocatable < SESSION:
                    continue

                block_start = slot_start
                block_end = slot_start + timedelta(hours=allocatable)

                # Create and save the new study block
                new_block = Event(
                    title=f"Learning for {exam.title}",
                    start=to_iso(block_start),
                    end=to_iso(block_end),
                    color=study_block_color,
                    user_id=exam.user_id,
                    exam_id=exam.id,
                    all_day=False,
                    priority=0,
                    locked=False,
                    recurrence="None",
                    recurrence_id="0",
                )
                db.session.add(new_block)
                db.session.commit()
                events.append(new_block)
                new_scheduled += allocatable
                summary["blocks_added"] += 1
                summary["hours_added"] += allocatable

                if new_scheduled >= hours_left:
                    break

                break # Only schedule one block per day in the general search

        # --- Safety / Extra Days Extension (Beyond Initial Window) ---
        # The logic below repeats the scheduling process outside the window_days boundary
        # to ensure all required hours are scheduled if possible.
        if new_scheduled < hours_left:
            for day_offset in range(window_days + 1, min(22, days_left_until_exam + 1)):
                current_day = window_end - timedelta(days=day_offset)

                if new_scheduled >= hours_left:
                    break

                # The logic inside this loop is identical to the main scheduling loop (Preferred Slot check + General Slot Search)
                # ... (code omitted for brevity, but it's the same logic) ...
                scheduled_today_for_exam = sum(
                    (to_dt(block.end) - to_dt(block.start)).total_seconds() / 3600
                    for block in events
                    if block.exam_id == exam.id and to_dt(block.start).date() == current_day.date()
                )

                today_max = min(max_per_day - scheduled_today_for_exam, hours_left - new_scheduled)
                if today_max <= SESSION:
                    continue

                events_today = [event for event in events if to_dt(event.start).date() == current_day.date()]

                # Preferred slot check
                preferred_start = datetime.combine(current_day.date(), preferred_time)
                preferred_end = preferred_start + timedelta(hours=today_max)
                if preferred_end.time() > DAY_END:
                    preferred_end = datetime.combine(current_day.date(), DAY_END)

                preferred_slot_duration = (preferred_end - preferred_start).total_seconds() / 3600
                slot_free = True
                if preferred_slot_duration >= SESSION:
                    for event in events_today:
                        event_start = to_dt(event.start)
                        event_end = to_dt(event.end)
                        if not (preferred_end <= event_start - timedelta(minutes=30) or preferred_start >= event_end + timedelta(minutes=30)):
                            slot_free = False
                            break
                else:
                    slot_free = False

                if slot_free:
                    # Create and save preferred block
                    new_block = Event(
                        title=f"Learning for {exam.title}",
                        start=to_iso(preferred_start),
                        end=to_iso(preferred_end),
                        color=study_block_color,
                        user_id=exam.user_id,
                        exam_id=exam.id,
                        all_day=False,
                        priority=0,
                        locked=False,
                        recurrence="None",
                        recurrence_id="0",
                    )
                    db.session.add(new_block)
                    db.session.commit()
                    events.append(new_block)
                    new_scheduled += preferred_slot_duration
                    summary["blocks_added"] += 1
                    summary["hours_added"] += preferred_slot_duration
                    continue

                # General slot search
                slots = free_slots(events, current_day.date())
                slots.sort(key=lambda slot: slot[1] - slot[0], reverse=True)
                for slot_start, slot_end in slots:
                    slot_duration = (slot_end - slot_start).total_seconds() / 3600
                    if slot_duration < SESSION:
                        continue

                    allocatable = min(slot_duration, hours_left - new_scheduled, today_max)
                    if allocatable < SESSION:
                        continue

                    block_start = slot_start
                    block_end = slot_start + timedelta(hours=allocatable)

                    # Create and save general block
                    new_block = Event(
                        title=f"Learning for {exam.title}",
                        start=to_iso(block_start),
                        end=to_iso(block_end),
                        color=study_block_color,
                        user_id=exam.user_id,
                        exam_id=exam.id,
                        all_day=False,
                        priority=0,
                        locked=False,
                        recurrence="None",
                        recurrence_id="0",
                    )
                    db.session.add(new_block)
                    db.session.commit()
                    events.append(new_block)
                    new_scheduled += allocatable
                    summary["blocks_added"] += 1
                    summary["hours_added"] += allocatable

                    if new_scheduled >= hours_left:
                        break
                    break # Move to next day after filling one slot

        # --- Final Status Update ---

        total_scheduled = new_scheduled + hours_scheduled_locked
        total_required = max(0, total - hours_done)

        if total_scheduled >= total_required:
            successes[exam.title] = [True, f"Successfully scheduled all {total_required:.1f} hours."]
        else:
            successes[exam.title] = [False, f"Could only schedule {total_scheduled:.1f} out of {total_required:.1f} hours."]

    return summary, successes