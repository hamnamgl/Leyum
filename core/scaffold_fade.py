import json
from datetime import datetime
from pathlib import Path

STORAGE_PATH = Path("storage/progress")

HELP_LEVELS = {
    1: 0.80,
    2: 0.80,
    3: 0.50,
    4: 0.50,
    5: 0.30,
    6: 0.10,
}


def load_progress(student_name):
    file = STORAGE_PATH / f"{student_name}.json"
    if file.exists():
        with open(file, "r") as f:
            return json.load(f)
    return {
        "first_session": datetime.now().strftime("%Y-%m-%d"),
        "current_week": 1,
        "independence_score": 0,
    }


def save_progress(student_name, progress):
    STORAGE_PATH.mkdir(parents=True, exist_ok=True)
    file = STORAGE_PATH / f"{student_name}.json"
    with open(file, "w") as f:
        json.dump(progress, f, indent=2)


def get_current_week(student_name):
    progress = load_progress(student_name)
    first = datetime.strptime(progress["first_session"], "%Y-%m-%d")
    today = datetime.now()
    days_passed = (today - first).days
    week = (days_passed // 7) + 1
    return min(week, 6)


def get_help_level(student_name):
    week = get_current_week(student_name)
    return HELP_LEVELS.get(week, 0.10)


def get_help_instructions(student_name):
    level = get_help_level(student_name)
    week = get_current_week(student_name)

    if level >= 0.80:
        return "Give full hints. Full step by step guidance. Be very supportive. Multiple attempts encouraged."
    elif level >= 0.50:
        return "Give partial hints only. Encourage student to attempt alone first before helping."
    elif level >= 0.30:
        return "Minimal hints. Ask student to try fully alone first. Only help if completely stuck."
    else:
        return "Almost no help. One word nudge maximum. Student should be nearly independent now."
