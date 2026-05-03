from pathlib import Path
import time

import gradio as gr
import ollama

from core.error_classifier import classify_error
from core.forgetting_curve import get_due_reviews
from core.independence_meter import get_score, get_score_label, update_score
from core.language_handler import detect_language
from core.misconception_graph import get_next_angle, log_mistake
from core.parent_report import generate_report
from core.scaffold_fade import get_current_week, get_help_instructions
from core.struggle_detector import analyze_struggle

CSS_TEXT = Path("ui/styles.css").read_text(encoding="utf-8")


def reset_session_data():
    return {
        "student_name": "",
        "topic": "",
        "history": [],
        "responses": [],
        "session_start": time.time(),
        "topics_studied": [],
        "hard_topics": [],
        "teaching_style": "analogy",
    }


session_data = reset_session_data()


def load_prompt(error_type):
    type_map = {
        1: "prompts/knowledge_gap.txt",
        2: "prompts/misconception.txt",
        3: "prompts/careless.txt",
    }
    with open(type_map[error_type], "r", encoding="utf-8") as f:
        return f.read()


def generate_response(prompt_template, student_answer, correct_answer, topic, language, help_instructions):
    filled = prompt_template.format(
        student_answer=student_answer,
        correct_answer=correct_answer,
        topic=topic,
        language=language,
    )
    full_prompt = filled + f"\n\nTeaching guidance: {help_instructions}"

    response = ollama.chat(
        model="gemma3:4b",
        messages=[{"role": "user", "content": full_prompt}],
    )
    return response["message"]["content"].strip()


def language_flag(language):
    flags = {
        "urdu": "PK",
        "english": "EN",
        "arabic": "AR",
        "hindi": "IN",
    }
    return flags.get(language.lower(), "AUTO")


def render_review_alert(student_name):
    due = get_due_reviews(student_name) if student_name else []
    if due:
        return (
            "<div class='review-banner urgent'>"
            "<strong>Review Due Today</strong><br>"
            f"{', '.join(due)}"
            "</div>"
        )
    return (
        "<div class='review-banner'>"
        "<strong>No Reviews Due</strong><br>"
        "Everything is up to date for today."
        "</div>"
    )


def render_language_badge(language="Waiting"):
    badge = language_flag(language)
    return (
        "<div class='status-pill language-pill'>"
        f"<span class='pill-kicker'>Language</span> Responding in {language.title()} [{badge}]"
        "</div>"
    )


def render_offline_badge():
    return (
        "<div class='status-pill offline-pill'>"
        "<span class='pill-kicker'>Offline</span> No Internet Needed"
        "</div>"
    )


def render_diagnosis_badge(error_type=None):
    if error_type is None:
        return (
            "<div class='diagnosis-card'>"
            "<span class='diagnosis-label neutral'>Diagnosis pending</span>"
            "</div>"
        )

    type_map = {
        1: ("Knowledge Gap", "type-one"),
        2: ("Active Misconception", "type-two"),
        3: ("Careless Slip", "type-three"),
    }
    label, css_class = type_map.get(error_type, ("Unknown", "neutral"))
    return (
        "<div class='diagnosis-card'>"
        f"<span class='diagnosis-label {css_class}'>{label}</span>"
        "</div>"
    )


def render_struggle_box(struggle):
    if struggle["level"] == "Normal":
        return (
            "<div class='struggle-box calm'>"
            "<strong>Struggle Watch:</strong> Normal"
            "</div>"
        )
    signal_list = "".join(f"<li>{signal}</li>" for signal in struggle["signals"])
    return (
        "<div class='struggle-box warning'>"
        f"<strong>{struggle['level']}</strong>"
        f"<div class='struggle-score'>Score: {struggle['struggle_score']}/100</div>"
        f"<ul>{signal_list}</ul>"
        "</div>"
    )


def render_independence_panel(student_name):
    score = get_score(student_name) if student_name else 0
    score_label = get_score_label(student_name) if student_name else "Not started yet"
    week = get_current_week(student_name) if student_name else 1
    help_level = get_help_instructions(student_name) if student_name else "Teacher setup needed before practice."
    progress_width = max(8, int(score)) if score > 0 else 8
    return (
        "<div class='independence-panel'>"
        f"<div class='independence-header'>Week {week} <span>{score_label}</span></div>"
        "<div class='independence-track'>"
        f"<div class='independence-fill' style='width: {progress_width}%;'></div>"
        "</div>"
        f"<div class='independence-meta'>Independence: {score}%</div>"
        f"<div class='help-guidance'>{help_level}</div>"
        "</div>"
    )


