import html
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


def render_teaching_angle(angle="analogy"):
    labels = {
        "analogy": "Analogy Mode",
        "step_by_step": "Step by Step",
        "real_world_story": "Real World Story",
        "counter_example": "Counter Example",
    }
    return (
        "<div class='angle-card'>"
        "<div class='angle-kicker'>Teaching Angle</div>"
        f"<div class='angle-value'>{labels.get(angle, angle.replace('_', ' ').title())}</div>"
        "</div>"
    )


def render_processing_status(state="idle"):
    states = {
        "idle": ("Tutor Ready", "Waiting for the next student answer.", "idle"),
        "working": ("Processing Answer", "Detecting language, classifying error, and preparing feedback.", "working"),
        "done": ("Response Ready", "Diagnosis and teaching response updated.", "done"),
    }
    title, detail, css_class = states.get(state, states["idle"])
    return (
        f"<div class='processing-card {css_class}'>"
        f"<strong>{title}</strong>"
        f"<div class='processing-detail'>{detail}</div>"
        "</div>"
    )


def render_session_analytics():
    total_questions = len(session_data["history"])
    hard_topics = len(session_data["hard_topics"])
    responses_seen = len(session_data["responses"])
    due_reviews = len(get_due_reviews(session_data["student_name"])) if session_data["student_name"] else 0
    return (
        "<div class='analytics-grid'>"
        f"<div class='analytics-card'><div class='analytics-value'>{total_questions}</div><div class='analytics-label'>Questions</div></div>"
        f"<div class='analytics-card'><div class='analytics-value'>{hard_topics}</div><div class='analytics-label'>Hard Topics</div></div>"
        f"<div class='analytics-card'><div class='analytics-value'>{responses_seen}</div><div class='analytics-label'>Responses Seen</div></div>"
        f"<div class='analytics-card'><div class='analytics-value'>{due_reviews}</div><div class='analytics-label'>Reviews Due</div></div>"
        "</div>"
    )


def render_week_timeline(current_week):
    chips = []
    for week in range(1, 7):
        level_map = {1: "80%", 2: "80%", 3: "50%", 4: "50%", 5: "30%", 6: "10%"}
        state = "past" if week < current_week else "current" if week == current_week else "future"
        chips.append(
            "<div class='week-chip {state}'>"
            f"<div class='week-number'>W{week}</div>"
            f"<div class='week-help'>{level_map[week]} help</div>"
            "</div>".format(state=state)
        )
    return "<div class='week-timeline'>" + "".join(chips) + "</div>"


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
        "<div class='timeline-label'>Scaffold fade timeline</div>"
        f"{render_week_timeline(week)}"
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


def render_report_box(message="Parent report will appear here after the session ends.", preview_html=""):
    preview = ""
    if preview_html:
        escaped_html = html.escape(preview_html)
        preview = (
            "<div class='report-preview'>"
            "<div class='report-preview-label'>Live Parent Report Preview</div>"
            f"<iframe class='report-frame' srcdoc='{escaped_html}'></iframe>"
            "</div>"
        )
    return f"<div class='report-box'>{message}</div>{preview}"


def lock_teacher_inputs():
    return (
        gr.update(interactive=False),
        gr.update(interactive=False),
        gr.update(interactive=False),
        gr.update(visible=False),
        gr.update(visible=True),
    )


def unlock_teacher_inputs():
    return (
        gr.update(interactive=True),
        gr.update(interactive=True),
        gr.update(interactive=True),
        gr.update(visible=True),
        gr.update(visible=False),
    )


def configure_teacher(student_name, topic, correct_answer):
    global session_data

    if not student_name.strip():
        empty_state = {"student_name": "", "topic": "", "correct_answer": "", "locked": False}
        return (
            empty_state,
            render_teacher_status("", ""),
            render_review_alert(""),
            render_independence_panel(""),
            render_language_badge("Waiting"),
            render_report_box("Add the student name to begin."),
            None,
            render_session_analytics(),
            [],
            render_teaching_angle("analogy"),
            render_processing_status("idle"),
            *unlock_teacher_inputs(),
        )

    if not topic.strip():
        empty_state = {"student_name": "", "topic": "", "correct_answer": "", "locked": False}
        return (
            empty_state,
            render_teacher_status("", ""),
            render_review_alert(""),
            render_independence_panel(""),
            render_language_badge("Waiting"),
            render_report_box("Add the topic to begin."),
            None,
            render_session_analytics(),
            [],
            render_teaching_angle("analogy"),
            render_processing_status("idle"),
            *unlock_teacher_inputs(),
        )

    if not correct_answer.strip():
        empty_state = {"student_name": "", "topic": "", "correct_answer": "", "locked": False}
        return (
            empty_state,
            render_teacher_status("", ""),
            render_review_alert(""),
            render_independence_panel(""),
            render_language_badge("Waiting"),
            render_report_box("Add the correct answer in the teacher setup."),
            None,
            render_session_analytics(),
            [],
            render_teaching_angle("analogy"),
            render_processing_status("idle"),
            *unlock_teacher_inputs(),
        )

    session_data = reset_session_data()
    session_data["student_name"] = student_name
    session_data["topic"] = topic
    session_data["topics_studied"] = [topic]

    teacher_state = {
        "student_name": student_name,
        "topic": topic,
        "correct_answer": correct_answer,
        "locked": True,
    }

    return (
        teacher_state,
        render_teacher_status(student_name, topic),
        render_review_alert(student_name),
        render_independence_panel(student_name),
        render_language_badge("Waiting"),
        render_report_box("Teacher setup saved. Student can answer now."),
        None,
        render_session_analytics(),
        [],
        render_teaching_angle("analogy"),
        render_processing_status("idle"),
        *lock_teacher_inputs(),
    )


