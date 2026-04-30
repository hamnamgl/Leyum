import csv

from core.error_classifier import classify_error


def run_validation():
    correct = 0
    total = 0
    errors = []

    with open("validation/assistments_sample.csv", "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            result = classify_error(
                student_answer=row["student_answer"],
                correct_answer=row["correct_answer"],
                topic=row["topic"],
            )
            predicted = result["error_type"]
            actual = int(row["error_type"])

            if predicted == actual:
                correct += 1
            else:
                errors.append(
                    {
                        "topic": row["topic"],
                        "student_answer": row["student_answer"],
                        "predicted": predicted,
                        "actual": actual,
                        "reason": result["reason"],
                    }
                )

    accuracy = (correct / total) * 100 if total > 0 else 0

    print(f"\n============================")
    print(f"  LEYUM Validation Results")
    print(f"============================")
    print(f"  Total Examples : {total}")
    print(f"  Correct        : {correct}")
    print(f"  Accuracy       : {accuracy:.1f}%")
    print(f"  Errors         : {len(errors)}")
    print(f"============================\n")

    if errors:
        print("Mismatches:")
        for e in errors:
            print(f"  Topic: {e['topic']}")
            print(f"  Student Answer: {e['student_answer']}")
            print(f"  Predicted: Type {e['predicted']} | Actual: Type {e['actual']}")
            print(f"  Reason: {e['reason']}")
            print()


if __name__ == "__main__":
    run_validation()