def render_teacher_status(student_name, topic):
    if not student_name or not topic:
        return (
            "<div class='teacher-status waiting'>"
            "Teacher setup not saved yet."
            "</div>"
        )
    return (
        "<div class='teacher-status ready'>"
        f"Teacher setup locked for <strong>{student_name}</strong> on <strong>{topic}</strong>."
        "</div>"
    )


def render_report_box(message="Parent report will appear here after the session ends."):
    return f"<div class='report-box'>{message}</div>"


def configure_teacher(student_name, topic, correct_answer):
    global session_data

    if not student_name.strip():
        empty_state = {"student_name": "", "topic": "", "correct_answer": ""}
        return (
            empty_state,
            render_teacher_status("", ""),
            render_review_alert(""),
            render_independence_panel(""),
            render_language_badge("Waiting"),
            render_report_box("Add the student name to begin."),
            [],
        )

    if not topic.strip():
        empty_state = {"student_name": "", "topic": "", "correct_answer": ""}
        return (
            empty_state,
            render_teacher_status("", ""),
            render_review_alert(""),
            render_independence_panel(""),
            render_language_badge("Waiting"),
            render_report_box("Add the topic to begin."),
            [],
        )

    if not correct_answer.strip():
        empty_state = {"student_name": "", "topic": "", "correct_answer": ""}
        return (
            empty_state,
            render_teacher_status("", ""),
            render_review_alert(""),
            render_independence_panel(""),
            render_language_badge("Waiting"),
            render_report_box("Add the correct answer in the teacher setup."),
            [],
        )

    session_data = reset_session_data()
    session_data["student_name"] = student_name
    session_data["topic"] = topic
    session_data["topics_studied"] = [topic]

    teacher_state = {
        "student_name": student_name,
        "topic": topic,
        "correct_answer": correct_answer,
    }

    return (
        teacher_state,
        render_teacher_status(student_name, topic),
        render_review_alert(student_name),
        render_independence_panel(student_name),
        render_language_badge("Waiting"),
        render_report_box("Teacher setup saved. Student can answer now."),
        [],
    )


def handle_answer(student_answer, chat_history, teacher_state):
    global session_data

    if chat_history is None:
        chat_history = []

    if not teacher_state or not teacher_state.get("student_name"):
        return (
            chat_history,
            render_diagnosis_badge(),
            render_struggle_box({"level": "Normal", "struggle_score": 0, "signals": []}),
            render_independence_panel(""),
            render_review_alert(""),
            render_language_badge("Waiting"),
            render_report_box("Save the teacher setup first."),
            "",
        )

    if not student_answer.strip():
        return (
            chat_history,
            render_diagnosis_badge(),
            render_struggle_box({"level": "Normal", "struggle_score": 0, "signals": []}),
            render_independence_panel(teacher_state["student_name"]),
            render_review_alert(teacher_state["student_name"]),
            render_language_badge("Waiting"),
            render_report_box("Student answer is required."),
            "",
        )

    student_name = teacher_state["student_name"]
    topic = teacher_state["topic"]
    correct_answer = teacher_state["correct_answer"]

    session_data["student_name"] = student_name
    session_data["topic"] = topic

    if topic not in session_data["topics_studied"]:
        session_data["topics_studied"].append(topic)

    language = detect_language(student_answer)

    response_time = time.time() - session_data["session_start"]
    session_data["responses"].append(
        {
            "text": student_answer,
            "response_time_seconds": response_time,
        }
    )
    session_data["session_start"] = time.time()

    classification = classify_error(
        student_answer,
        correct_answer,
        topic,
        session_data["history"],
    )
    error_type = classification["error_type"]

    help_instructions = get_help_instructions(student_name)
    prompt_template = load_prompt(error_type)

    teaching_response = generate_response(
        prompt_template,
        student_answer,
        correct_answer,
        topic,
        language,
        help_instructions,
    )

    angle = get_next_angle(student_name, topic)
    log_mistake(student_name, topic, student_answer, error_type, angle)
    session_data["teaching_style"] = angle

    if topic not in session_data["hard_topics"]:
        session_data["hard_topics"].append(topic)

    update_score(student_name, was_correct=False, attempts_needed=2)

    session_data["history"].append(
        {
            "question": correct_answer,
            "student_answer": student_answer,
            "error_type": error_type,
        }
    )

    struggle = analyze_struggle(session_data["responses"])

    chat_history.append({"role": "user", "content": student_answer})
    chat_history.append({"role": "assistant", "content": teaching_response})

    return (
        chat_history,
        render_diagnosis_badge(error_type),
        render_struggle_box(struggle),
        render_independence_panel(student_name),
        render_review_alert(student_name),
        render_language_badge(language),
        render_report_box("Session is active. End session any time to generate the parent report."),
        "",
    )


