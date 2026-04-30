import json
from pathlib import Path

STORAGE_PATH = Path("storage/misconceptions")


def load_graph(student_name):
    file = STORAGE_PATH / f"{student_name}.json"
    if file.exists():
        with open(file, "r") as f:
            return json.load(f)
    return {}


def save_graph(student_name, graph):
    STORAGE_PATH.mkdir(parents=True, exist_ok=True)
    file = STORAGE_PATH / f"{student_name}.json"
    with open(file, "w") as f:
        json.dump(graph, f, indent=2)


def log_mistake(student_name, topic, student_answer, error_type, teaching_angle_used):
    graph = load_graph(student_name)

    if topic not in graph:
        graph[topic] = {
            "mistakes": [],
            "angles_tried": [],
            "mistake_count": 0,
        }

    graph[topic]["mistakes"].append(
        {
            "answer": student_answer,
            "error_type": error_type,
            "angle": teaching_angle_used,
        }
    )
    graph[topic]["mistake_count"] += 1

    if teaching_angle_used not in graph[topic]["angles_tried"]:
        graph[topic]["angles_tried"].append(teaching_angle_used)

    save_graph(student_name, graph)


def get_next_angle(student_name, topic):
    graph = load_graph(student_name)

    if topic not in graph:
        return "analogy"

    angles_tried = graph[topic]["angles_tried"]
    mistake_count = graph[topic]["mistake_count"]

    all_angles = ["analogy", "step_by_step", "real_world_story", "counter_example"]

    for angle in all_angles:
        if angle not in angles_tried:
            return angle

    return all_angles[mistake_count % len(all_angles)]
