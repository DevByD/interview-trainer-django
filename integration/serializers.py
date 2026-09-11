"""Serializers for HumanDB ATS integration endpoints."""

from rest_framework import serializers


class CandidateSyncSerializer(serializers.Serializer):
    """Input serializer for synchronizing candidates from HumanDB."""

    human_db_user_id = serializers.UUIDField(required=True)
    email = serializers.EmailField(required=True)
    username = serializers.CharField(required=False, allow_blank=True, max_length=150, default="")
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150, default="")
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150, default="")
    phone = serializers.CharField(required=False, allow_blank=True, max_length=20, default="")
    headline = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")
    summary = serializers.CharField(required=False, allow_blank=True, default="")
    location = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")
    resume_url = serializers.URLField(required=False, allow_blank=True, max_length=500, default="")
    linkedin_url = serializers.URLField(required=False, allow_blank=True, max_length=500, default="")
    github_url = serializers.URLField(required=False, allow_blank=True, max_length=500, default="")
    portfolio_url = serializers.URLField(required=False, allow_blank=True, max_length=500, default="")
    skills = serializers.JSONField(required=False, default=list)
    education = serializers.JSONField(required=False, default=list)
    experience = serializers.JSONField(required=False, default=0)

    def validate_email(self, value: str) -> str:
        return value.strip().lower()


class CandidateSyncResponseSerializer(serializers.Serializer):
    """Output serializer for candidate synchronization."""

    success = serializers.BooleanField(default=True)
    human_db_user_id = serializers.UUIDField()
    interview_user_id = serializers.IntegerField()
    candidate_profile_id = serializers.IntegerField()
    email = serializers.EmailField()


class AssessmentCreateSerializer(serializers.Serializer):
    """Input serializer for creating assessments triggered by HumanDB."""

    human_db_user_id = serializers.UUIDField(required=True)
    title = serializers.CharField(required=True, max_length=200)
    start_time = serializers.DateTimeField(required=True)
    expire_time = serializers.DateTimeField(required=True)
    duration_minutes = serializers.IntegerField(required=False, default=60, min_value=1)
    has_coding = serializers.BooleanField(required=False, default=False)
    employer_id = serializers.IntegerField(required=False, default=None, allow_null=True)

    def validate(self, attrs):
        start_time = attrs.get("start_time")
        expire_time = attrs.get("expire_time")
        if start_time and expire_time and expire_time <= start_time:
            raise serializers.ValidationError({
                "expire_time": "expire_time must be strictly later than start_time."
            })
        return attrs


class AssessmentDetailSerializer(serializers.Serializer):
    """Output serializer for detailed assessment retrieval."""

    assessment_id = serializers.IntegerField(source="id")
    human_db_user_id = serializers.SerializerMethodField()
    title = serializers.CharField()
    status = serializers.CharField()
    candidate_status = serializers.CharField()
    start_time = serializers.DateTimeField()
    expire_time = serializers.DateTimeField()
    duration_minutes = serializers.IntegerField()
    has_coding = serializers.BooleanField()
    token = serializers.CharField()

    def get_human_db_user_id(self, obj):
        try:
            profile = getattr(obj.candidate, "candidate_profile", None)
            if profile and profile.human_db_user_id:
                return str(profile.human_db_user_id)
        except Exception:
            pass
        return None


class ResultDetailSerializer(serializers.Serializer):
    """Output serializer for assessment test results."""

    assessment_id = serializers.IntegerField(source="assessment.id")
    human_db_user_id = serializers.SerializerMethodField()
    logical_correct = serializers.IntegerField()
    logical_total = serializers.IntegerField()
    quant_correct = serializers.IntegerField()
    quant_total = serializers.IntegerField()
    technical_correct = serializers.IntegerField()
    technical_total = serializers.IntegerField()
    total_correct = serializers.IntegerField()
    total_questions = serializers.IntegerField()
    percentage = serializers.FloatField()
    has_coding = serializers.BooleanField()
    aptitude_score = serializers.FloatField()
    coding_score = serializers.FloatField()
    overall_score = serializers.FloatField()
    passed = serializers.BooleanField()
    violation_count = serializers.IntegerField()
    auto_submitted_for_malpractice = serializers.BooleanField()
    submission_reason = serializers.CharField()
    completed_at = serializers.DateTimeField()

    def get_human_db_user_id(self, obj):
        try:
            profile = getattr(obj.assessment.candidate, "candidate_profile", None)
            if profile and profile.human_db_user_id:
                return str(profile.human_db_user_id)
        except Exception:
            pass
        return None


class ResultCallbackSerializer(serializers.Serializer):
    """Serializer to validate future HumanDB result callback payloads."""

    assessment_id = serializers.IntegerField(required=True)
    human_db_user_id = serializers.UUIDField(required=False, allow_null=True)
    overall_score = serializers.FloatField(required=False)
    percentage = serializers.FloatField(required=False)
    passed = serializers.BooleanField(required=False)
    has_coding = serializers.BooleanField(required=False)
    completed_at = serializers.DateTimeField(required=False, allow_null=True)
    submission_reason = serializers.CharField(required=False, allow_blank=True)
    status = serializers.CharField(required=False, allow_blank=True)
    extra_data = serializers.JSONField(required=False, default=dict)