def unlock_teacher(teacher_state):
    state = teacher_state or {}
    if not state.get("student_name"):
        empty_state = {"student_name": "", "topic": "", "correct_answer": "", "locked": False}
        return (
            empty_state,
            render_teacher_status("", ""),
            render_report_box("Nothing is locked yet. Add a teacher setup first."),
            *unlock_teacher_inputs(),
        )

    state["locked"] = False
    return (
        state,
        "<div class='teacher-status waiting'>Teacher setup unlocked. You can edit the saved answer or topic now.</div>",
        render_report_box("Teacher setup unlocked. Save again after making changes."),
        *unlock_teacher_inputs(),
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
            render_session_analytics(),
            render_teaching_angle("analogy"),
            render_processing_status("idle"),
            "",
        )

    if not teacher_state.get("locked"):
        return (
            chat_history,
            render_diagnosis_badge(),
            render_struggle_box({"level": "Normal", "struggle_score": 0, "signals": []}),
            render_independence_panel(teacher_state["student_name"]),
            render_review_alert(teacher_state["student_name"]),
            render_language_badge("Waiting"),
            render_report_box("Teacher setup is unlocked. Save the teacher setup before checking an answer."),
            render_session_analytics(),
            render_teaching_angle(session_data["teaching_style"]),
            render_processing_status("idle"),
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
            render_session_analytics(),
            render_teaching_angle(session_data["teaching_style"]),
            render_processing_status("idle"),
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
        render_session_analytics(),
        render_teaching_angle(angle),
        render_processing_status("done"),
        "",
    )


def begin_processing(chat_history, teacher_state):
    if chat_history is None:
        chat_history = []
    student_name = teacher_state.get("student_name", "") if teacher_state else ""
    angle = session_data.get("teaching_style", "analogy")
    return (
        chat_history,
        render_diagnosis_badge(),
        render_struggle_box({"level": "Normal", "struggle_score": 0, "signals": []}),
        render_independence_panel(student_name),
        render_review_alert(student_name),
        render_language_badge("Analyzing"),
        render_report_box("Working on the student's answer..."),
        render_session_analytics(),
        render_teaching_angle(angle),
        render_processing_status("working"),
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

    preview_html = Path(report_path).read_text(encoding="utf-8")
    return (
        render_report_box(
            f"Parent report generated successfully.<br><strong>{report_path}</strong>",
            preview_html=preview_html,
        ),
        str(Path(report_path).resolve()),
        render_session_analytics(),
    )


with gr.Blocks(title="LEYUM - Offline AI Tutor") as app:
    teacher_state = gr.State({"student_name": "", "topic": "", "correct_answer": "", "locked": False})

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
                teacher_unlock_btn = gr.Button("Unlock Teacher Setup", visible=False)
                teacher_status = gr.HTML(render_teacher_status("", ""))

            with gr.Group(elem_classes=["student-card"]):
                gr.Markdown("## Student Practice")
                diagnosis_display = gr.HTML(render_diagnosis_badge())
                angle_display = gr.HTML(render_teaching_angle("analogy"))
                struggle_display = gr.HTML(
                    render_struggle_box({"level": "Normal", "struggle_score": 0, "signals": []})
                )
                processing_display = gr.HTML(render_processing_status("idle"))
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
                gr.Markdown("## Session Analytics")
                analytics_display = gr.HTML(render_session_analytics())

            with gr.Group(elem_classes=["report-card"]):
                gr.Markdown("## Parent Report")
                report_display = gr.HTML(render_report_box())
                report_file = gr.File(label="Download Parent Report", interactive=False)
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
            report_file,
            analytics_display,
            chatbox,
            angle_display,
            processing_display,
            student_name_input,
            topic_input,
            correct_answer_input,
            teacher_save_btn,
            teacher_unlock_btn,
        ],
    )

    teacher_unlock_btn.click(
        fn=unlock_teacher,
        inputs=[teacher_state],
        outputs=[
            teacher_state,
            teacher_status,
            report_display,
            student_name_input,
            topic_input,
            correct_answer_input,
            teacher_save_btn,
            teacher_unlock_btn,
        ],
    )

    submit_btn.click(
        fn=begin_processing,
        inputs=[chatbox, teacher_state],
        outputs=[
            chatbox,
            diagnosis_display,
            struggle_display,
            independence_display,
            review_display,
            language_display,
            report_display,
            analytics_display,
            angle_display,
            processing_display,
        ],
        show_progress="full",
    ).then(
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
            analytics_display,
            angle_display,
            processing_display,
            student_answer_input,
        ],
        show_progress="full",
    )

    end_btn.click(
        fn=end_session,
        inputs=[teacher_state],
        outputs=[report_display, report_file, analytics_display],
    )


if __name__ == "__main__":
    app.launch(css=CSS_TEXT, ssl_verify=False)
