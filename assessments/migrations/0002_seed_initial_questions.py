from django.db import migrations


def seed_questions(apps, schema_editor):
    Question = apps.get_model("assessments", "Question")
    from assessments.question_bank import DEFAULT_QUESTIONS

    for q_data in DEFAULT_QUESTIONS:
        Question.objects.update_or_create(
            section=q_data["section"],
            question_text=q_data["question_text"],
            defaults={
                "option_a": q_data["option_a"],
                "option_b": q_data["option_b"],
                "option_c": q_data["option_c"],
                "option_d": q_data["option_d"],
                "correct_answer": q_data["correct_answer"],
                "difficulty": q_data["difficulty"],
            },
        )


def unseed_questions(apps, schema_editor):
    # Reverse operation - keep questions
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("assessments", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_questions, reverse_code=unseed_questions),
    ]
