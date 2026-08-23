"""Management command to seed coding questions and test cases."""

from django.core.management.base import BaseCommand
from assessments.coding_bank import DEFAULT_CODING_QUESTIONS, ensure_coding_bank_seeded
from assessments.models import CodingQuestion, CodingTestCase


class Command(BaseCommand):
    help = "Seed Coding Question Bank with curated DSA problems and test cases."

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0

        for item in DEFAULT_CODING_QUESTIONS:
            q_obj, created = CodingQuestion.objects.update_or_create(
                slug=item["slug"],
                defaults={
                    "title": item["title"],
                    "category": item.get("category", CodingQuestion.Categories.ARRAYS),
                    "description": item["description"],
                    "input_format": item["input_format"],
                    "output_format": item["output_format"],
                    "constraints": item["constraints"],
                    "sample_input": item["sample_input"],
                    "sample_output": item["sample_output"],
                    "explanation": item["explanation"],
                    "difficulty": item["difficulty"],
                    "starter_code": item["starter_code"],
                    "max_score": item["max_score"],
                },

            )
            if created:
                created_count += 1
            else:
                updated_count += 1

            for tc_data in item.get("test_cases", []):
                CodingTestCase.objects.update_or_create(
                    question=q_obj,
                    order=tc_data["order"],
                    defaults={
                        "input_data": tc_data["input_data"],
                        "expected_output": tc_data["expected_output"],
                        "is_sample": tc_data["is_sample"],
                    },
                )

        total_questions = CodingQuestion.objects.count()
        total_test_cases = CodingTestCase.objects.count()

        self.stdout.write(self.style.SUCCESS(f"Coding Questions Created: {created_count}, Updated: {updated_count}"))
        self.stdout.write(f"Total Coding Questions: {total_questions}")
        self.stdout.write(f"Total Test Cases: {total_test_cases}")
