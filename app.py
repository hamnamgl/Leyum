from pathlib import Path
import time

import gradio as gr
import ollama

from core.error_classifier import classify_error
from core.forgetting_curve import get_due_reviews, mark_learned, mark_reviewed
from core.independence_meter import get_score, get_score_label, update_score
from core.language_handler import detect_language
from core.misconception_graph import get_next_angle, log_mistake
from core.parent_report import generate_report
from core.scaffold_fade import get_current_week, get_help_instructions
from core.struggle_detector import analyze_struggle


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


session_data = {
    "student_name": "",
    "topic": "",
    "history": [],
    "responses": [],
    "session_start": time.time(),
    "topics_studied": [],
    "hard_topics": [],
    "teaching_style": "analogy",
}


def handle_answer(student_name, topic, student_answer, correct_answer, chat_history):
    global session_data

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
    reason = classification["reason"]

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

    type_labels = {1: "Knowledge Gap", 2: "Active Misconception", 3: "Careless Slip"}
    label = type_labels.get(error_type, "Unknown")

    full_response = f"[Diagnosis: {label}]\n\n{teaching_response}"

    if struggle["level"] != "Normal":
        full_response += "\n\n⚠️ I notice you might be struggling a little. Take your time — there is no rush."

    if chat_history is None:
        chat_history = []
    chat_history.append((student_answer, full_response))

    score = get_score(student_name)
    score_label = get_score_label(student_name)
    week = get_current_week(student_name)

    due = get_due_reviews(student_name)
    review_text = f"📅 Topics due for review today: {', '.join(due)}" if due else "✅ No reviews due today"

    return chat_history, f"Week {week} | {score_label} | Independence: {score}%", review_text


def end_session(student_name):
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

    return f"✅ Session complete! Parent report saved to: {report_path}"


with gr.Blocks(title="LEYUM — Offline AI Tutor", css=Path("ui/styles.css").read_text(encoding="utf-8")) as app:
    gr.Markdown("# 📘 LEYUM — Offline AI Tutor")
    gr.Markdown("*The tutor that understands WHY you are wrong — not just that you are wrong.*")

    with gr.Row():
        student_name_input = gr.Textbox(label="Your Name", placeholder="e.g. Fatima")
        topic_input = gr.Textbox(label="Topic", placeholder="e.g. Decimals")

    chatbox = gr.Chatbot(label="LEYUM Tutor", height=400)

    with gr.Row():
        student_answer_input = gr.Textbox(label="Your Answer", placeholder="Type your answer here...")
        correct_answer_input = gr.Textbox(label="Correct Answer", placeholder="What is the correct answer?")

    submit_btn = gr.Button("Submit Answer", variant="primary")
    end_btn = gr.Button("End Session & Get Parent Report", variant="secondary")

    independence_display = gr.Textbox(label="Independence Meter", interactive=False)
    review_display = gr.Textbox(label="Review Alerts", interactive=False)
    report_display = gr.Textbox(label="Session Report", interactive=False)

    submit_btn.click(
        fn=handle_answer,
        inputs=[student_name_input, topic_input, student_answer_input, correct_answer_input, chatbox],
        outputs=[chatbox, independence_display, review_display],
    )

    end_btn.click(
        fn=end_session,
        inputs=[student_name_input],
        outputs=[report_display],
    )


if __name__ == "__main__":
    app.launch()
