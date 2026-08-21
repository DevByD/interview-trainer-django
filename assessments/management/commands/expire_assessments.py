from django.core.management.base import BaseCommand
from assessments.services import expire_past_due_assessments


class Command(BaseCommand):
    help = "Expire past-due assessments that were not completed by candidates and mark them as MISSED TEST (NOT_ATTENDED)."

    def handle(self, *args, **options):
        count = expire_past_due_assessments()
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully expired {count} past-due assessment(s). Marked status=EXPIRED and candidate_status=NOT_ATTENDED."
            )
        )
