"""Django management command to seed the Question Bank with 150 categorized questions.

Usage:
    python manage.py seed_questions
    python manage.py seed_questions --force
"""

from django.core.management.base import BaseCommand
from assessments.models import Question
from assessments.question_bank import DEFAULT_QUESTIONS


class Command(BaseCommand):
    help = "Seed Question Bank with Logical Reasoning, Quantitative Aptitude, and Technical Aptitude questions."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force update/refresh of all questions from the master question bank.",
        )

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0

        for q_data in DEFAULT_QUESTIONS:
            obj, created = Question.objects.update_or_create(
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
            if created:
                created_count += 1
            else:
                updated_count += 1

        # Section breakdown
        logical_count = Question.objects.filter(section=Question.Sections.LOGICAL).count()
        quant_count = Question.objects.filter(section=Question.Sections.QUANTITATIVE).count()
        tech_count = Question.objects.filter(section=Question.Sections.TECHNICAL).count()
        total_count = Question.objects.count()

        # Optional Firestore synchronization
        try:
            from services.firebase_service import bulk_sync_questions_to_firestore
            all_questions = list(Question.objects.all())
            bulk_sync_questions_to_firestore(all_questions)
        except Exception:
            pass

        self.stdout.write(self.style.SUCCESS(f"Created: {created_count}, Updated: {updated_count}"))
        self.stdout.write(f"Logical Reasoning: {logical_count}")
        self.stdout.write(f"Quantitative Aptitude: {quant_count}")
        self.stdout.write(f"Technical Aptitude: {tech_count}")
        self.stdout.write(self.style.SUCCESS(f"Total: {total_count}"))
