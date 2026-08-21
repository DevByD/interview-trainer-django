"""Email invitation delivery service for candidate assessments with plain-text and HTML support."""

import logging
from django.conf import settings
from django.core.mail import EmailMultiAlternatives

logger = logging.getLogger(__name__)


def send_assessment_invitation(assessment, request=None) -> bool:
    """Send an assessment invitation email to the assigned candidate.

    Sends both plain text and a responsive HTML email with an action CTA.
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
    section_map = {
        "LOGICAL": "Logical Reasoning",
        "QUANTITATIVE": "Quantitative Aptitude",
        "TECHNICAL": "Technical Aptitude",
    }
    section_names = [section_map.get(s, s) for s in sections_list]
    sections_str = ", ".join(section_names) if section_names else "Logical, Quantitative, Technical Aptitude"
    question_count = assessment.questions.count()
    employer_name = (
        assessment.employer.employer_profile.company
        if hasattr(assessment.employer, "employer_profile")
        else assessment.employer.get_full_name() or assessment.employer.username
    )

    subject = "Your Interview Assessment Invitation"
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@interviewtrainer.local")

    text_body = f"""Dear {candidate_name},

You have been invited by {employer_name} to take an online assessment on the Interview Trainer platform.

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

    html_body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; color: #1e293b; margin: 0; padding: 20px; }}
    .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 32px; }}
    .badge {{ display: inline-block; background-color: #eff6ff; color: #2563eb; font-size: 12px; font-weight: 700; padding: 4px 10px; border-radius: 99px; text-transform: uppercase; margin-bottom: 12px; }}
    h1 {{ font-size: 22px; font-weight: 800; color: #0f172a; margin: 0 0 16px 0; }}
    p {{ font-size: 15px; line-height: 1.6; color: #334155; margin: 0 0 16px 0; }}
    .meta-card {{ background-color: #f1f5f9; border-radius: 8px; padding: 16px; margin: 20px 0; font-size: 14px; line-height: 1.8; }}
    .btn {{ display: inline-block; background-color: #2563eb; color: #ffffff !important; font-size: 16px; font-weight: 700; text-decoration: none; padding: 14px 28px; border-radius: 8px; margin: 16px 0; }}
    .footer {{ font-size: 12px; color: #94a3b8; margin-top: 32px; border-top: 1px solid #e2e8f0; padding-top: 16px; }}
  </style>
</head>
<body>
  <div class="container">
    <span class="badge">Assessment Invitation</span>
    <h1>You're Invited to an Online Assessment</h1>
    <p>Dear <strong>{candidate_name}</strong>,</p>
    <p><strong>{employer_name}</strong> has invited you to complete an online assessment on the <strong>Interview Trainer</strong> platform.</p>
    
    <div class="meta-card">
      <strong>Assessment:</strong> {assessment.title}<br>
      <strong>Sections:</strong> {sections_str}<br>
      <strong>Questions:</strong> {question_count}<br>
      <strong>Duration:</strong> {assessment.duration_minutes} Minutes<br>
      <strong>Start Time:</strong> {assessment.start_time.strftime('%B %d, %Y at %H:%M %Z')}<br>
      <strong>Expiry Deadline:</strong> {assessment.expire_time.strftime('%B %d, %Y at %H:%M %Z')}
    </div>

    <p style="text-align: center;">
      <a href="{test_link}" class="btn" target="_blank">Start Assessment &rarr;</a>
    </p>

    <p style="font-size: 13px; color: #64748b;">
      <em>Note: Ensure you have a stable connection. Server time is strictly authoritative and the test will auto-submit when the countdown expires.</em>
    </p>

    <div class="footer">
      Interview Trainer &bull; Smarter Online Assessments<br>
      Direct link: {test_link}
    </div>
  </div>
</body>
</html>
"""

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=from_email,
            to=[candidate_email],
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)

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
