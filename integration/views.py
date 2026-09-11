"""API views for HumanDB Recruitment / ATS integration."""

import logging
import os
from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import CandidateProfile, EmployerProfile
from assessments.models import (
    Assessment,
    AssessmentCodingQuestion,
    AssessmentQuestion,
    CodingQuestion,
    CodingSubmission,
    Question,
)
from integration.authentication import (
    HasHumanDBIntegrationKey,
    HumanDBIntegrationAuthentication,
)
from integration.models import IntegrationSyncLog
from integration.serializers import (
    AssessmentCreateSerializer,
    AssessmentDetailSerializer,
    CandidateSyncSerializer,
    ResultCallbackSerializer,
    ResultDetailSerializer,
)

logger = logging.getLogger(__name__)


def _get_or_create_integration_employer(employer_id=None) -> User:
    """Retrieve or create the system employer account for HumanDB integration assessments."""
    if employer_id:
        emp = User.objects.filter(id=employer_id).first()
        if emp:
            return emp

    # Check for configured default employer in settings/env
    configured_username = getattr(settings, "HUMANDB_DEFAULT_EMPLOYER_USERNAME", "")
    if configured_username:
        emp = User.objects.filter(username=configured_username).first()
        if emp:
            return emp

    # Fallback to system HumanDB recruiter
    employer_user, _ = User.objects.get_or_create(
        username="humandb_integration",
        defaults={
            "first_name": "HumanDB",
            "last_name": "Recruiter",
            "email": "humandb-recruiter@local.system",
            "is_active": True,
        },
    )
    EmployerProfile.objects.get_or_create(
        user=employer_user,
        defaults={"company": "HumanDB Recruitment"},
    )
    return employer_user


class CandidateSyncView(APIView):
    """Synchronize a shortlisted candidate from HumanDB into Interview Trainer.

    POST /api/integration/candidates/sync/
    Idempotent: updates existing records if human_db_user_id matches.
    """

    authentication_classes = [HumanDBIntegrationAuthentication]
    permission_classes = [HasHumanDBIntegrationKey]

    def post(self, request):
        serializer = CandidateSyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        human_db_user_id = data["human_db_user_id"]
        email = data["email"]
        username = data.get("username", "").strip()
        first_name = data.get("first_name", "").strip()
        last_name = data.get("last_name", "").strip()
        phone = data.get("phone", "").strip()
        headline = data.get("headline", "").strip()
        summary = data.get("summary", "").strip()
        location = data.get("location", "").strip()
        resume_url = data.get("resume_url", "").strip()
        linkedin_url = data.get("linkedin_url", "").strip()
        github_url = data.get("github_url", "").strip()
        portfolio_url = data.get("portfolio_url", "").strip()
        skills_raw = data.get("skills", [])
        education_raw = data.get("education", [])
        experience_raw = data.get("experience", 0)

        # Normalize skills as comma-separated string
        if isinstance(skills_raw, list):
            skills_str = ", ".join(str(s).strip() for s in skills_raw if str(s).strip())
        else:
            skills_str = str(skills_raw).strip()

        # Normalize education (capped at 200 chars to fit DB schema)
        if isinstance(education_raw, list):
            edu_items = []
            for item in education_raw:
                if isinstance(item, dict):
                    deg = item.get("degree") or item.get("name") or ""
                    inst = item.get("institution") or item.get("school") or item.get("university") or ""
                    if deg and inst:
                        edu_items.append(f"{deg}, {inst}")
                    elif deg or inst:
                        edu_items.append(deg or inst)
                elif isinstance(item, str) and item.strip():
                    edu_items.append(item.strip())
            education_str = "; ".join(edu_items)[:200]
        else:
            education_str = str(education_raw).strip()[:200]

        # Normalize experience years
        experience_val = 0
        if isinstance(experience_raw, (int, float)):
            experience_val = max(0, min(50, int(experience_raw)))
        elif isinstance(experience_raw, list):
            experience_val = min(50, len(experience_raw))
        elif isinstance(experience_raw, str) and experience_raw.isdigit():
            experience_val = max(0, min(50, int(experience_raw)))

        with transaction.atomic():
            # 1. Check if candidate already exists by HumanDB UUID
            profile = CandidateProfile.objects.select_related("user").filter(
                human_db_user_id=human_db_user_id
            ).first()

            if profile:
                user = profile.user
                user_updated = False
                if first_name and user.first_name != first_name:
                    user.first_name = first_name
                    user_updated = True
                if last_name and user.last_name != last_name:
                    user.last_name = last_name
                    user_updated = True
                if email and user.email != email:
                    user.email = email
                    user_updated = True
                if user_updated:
                    user.save()
            else:
                # 2. Check if a User with this email already exists
                user = User.objects.filter(email__iexact=email).first()
                if user:
                    profile = getattr(user, "candidate_profile", None)
                    if profile:
                        if profile.human_db_user_id and profile.human_db_user_id != human_db_user_id:
                            return Response(
                                {
                                    "error": f"Candidate email '{email}' is already mapped to another HumanDB user ID."
                                },
                                status=status.HTTP_400_BAD_REQUEST,
                            )
                        profile.human_db_user_id = human_db_user_id
                    else:
                        profile = CandidateProfile(user=user, human_db_user_id=human_db_user_id)

                    user_updated = False
                    if first_name and not user.first_name:
                        user.first_name = first_name
                        user_updated = True
                    if last_name and not user.last_name:
                        user.last_name = last_name
                        user_updated = True
                    if user_updated:
                        user.save()
                else:
                    # 3. Create new User with unusable password
                    final_username = username
                    if not final_username or User.objects.filter(username=final_username).exists():
                        if not User.objects.filter(username=email).exists():
                            final_username = email
                        else:
                            short_id = str(human_db_user_id).replace("-", "")[:8]
                            final_username = f"cand_{short_id}"
                            counter = 1
                            base_uname = final_username
                            while User.objects.filter(username=final_username).exists():
                                final_username = f"{base_uname}_{counter}"
                                counter += 1

                    user = User(
                        username=final_username,
                        email=email,
                        first_name=first_name,
                        last_name=last_name,
                        is_active=True,
                    )
                    user.set_unusable_password()
                    user.save()

                    profile = CandidateProfile(
                        user=user,
                        human_db_user_id=human_db_user_id,
                    )

            # Update profile attributes
            if phone:
                profile.phone = phone
            if education_str:
                profile.education = education_str
            if skills_str:
                profile.skills = skills_str
            if experience_val is not None:
                profile.experience = experience_val
            if headline:
                profile.headline = headline
            if summary:
                profile.summary = summary
            if location:
                profile.location = location
            if resume_url:
                profile.resume_url = resume_url
            if linkedin_url:
                profile.linkedin_url = linkedin_url
            if github_url:
                profile.github_url = github_url
            if portfolio_url:
                profile.portfolio_url = portfolio_url

            profile.save()

        # Firestore synchronization if available
        try:
            from services.firebase_service import sync_candidate_to_firestore
            sync_candidate_to_firestore(user, profile)
        except Exception as e:
            logger.debug("Firestore candidate sync skipped: %s", e)

        # Audit log
        try:
            IntegrationSyncLog.objects.create(
                action=IntegrationSyncLog.ActionType.CANDIDATE_SYNC,
                human_db_user_id=human_db_user_id,
                payload={"email": email, "interview_user_id": user.id},
                response_status=200,
            )
        except Exception:
            pass

        return Response(
            {
                "success": True,
                "human_db_user_id": str(human_db_user_id),
                "interview_user_id": user.id,
                "candidate_profile_id": profile.id,
                "email": user.email,
            },
            status=status.HTTP_200_OK,
        )


