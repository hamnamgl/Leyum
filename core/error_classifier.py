import json

import ollama


def classify_error(student_answer, correct_answer, topic, session_history=[]):
    prompt = f"""You are an expert educational AI. Analyze this student's wrong answer and classify it into exactly one of these three types:

Type 1 - Knowledge Gap: Student has never learned this concept. Complete blank.
Type 2 - Misconception: Student has an active false belief. Confidently wrong.
Type 3 - Careless Error: Student knows the concept but made a small slip.

Topic: {topic}
Correct Answer: {correct_answer}
Student's Answer: {student_answer}
Recent History: {json.dumps(session_history[-5:]) if session_history else "No history yet"}

Reply ONLY with this JSON format, nothing else:
{{
  "error_type": 1,
  "reason": "brief reason here"
}}

error_type must be 1, 2, or 3. Nothing else."""

    response = ollama.chat(
        model="gemma3:4b",
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response["message"]["content"].strip()

    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    result = json.loads(raw.strip())
    return result