def end_session(teacher_state):
    if not teacher_state or not teacher_state.get("student_name"):
        return render_report_box("Teacher setup is required before ending a session.")

    student_name = teacher_state["student_name"]
    due = get_due_reviews(student_name)
    score = get_score(student_name)

    report_path = generate_report(
        student_name,
        {
            "topics_studied": session_data["topics_studied"],
            "hard_topics": session_data["hard_topics"],
            "teaching_style_worked": session_data["teaching_style"],
            "due_reviews": due,
            "independence_score": score,
            "struggle_level": analyze_struggle(session_data["responses"])["level"],
            "total_questions": len(session_data["history"]),
            "correct_first_attempt": max(0, len(session_data["history"]) - len(session_data["hard_topics"])),
        },
    )

    return render_report_box(f"Parent report generated successfully.<br><strong>{report_path}</strong>")


with gr.Blocks(title="LEYUM - Offline AI Tutor") as app:
    teacher_state = gr.State({"student_name": "", "topic": "", "correct_answer": ""})

    gr.Markdown("# LEYUM - Offline AI Tutor")
    gr.Markdown("*Understands why a student is wrong, not just that they are wrong.*")

    with gr.Row():
        offline_display = gr.HTML(render_offline_badge())
        language_display = gr.HTML(render_language_badge("Waiting"))

    review_display = gr.HTML(render_review_alert(""))

    with gr.Row(equal_height=True):
        with gr.Column(scale=5):
            with gr.Group(elem_classes=["teacher-card"]):
                gr.Markdown("## Teacher Setup")
                student_name_input = gr.Textbox(label="Student Name", placeholder="e.g. Fatima")
                topic_input = gr.Textbox(label="Topic", placeholder="e.g. Decimals")
                correct_answer_input = gr.Textbox(
                    label="Correct Answer",
                    placeholder="Teacher enters the correct answer here",
                )
                teacher_save_btn = gr.Button("Save Teacher Setup", variant="primary")
                teacher_status = gr.HTML(render_teacher_status("", ""))

            with gr.Group(elem_classes=["student-card"]):
                gr.Markdown("## Student Practice")
                diagnosis_display = gr.HTML(render_diagnosis_badge())
                struggle_display = gr.HTML(
                    render_struggle_box({"level": "Normal", "struggle_score": 0, "signals": []})
                )
                chatbox = gr.Chatbot(label="LEYUM Tutor", height=420)
                student_answer_input = gr.Textbox(
                    label="Student Answer",
                    placeholder="Student types their answer here...",
                    lines=3,
                )
                submit_btn = gr.Button("Check Student Answer", variant="primary")

        with gr.Column(scale=3):
            with gr.Group(elem_classes=["dashboard-card"]):
                gr.Markdown("## Independence")
                independence_display = gr.HTML(render_independence_panel(""))

            with gr.Group(elem_classes=["report-card"]):
                gr.Markdown("## Parent Report")
                report_display = gr.HTML(render_report_box())
                end_btn = gr.Button("Generate Parent Report", variant="primary", elem_classes=["report-button"])

    teacher_save_btn.click(
        fn=configure_teacher,
        inputs=[student_name_input, topic_input, correct_answer_input],
        outputs=[
            teacher_state,
            teacher_status,
            review_display,
            independence_display,
            language_display,
            report_display,
            chatbox,
        ],
    )

    submit_btn.click(
        fn=handle_answer,
        inputs=[student_answer_input, chatbox, teacher_state],
        outputs=[
            chatbox,
            diagnosis_display,
            struggle_display,
            independence_display,
            review_display,
            language_display,
            report_display,
            student_answer_input,
        ],
    )

    end_btn.click(
        fn=end_session,
        inputs=[teacher_state],
        outputs=[report_display],
    )


if __name__ == "__main__":
    app.launch(css=CSS_TEXT, ssl_verify=False)
