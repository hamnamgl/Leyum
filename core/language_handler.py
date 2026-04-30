import ollama


def detect_language(text):
    prompt = f"""What language is this text written in? Reply with ONLY the language name in English. Nothing else. No explanation.

Text: {text}"""

    response = ollama.chat(
        model="gemma3:4b",
        messages=[{"role": "user", "content": prompt}],
    )

    language = response["message"]["content"].strip()
    return language
