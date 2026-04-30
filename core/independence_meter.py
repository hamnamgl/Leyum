import json
from datetime import datetime
from pathlib import Path

STORAGE_PATH = Path("storage/progress")


def load_progress(student_name):
    file = STORAGE_PATH / f"{student_name}.json"
    if file.exists():
        with open(file, "r") as f:
            return json.load(f)
    return {
        "first_session": datetime.now().strftime("%Y-%m-%d"),
        "independence_score": 0,
        "total_questions": 0,
        "correct_first_attempt": 0,
        "history": [],
    }


def save_progress(student_name, progress):
    STORAGE_PATH.mkdir(parents=True, exist_ok=True)
    file = STORAGE_PATH / f"{student_name}.json"
    with open(file, "w") as f:
        json.dump(progress, f, indent=2)


def update_score(student_name, was_correct, attempts_needed):
    progress = load_progress(student_name)

    progress["total_questions"] += 1

    if was_correct and attempts_needed == 1:
        progress["correct_first_attempt"] += 1

    if progress["total_questions"] > 0:
        raw_score = (progress["correct_first_attempt"] / progress["total_questions"]) * 100
        progress["independence_score"] = round(raw_score, 1)

    progress["history"].append(
        {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "correct": was_correct,
            "attempts": attempts_needed,
        }
    )

    save_progress(student_name, progress)


def get_score(student_name):
    progress = load_progress(student_name)
    return progress["independence_score"]


def get_score_label(student_name):
    score = get_score(student_name)

    if score >= 80:
        return "🌟 Almost Independent!"
    elif score >= 60:
        return "💪 Getting Stronger!"
    elif score >= 40:
        return "📈 Making Progress!"
    elif score >= 20:
        return "🌱 Just Starting!"
    else:
        return "🤝 Learning Together!"
