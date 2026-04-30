from collections import Counter


def analyze_struggle(responses_in_session):
    """
    responses_in_session = list of dicts:
    [
        {
            "text": "student response text",
            "response_time_seconds": 45
        },
        ...
    ]
    """

    if not responses_in_session:
        return {
            "struggle_score": 0,
            "signals": [],
            "level": "Normal",
        }

    signals = []
    score = 0

    avg_time = sum(r["response_time_seconds"] for r in responses_in_session) / len(responses_in_session)
    if avg_time > 60:
        signals.append("Very slow responses - deep confusion")
        score += 30
    elif avg_time > 30:
        signals.append("Slow responses - struggling with comprehension")
        score += 15

    lengths = [len(r["text"].split()) for r in responses_in_session]
    if len(lengths) >= 3:
        if lengths[-1] < lengths[0] * 0.5:
            signals.append("Responses getting much shorter - fatigue or frustration")
            score += 20

    incomplete = [
        r
        for r in responses_in_session
        if r["text"].strip().endswith(("...", "?", "i dont", "idk", "I don't"))
    ]
    if incomplete:
        signals.append("Incomplete responses - hit wall of confusion")
        score += 25

    all_words = []
    for r in responses_in_session:
        all_words.extend(r["text"].lower().split())

    if all_words:
        word_counts = Counter(all_words)
        most_common_count = word_counts.most_common(1)[0][1]
        if most_common_count >= 4:
            signals.append("Repeating same words - trying to reason through confusion")
            score += 15

    very_short = [r for r in responses_in_session if len(r["text"].split()) <= 2]
    if len(very_short) >= 2:
        signals.append("Multiple very short responses - giving up")
        score += 10

    score = min(score, 100)

    if score >= 60:
        level = "High Struggle"
    elif score >= 30:
        level = "Moderate Struggle"
    else:
        level = "Normal"

    return {
        "struggle_score": score,
        "signals": signals,
        "level": level,
    }