class AssessmentCreateView(APIView):
    """Create an assessment for a synchronized HumanDB candidate.

    POST /api/integration/assessments/
    """

    authentication_classes = [HumanDBIntegrationAuthentication]
    permission_classes = [HasHumanDBIntegrationKey]

    def post(self, request):
        serializer = AssessmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        human_db_user_id = data["human_db_user_id"]
        profile = CandidateProfile.objects.select_related("user").filter(
            human_db_user_id=human_db_user_id
        ).first()

        if not profile:
            return Response(
                {
                    "error": f"Candidate with human_db_user_id '{human_db_user_id}' not found. Please sync candidate first."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        candidate_user = profile.user
        employer_user = _get_or_create_integration_employer(data.get("employer_id"))
        has_coding = data.get("has_coding", False)

        with transaction.atomic():
            assessment = Assessment.objects.create(
                employer=employer_user,
                candidate=candidate_user,
                title=data["title"],
                start_time=data["start_time"],
                expire_time=data["expire_time"],
                duration_minutes=data["duration_minutes"],
                status=Assessment.Status.PENDING,
                candidate_status=Assessment.CandidateStatus.NOT_STARTED,
                has_coding=has_coding,
            )

            # Assign MCQ questions from Question Bank
            selected_mcq_questions = []
            for section in [
                Question.Sections.LOGICAL,
                Question.Sections.QUANTITATIVE,
                Question.Sections.TECHNICAL,
            ]:
                qs = Question.objects.filter(section=section, is_active=True, is_approved=True)
                if not qs.exists():
                    qs = Question.objects.filter(section=section)
                selected_mcq_questions.extend(list(qs.order_by("?")[:5]))

            if selected_mcq_questions:
                AssessmentQuestion.objects.bulk_create([
                    AssessmentQuestion(assessment=assessment, question=q, order=idx + 1)
                    for idx, q in enumerate(selected_mcq_questions)
                ])

            # Assign Coding question if coding assessment
            selected_coding_questions = []
            if has_coding:
                cqs = CodingQuestion.objects.filter(is_active=True, is_approved=True)
                if not cqs.exists():
                    cqs = CodingQuestion.objects.all()
                selected_coding_questions = list(cqs.order_by("?")[:1])

                if selected_coding_questions:
                    AssessmentCodingQuestion.objects.bulk_create([
                        AssessmentCodingQuestion(assessment=assessment, question=cq, order=c_idx + 1)
                        for c_idx, cq in enumerate(selected_coding_questions)
                    ])
                    for cq in selected_coding_questions:
                        CodingSubmission.objects.get_or_create(
                            assessment=assessment,
                            question=cq,
                            defaults={
                                "language": "python",
                                "source_code": "",
                                "total_test_cases": cq.test_cases.count(),
                            },
                        )

        # Firestore sync if available
        try:
            from services.firebase_service import sync_assessment_to_firestore
            q_ids = [q.id for q in selected_mcq_questions]
            sync_assessment_to_firestore(assessment, q_ids)
        except Exception as e:
            logger.debug("Firestore assessment sync skipped: %s", e)

        # Audit log
        try:
            IntegrationSyncLog.objects.create(
                action=IntegrationSyncLog.ActionType.ASSESSMENT_CREATE,
                human_db_user_id=human_db_user_id,
                assessment_id=assessment.id,
                payload={"title": assessment.title, "token": assessment.token},
                response_status=201,
            )
        except Exception:
            pass

        return Response(
            {
                "success": True,
                "assessment_id": assessment.id,
                "token": assessment.token,
                "candidate": {
                    "human_db_user_id": str(human_db_user_id),
                    "interview_user_id": candidate_user.id,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class AssessmentDetailView(APIView):
    """Retrieve detailed information about a single assessment.

    GET /api/integration/assessments/<int:assessment_id>/
    """

    authentication_classes = [HumanDBIntegrationAuthentication]
    permission_classes = [HasHumanDBIntegrationKey]

    def get(self, request, assessment_id):
        try:
            assessment = Assessment.objects.select_related(
                "candidate", "candidate__candidate_profile"
            ).get(pk=assessment_id)
        except Assessment.DoesNotExist:
            return Response(
                {"error": f"Assessment with id {assessment_id} not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = AssessmentDetailSerializer(assessment)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ResultDetailView(APIView):
    """Retrieve assessment test results for HumanDB.

    GET /api/integration/results/<int:assessment_id>/
    """

    authentication_classes = [HumanDBIntegrationAuthentication]
    permission_classes = [HasHumanDBIntegrationKey]

    def get(self, request, assessment_id):
        try:
            assessment = Assessment.objects.select_related(
                "candidate", "candidate__candidate_profile"
            ).get(pk=assessment_id)
        except Assessment.DoesNotExist:
            return Response(
                {"error": f"Assessment with id {assessment_id} not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            result = assessment.result
        except Assessment.result.RelatedObjectDoesNotExist:
            return Response(
                {"error": f"Result for assessment {assessment_id} not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ResultDetailSerializer(result)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ResultCallbackView(APIView):
    """Receive or simulate result callback for HumanDB testing.

    POST /api/integration/results/callback/
    Accepts and validates result payload. Only calls HumanDB if explicitly configured.
    """

    authentication_classes = [HumanDBIntegrationAuthentication]
    permission_classes = [HasHumanDBIntegrationKey]

    def post(self, request):
        serializer = ResultCallbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # DO NOT call HumanDB yet unless an explicit HUMANDB callback URL and secret are configured
        callback_url = getattr(
            settings, "HUMANDB_CALLBACK_URL", os.getenv("HUMANDB_CALLBACK_URL", "")
        ).strip()
        callback_secret = getattr(
            settings, "HUMANDB_CALLBACK_SECRET", os.getenv("HUMANDB_CALLBACK_SECRET", "")
        ).strip()

        forwarded = False
        if callback_url and callback_secret:
            try:
                import requests
                headers = {
                    "Authorization": f"Token {callback_secret}",
                    "Content-Type": "application/json",
                }
                requests.post(callback_url, json=request.data, headers=headers, timeout=5)
                forwarded = True
            except Exception as e:
                logger.warning("HumanDB callback dispatch failed: %s", e)
                forwarded = False

        # Convert validated data to JSON-serializable dictionary
        clean_data = {
            "assessment_id": data["assessment_id"],
            "human_db_user_id": str(data["human_db_user_id"]) if data.get("human_db_user_id") else None,
            "overall_score": data.get("overall_score"),
            "percentage": data.get("percentage"),
            "passed": data.get("passed"),
            "has_coding": data.get("has_coding"),
            "completed_at": data.get("completed_at").isoformat() if data.get("completed_at") else None,
            "submission_reason": data.get("submission_reason", ""),
            "status": data.get("status", ""),
            "extra_data": data.get("extra_data", {}),
        }

        # Audit log
        IntegrationSyncLog.objects.create(
            action=IntegrationSyncLog.ActionType.RESULT_CALLBACK,
            human_db_user_id=data.get("human_db_user_id"),
            assessment_id=data.get("assessment_id"),
            payload=clean_data,
            response_status=200,
        )

        return Response(
            {
                "success": True,
                "message": "Result callback accepted and validated successfully.",
                "forwarded_to_humandb": forwarded,
                "data": clean_data,
            },
            status=status.HTTP_200_OK,
        )
