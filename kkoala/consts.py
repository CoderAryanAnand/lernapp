from datetime import time as dtime
from zoneinfo import ZoneInfo

DAY_START = dtime(8, 0)
FROM_EMAIL = "KantiKoala <noreply@kantikoala.app>"
DEFAULT_SETTINGS = {
    "learn_on_saturday": False,
    "learn_on_sunday": False,
    "preferred_learning_time": "18:00",
    "study_block_color": "#0000FF",
    "priority_settings": {
        1: {
            "color": "#770000",
            # "days_to_learn": 14,
            "max_hours_per_day": 2.0,
            "total_hours_to_learn": 14.0,
        },
        2: {
            "color": "#ca8300",
            # "days_to_learn": 7,
            "max_hours_per_day": 1.5,
            "total_hours_to_learn": 7.0,
        },
        3: {
            "color": "#097200",
            # "days_to_learn": 4,
            "max_hours_per_day": 1.0,
            "total_hours_to_learn": 4.0,
        },
    },
    "time_zone": ZoneInfo("Europe/Zurich"),
}
