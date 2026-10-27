from rest_framework import serializers
from .models import (
    University,
    Course,
    Unit,
    LecturerUnitAssignment,
    StudentEnrollment,
    LearningResource,
    WeeklySummary,
    ConsolidatedRevisionPack,
    Lab,
    AssessmentQuestion,
    AnswerOption,
    LabAttempt,
    SubmittedAnswer,
    ReadinessTest,
    ReadinessQuestion,
    ReadinessAnswerOption,
    ReadinessAttempt,
    ExamEligibility,
)


class UniversitySerializer(serializers.ModelSerializer):
    class Meta:
        model = University
        fields = ['id', 'name', 'code', 'is_demo']


class CourseSerializer(serializers.ModelSerializer):
    university_name = serializers.CharField(source='university.name', read_only=True)

    class Meta:
        model = Course
        fields = ['id', 'university', 'university_name', 'title', 'code', 'department']


class UnitSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='course.title', read_only=True)
    university_name = serializers.CharField(source='course.university.name', read_only=True)
    university_code = serializers.CharField(source='course.university.code', read_only=True)

    class Meta:
        model = Unit
        fields = [
            'id',
            'course',
            'course_title',
            'university_name',
            'university_code',
            'code',
            'title',
            'description',
            'total_weeks',
            'is_primary_demo',
        ]


class LearningResourceSerializer(serializers.ModelSerializer):
    uploader_name = serializers.CharField(source='uploader.username', read_only=True)

    class Meta:
        model = LearningResource
        fields = [
            'id',
            'unit',
            'week_number',
            'title',
            'resource_type',
            'file',
            'external_url',
            'uploader_name',
            'is_published',
            'indexing_state',
            'indexing_error',
            'created_at',
        ]
        read_only_fields = ['uploader_name', 'created_at']


class WeeklySummarySerializer(serializers.ModelSerializer):
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True)

    class Meta:
        model = WeeklySummary
        fields = [
            'id',
            'unit',
            'week_number',
            'summary_text',
            'key_concepts',
            'learning_outcomes',
            'is_published',
            'published_at',
            'updated_by_name',
            'updated_at',
        ]


class ConsolidatedRevisionPackSerializer(serializers.ModelSerializer):
    published_by_name = serializers.CharField(source='published_by.username', read_only=True)

    class Meta:
        model = ConsolidatedRevisionPack
        fields = [
            'id',
            'unit',
            'version',
            'title',
            'content',
            'is_published',
            'published_at',
            'published_by_name',
        ]


class AnswerOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnswerOption
        fields = ['id', 'order', 'option_text', 'is_correct']


class StudentAnswerOptionSerializer(serializers.ModelSerializer):
    """Safely omit is_correct for student during assessment execution."""
    class Meta:
        model = AnswerOption
        fields = ['id', 'order', 'option_text']


class AssessmentQuestionSerializer(serializers.ModelSerializer):
    options = serializers.SerializerMethodField()

    class Meta:
        model = AssessmentQuestion
        fields = [
            'id',
            'lab',
            'order',
            'question_text',
            'question_type',
            'marks',
            'topic_tag',
            'learning_outcome',
            'explanation',
            'rubric',
            'options',
        ]

    def get_options(self, obj):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        # Only show is_correct to lecturers or admins
        if user and getattr(user, 'role', '') in ('lecturer', 'admin'):
            return AnswerOptionSerializer(obj.options.all(), many=True).data
        return StudentAnswerOptionSerializer(obj.options.all(), many=True).data


class LabSerializer(serializers.ModelSerializer):
    questions = AssessmentQuestionSerializer(many=True, read_only=True)
    questions_count = serializers.IntegerField(source='questions.count', read_only=True)

    class Meta:
        model = Lab
        fields = [
            'id',
            'unit',
            'week_number',
            'title',
            'instructions',
            'learning_outcomes',
            'activity_type',
            'total_marks',
            'pass_mark',
            'status',
            'deadline',
            'time_limit_minutes',
            'retake_limit',
            'scoring_policy',
            'require_pass_to_complete',
            'created_at',
            'questions_count',
            'questions',
        ]


class SubmittedAnswerSerializer(serializers.ModelSerializer):
    question_text = serializers.CharField(source='question.question_text', read_only=True)
    topic_tag = serializers.CharField(source='question.topic_tag', read_only=True)

    class Meta:
        model = SubmittedAnswer
        fields = [
            'id',
            'question',
            'question_text',
            'topic_tag',
            'selected_option_ids',
            'written_response',
            'score_awarded',
            'max_marks',
            'is_correct',
            'feedback',
        ]


class LabAttemptSerializer(serializers.ModelSerializer):
    student_username = serializers.CharField(source='student.username', read_only=True)
    lab_title = serializers.CharField(source='lab.title', read_only=True)
    week_number = serializers.IntegerField(source='lab.week_number', read_only=True)
    submitted_answers = SubmittedAnswerSerializer(many=True, read_only=True)

    class Meta:
        model = LabAttempt
        fields = [
            'id',
            'student',
            'student_username',
            'lab',
            'lab_title',
            'week_number',
            'attempt_number',
            'score',
            'max_score',
            'percentage',
            'is_passed',
            'is_completed',
            'started_at',
            'submitted_at',
            'time_taken_seconds',
            'submitted_answers',
        ]


class ReadinessAnswerOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReadinessAnswerOption
        fields = ['id', 'order', 'option_text', 'is_correct']


class StudentReadinessAnswerOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReadinessAnswerOption
        fields = ['id', 'order', 'option_text']


class ReadinessQuestionSerializer(serializers.ModelSerializer):
    options = serializers.SerializerMethodField()

    class Meta:
        model = ReadinessQuestion
        fields = [
            'id',
            'order',
            'question_text',
            'marks',
            'topic_tag',
            'learning_outcome',
            'explanation',
            'options',
        ]

    def get_options(self, obj):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user and getattr(user, 'role', '') in ('lecturer', 'admin'):
            return ReadinessAnswerOptionSerializer(obj.options.all(), many=True).data
        return StudentReadinessAnswerOptionSerializer(obj.options.all(), many=True).data


class ReadinessTestSerializer(serializers.ModelSerializer):
    questions = ReadinessQuestionSerializer(many=True, read_only=True)
    questions_count = serializers.IntegerField(source='questions.count', read_only=True)

    class Meta:
        model = ReadinessTest
        fields = [
            'id',
            'unit',
            'title',
            'instructions',
            'qualifying_threshold',
            'time_limit_minutes',
            'retake_limit',
            'is_active',
            'questions_count',
            'questions',
        ]


class ReadinessAttemptSerializer(serializers.ModelSerializer):
    student_username = serializers.CharField(source='student.username', read_only=True)

    class Meta:
        model = ReadinessAttempt
        fields = [
            'id',
            'student',
            'student_username',
            'readiness_test',
            'attempt_number',
            'score',
            'max_score',
            'percentage',
            'is_passed',
            'is_eligible',
            'weak_topics_identified',
            'submitted_at',
        ]


class ExamEligibilitySerializer(serializers.ModelSerializer):
    student_username = serializers.CharField(source='student.username', read_only=True)
    unit_code = serializers.CharField(source='unit.code', read_only=True)
    unit_title = serializers.CharField(source='unit.title', read_only=True)

    class Meta:
        model = ExamEligibility
        fields = [
            'id',
            'student',
            'student_username',
            'unit',
            'unit_code',
            'unit_title',
            'is_eligible',
            'readiness_score',
            'verified_at',
            'reason',
        ]
