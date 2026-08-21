"""Email invitation delivery service for candidate assessments."""

import logging
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_assessment_invitation(assessment, request=None) -> bool:
    """Send an assessment invitation email to the assigned candidate.

    Never raises an uncaught exception so that assessment creation is never
    interrupted even if email delivery / SMTP fails.
    """
    candidate_user = assessment.candidate
    candidate_name = candidate_user.get_full_name() or candidate_user.username
    candidate_email = candidate_user.email

    if not candidate_email:
        logger.warning(
            "Candidate %s has no email address. Invitation email skipped.",
            candidate_user.username,
        )
        return False

    if request:
        test_link = request.build_absolute_uri(f"/test/{assessment.token}/")
    else:
        site_domain = getattr(settings, "SITE_DOMAIN", "localhost:8000")
        test_link = f"http://{site_domain}/test/{assessment.token}/"

    # Distinct sections list
    sections_list = (
        assessment.questions.values_list("question__section", flat=True)
        .distinct()
    )
    section_names = []
    section_map = {
        "LOGICAL": "Logical Reasoning",
        "QUANTITATIVE": "Quantitative Aptitude",
        "TECHNICAL": "Technical Aptitude",
    }
    for s in sections_list:
        section_names.append(section_map.get(s, s))

    sections_str = ", ".join(section_names) if section_names else "Logical, Quantitative, Technical Aptitude"
    question_count = assessment.questions.count()

    subject = "Your Interview Assessment Invitation"
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@interviewtrainer.local")

    message_body = f"""Dear {candidate_name},

You have been invited by {assessment.employer.employer_profile.company if hasattr(assessment.employer, 'employer_profile') else assessment.employer.get_full_name() or assessment.employer.username} to take an online assessment on the Interview Trainer platform.

------------------------------------------------------------
ASSESSMENT DETAILS
------------------------------------------------------------
Title:               {assessment.title}
Sections:            {sections_str}
Number of Questions: {question_count}
Duration:            {assessment.duration_minutes} minutes
Start Date & Time:   {assessment.start_time.strftime('%B %d, %Y at %H:%M %Z')}
Expiry Date & Time:  {assessment.expire_time.strftime('%B %d, %Y at %H:%M %Z')}

------------------------------------------------------------
INSTRUCTIONS
------------------------------------------------------------
1. Ensure you have a stable internet connection before starting.
2. Read each question carefully and select the best answer.
3. Keep track of the authoritative server-side countdown timer.
4. The test will automatically submit when the timer expires.
5. Only one final submission is permitted.

ACCESS YOUR TEST:
{test_link}

Good luck!
The Interview Trainer Team
"""

    try:
        send_mail(
            subject=subject,
            message=message_body,
            from_email=from_email,
            recipient_list=[candidate_email],
            fail_silently=False,
        )
        logger.info(
            "Assessment invitation successfully sent to candidate %s <%s> for '%s'.",
            candidate_name,
            candidate_email,
            assessment.title,
        )
        return True
    except Exception as exc:
        logger.error(
            "Failed to deliver assessment invitation email to %s: %s",
            candidate_email,
            exc,
            exc_info=True,
        )
        return False
