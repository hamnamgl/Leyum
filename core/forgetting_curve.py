import json
from datetime import datetime, timedelta
from pathlib import Path

STORAGE_PATH = Path("storage/schedules")

REVIEW_DAYS = [1, 2, 5, 12, 30]
MISCONCEPTION_MULTIPLIER = 1.5


def load_schedule(student_name):
    file = STORAGE_PATH / f"{student_name}.json"
    if file.exists():
        with open(file, "r") as f:
            return json.load(f)
    return {}


def save_schedule(student_name, schedule):
    STORAGE_PATH.mkdir(parents=True, exist_ok=True)
    file = STORAGE_PATH / f"{student_name}.json"
    with open(file, "w") as f:
        json.dump(schedule, f, indent=2)


def mark_learned(student_name, topic, had_misconception=False):
    schedule = load_schedule(student_name)

    today = datetime.now()
    days = REVIEW_DAYS.copy()

    if had_misconception:
        days = [max(1, int(d / MISCONCEPTION_MULTIPLIER)) for d in days]

    review_dates = [(today + timedelta(days=d)).strftime("%Y-%m-%d") for d in days]

    schedule[topic] = {
        "learned_on": today.strftime("%Y-%m-%d"),
        "had_misconception": had_misconception,
        "review_dates": review_dates,
        "reviews_done": [],
    }

    save_schedule(student_name, schedule)


def get_due_reviews(student_name):
    schedule = load_schedule(student_name)
    today = datetime.now().strftime("%Y-%m-%d")
    due = []

    for topic, data in schedule.items():
        if today in data["review_dates"] and today not in data["reviews_done"]:
            due.append(topic)

    return due


def mark_reviewed(student_name, topic):
    schedule = load_schedule(student_name)
    today = datetime.now().strftime("%Y-%m-%d")

    if topic in schedule:
        if today not in schedule[topic]["reviews_done"]:
            schedule[topic]["reviews_done"].append(today)

    save_schedule(student_name, schedule)
