import os
from decimal import Decimal
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser, JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

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
    ReadinessTest,
    ReadinessQuestion,
    ReadinessAnswerOption,
    ReadinessAttempt,
    ExamEligibility,
)
from .permissions import (
    IsLecturerOrAdmin,
    log_unauthorized_access,
)
from .serializers import (
    UniversitySerializer,
    CourseSerializer,
    UnitSerializer,
    LearningResourceSerializer,
    WeeklySummarySerializer,
    ConsolidatedRevisionPackSerializer,
    LabSerializer,
    LabAttemptSerializer,
    ReadinessTestSerializer,
    ReadinessAttemptSerializer,
    ExamEligibilitySerializer,
)
from .services import (
    calculate_unit_readiness_status,
    grade_lab_submission,
    get_student_lab_summary,
    calculate_student_weakness_recommendations,
    grade_readiness_attempt,
    get_lecturer_cohort_analytics,
)
from security.services import create_security_event


# -------------------------------------------------------------
# Catalog & Enrollment Views
# -------------------------------------------------------------

class UniversityListView(APIView):
    """GET /api/academic/universities/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        universities = University.objects.all().order_by('name')
        return Response(UniversitySerializer(universities, many=True).data)


class CourseListView(APIView):
    """GET /api/academic/courses/?university_id=X"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        uni_id = request.query_params.get('university_id')
        qs = Course.objects.all().select_related('university')
        if uni_id:
            qs = qs.filter(university_id=uni_id)
        return Response(CourseSerializer(qs, many=True).data)


class UnitListView(APIView):
    """GET /api/academic/units/?course_id=X"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        course_id = request.query_params.get('course_id')
        qs = Unit.objects.all().select_related('course', 'course__university')
        if course_id:
            qs = qs.filter(course_id=course_id)
        return Response(UnitSerializer(qs, many=True).data)


class EnrolledUnitsView(APIView):
    """GET /api/academic/units/enrolled/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role == 'student':
            enrollments = StudentEnrollment.objects.filter(
                student=request.user,
                status='active'
            ).select_related('unit', 'unit__course', 'unit__course__university')
            units = [e.unit for e in enrollments]
            return Response(UnitSerializer(units, many=True).data)
        elif request.user.role == 'lecturer':
            assignments = LecturerUnitAssignment.objects.filter(
                lecturer=request.user
            ).select_related('unit', 'unit__course', 'unit__course__university')
            units = [a.unit for a in assignments]
            return Response(UnitSerializer(units, many=True).data)
        else:
            # Admin sees all units
            units = Unit.objects.all().select_related('course', 'course__university')
            return Response(UnitSerializer(units, many=True).data)


class EnrollStudentView(APIView):
    """POST /api/academic/units/<unit_id>/enroll/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, unit_id):
        unit = get_object_or_404(Unit, pk=unit_id)
        enrollment, created = StudentEnrollment.objects.get_or_create(
            student=request.user,
            unit=unit,
            defaults={'status': 'active'}
        )
        return Response({
            "message": f"Successfully enrolled in {unit.code}: {unit.title}.",
            "unit": UnitSerializer(unit).data,
            "created": created,
        })


# -------------------------------------------------------------
# 14-Week Learning Resources & Weekly Summaries
# -------------------------------------------------------------

class UnitResourcesView(APIView):
    """
    GET /api/academic/units/<unit_id>/resources/?week=X
    POST /api/academic/units/<unit_id>/resources/
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request, unit_id):
        unit = get_object_or_404(Unit, pk=unit_id)

        # Boundary check: student must be enrolled
        if request.user.role == 'student':
            if not StudentEnrollment.objects.filter(student=request.user, unit=unit, status='active').exists():
                log_unauthorized_access(
                    request,
                    reason=f"Student {request.user.username} tried to view un-enrolled unit {unit.code}",
                    target_unit_id=unit.id,
                )
                return Response({'error': 'You are not enrolled in this unit.'}, status=403)
            qs = LearningResource.objects.filter(unit=unit, is_published=True)
        else:
            qs = LearningResource.objects.filter(unit=unit)

        week = request.query_params.get('week')
        if week and week.isdigit():
            qs = qs.filter(week_number=int(week))

        return Response(LearningResourceSerializer(qs.order_by('week_number', 'created_at'), many=True).data)

    def post(self, request, unit_id):
        unit = get_object_or_404(Unit, pk=unit_id)

        # Authorization: Lecturer assigned or admin
        if request.user.role == 'student':
            log_unauthorized_access(
                request,
                reason=f"Student {request.user.username} attempted to upload learning material to {unit.code}",
                target_unit_id=unit.id,
            )
            return Response({'error': 'Lecturer authorization required.'}, status=403)

        if request.user.role == 'lecturer' and not LecturerUnitAssignment.objects.filter(lecturer=request.user, unit=unit).exists():
            log_unauthorized_access(
                request,
                reason=f"Lecturer {request.user.username} attempted to upload material to unassigned unit {unit.code}",
                target_unit_id=unit.id,
            )
            return Response({'error': 'You are not assigned to manage this unit.'}, status=403)

        title = str(request.data.get('title', '')).strip()
        week_number = request.data.get('week_number')
        resource_type = request.data.get('resource_type', 'pdf')
        external_url = str(request.data.get('external_url', '')).strip()
        file_obj = request.FILES.get('file')

        if not title:
            return Response({'error': 'Resource title is required.'}, status=400)
        if not week_number or not str(week_number).isdigit() or int(week_number) < 1 or int(week_number) > 14:
            return Response({'error': 'Valid week number (1-14) is required.'}, status=400)

        week_num = int(week_number)

        # File validation if file is uploaded
        indexing_state = 'indexed'
        indexing_error = ''

        if file_obj:
            # Validate size (10 MB max)
            if file_obj.size > 10 * 1024 * 1024:
                create_security_event(
                    event_type='malicious_upload',
                    severity='MEDIUM',
                    description=f"Upload rejected: File size {file_obj.size} bytes exceeds 10MB limit.",
                    user=request.user,
                    endpoint=request.path,
                    request=request,
                    metadata={'filename': file_obj.name, 'size': file_obj.size},
                )
                return Response({'error': 'File size exceeds 10MB limit.'}, status=400)

            # Validate extension
            ext = os.path.splitext(file_obj.name)[1].lower()
            allowed_exts = {'.pdf', '.png', '.jpg', '.jpeg', '.docx', '.pptx', '.txt'}
            if ext not in allowed_exts:
                create_security_event(
                    event_type='malicious_upload',
                    severity='HIGH',
                    description=f"Upload rejected: Disallowed file extension '{ext}'.",
                    user=request.user,
                    endpoint=request.path,
                    request=request,
                    metadata={'filename': file_obj.name, 'extension': ext},
                )
                return Response({'error': f"Disallowed file extension '{ext}'. Supported: PDF, PNG, JPG, DOCX."}, status=400)

            # Validate magic bytes for PDFs
            if ext == '.pdf':
                header = file_obj.read(5)
                file_obj.seek(0)
                if header != b'%PDF-':
                    create_security_event(
                        event_type='malicious_upload',
                        severity='HIGH',
                        description="Upload rejected: File claims to be PDF but lacks valid %PDF header.",
                        user=request.user,
                        endpoint=request.path,
                        request=request,
                        metadata={'filename': file_obj.name},
                    )
                    return Response({'error': 'Invalid file format: Corrupted or spoofed PDF.'}, status=400)

        resource = LearningResource.objects.create(
            unit=unit,
            week_number=week_num,
            title=title,
            resource_type=resource_type,
            file=file_obj,
            external_url=external_url,
            uploader=request.user,
            is_published=True,
            indexing_state=indexing_state,
            indexing_error=indexing_error,
        )

        return Response(LearningResourceSerializer(resource).data, status=201)


class UnitSummariesView(APIView):
    """
    GET /api/academic/units/<unit_id>/summaries/
    POST /api/academic/units/<unit_id>/summaries/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, unit_id):
        unit = get_object_or_404(Unit, pk=unit_id)
        if request.user.role == 'student':
            qs = WeeklySummary.objects.filter(unit=unit, is_published=True)
        else:
            qs = WeeklySummary.objects.filter(unit=unit)
        return Response(WeeklySummarySerializer(qs.order_by('week_number'), many=True).data)

    def post(self, request, unit_id):
        unit = get_object_or_404(Unit, pk=unit_id)
        if request.user.role not in ('lecturer', 'admin'):
            return Response({'error': 'Lecturer or admin access required.'}, status=403)

        week_number = request.data.get('week_number')
        if not week_number or not str(week_number).isdigit():
            return Response({'error': 'Valid week number is required.'}, status=400)

        summary_text = str(request.data.get('summary_text', '')).strip()
        key_concepts = request.data.get('key_concepts', [])
        learning_outcomes = request.data.get('learning_outcomes', [])
        is_published = bool(request.data.get('is_published', True))

        summary, created = WeeklySummary.objects.update_or_create(
            unit=unit,
            week_number=int(week_number),
            defaults={
                'summary_text': summary_text,
                'key_concepts': key_concepts if isinstance(key_concepts, list) else [],
                'learning_outcomes': learning_outcomes if isinstance(learning_outcomes, list) else [],
                'is_published': is_published,
                'published_at': timezone.now() if is_published else None,
                'updated_by': request.user,
            }
        )
        return Response(WeeklySummarySerializer(summary).data, status=200)


class ConsolidatedRevisionPackView(APIView):
    """
    GET /api/academic/units/<unit_id>/revision-pack/
    POST /api/academic/units/<unit_id>/revision-pack/publish/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, unit_id):
        unit = get_object_or_404(Unit, pk=unit_id)
        pack = ConsolidatedRevisionPack.objects.filter(unit=unit, is_published=True).order_by('-published_at').first()
        if not pack:
            # Build an aggregated on-the-fly preview from published summaries & resources
            summaries = WeeklySummary.objects.filter(unit=unit, is_published=True).order_by('week_number')
            content_by_week = {}
            for s in summaries:
                res_titles = list(LearningResource.objects.filter(unit=unit, week_number=s.week_number, is_published=True).values_list('title', flat=True))
                content_by_week[f"week_{s.week_number}"] = {
                    "week_number": s.week_number,
                    "title": f"Week {s.week_number} Core Concepts",
                    "summary": s.summary_text,
                    "key_concepts": s.key_concepts,
                    "learning_outcomes": s.learning_outcomes,
                    "resources": res_titles,
                }
            return Response({
                "unit": unit.id,
                "version": "v1.0 (Draft Preview)",
                "title": f"{unit.code}: 14-Week Comprehensive Revision Pack",
                "content": content_by_week,
                "is_published": False,
                "published_at": None,
                "published_by_name": "Course Directorate",
            })
        return Response(ConsolidatedRevisionPackSerializer(pack).data)

    def post(self, request, unit_id):
        unit = get_object_or_404(Unit, pk=unit_id)
        if request.user.role not in ('lecturer', 'admin'):
            return Response({'error': 'Lecturer or admin access required.'}, status=403)

        version = str(request.data.get('version', 'v1.0')).strip()
        custom_content = request.data.get('content')

        if not custom_content:
            # Aggregate all 14 weeks from approved summaries
            summaries = WeeklySummary.objects.filter(unit=unit, is_published=True).order_by('week_number')
            content_by_week = {}
            for s in summaries:
                res_titles = list(LearningResource.objects.filter(unit=unit, week_number=s.week_number, is_published=True).values_list('title', flat=True))
                content_by_week[f"week_{s.week_number}"] = {
                    "week_number": s.week_number,
                    "title": f"Week {s.week_number} Core Concepts",
                    "summary": s.summary_text,
                    "key_concepts": s.key_concepts,
                    "learning_outcomes": s.learning_outcomes,
                    "resources": res_titles,
                }
            custom_content = content_by_week

        pack = ConsolidatedRevisionPack.objects.create(
            unit=unit,
            version=version,
            title=f"{unit.code}: 14-Week Consolidated Revision Pack ({version})",
            content=custom_content,
            is_published=True,
            published_by=request.user,
        )
        return Response(ConsolidatedRevisionPackSerializer(pack).data, status=201)


class StudentWeaknessRecommendationsView(APIView):
    """GET /api/academic/units/<unit_id>/weaknesses/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, unit_id):
        unit = get_object_or_404(Unit, pk=unit_id)
        # Students view their own weaknesses; lecturers can specify ?student_id=X
        target_student = request.user
        student_id = request.query_params.get('student_id')
        if student_id and request.user.role in ('lecturer', 'admin'):
            from django.contrib.auth import get_user_model
            User = get_user_model()
            target_student = get_object_or_404(User, pk=student_id)

        recommendations = calculate_student_weakness_recommendations(target_student, unit)
        return Response(recommendations)


# -------------------------------------------------------------
# Weekly Labs & Assessment Builder Views
# -------------------------------------------------------------

class UnitLabsView(APIView):
    """
    GET /api/academic/units/<unit_id>/labs/
    POST /api/academic/units/<unit_id>/labs/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, unit_id):
        unit = get_object_or_404(Unit, pk=unit_id)
        if request.user.role == 'student':
            qs = Lab.objects.filter(unit=unit, status__in=['published', 'closed']).order_by('week_number')
        else:
            qs = Lab.objects.filter(unit=unit).order_by('week_number')

        serializer = LabSerializer(qs, many=True, context={'request': request})
        labs_data = serializer.data

        # If student, attach attempt status & score summary for each lab
        if request.user.role == 'student':
            for lab_dict in labs_data:
                lab_obj = Lab.objects.filter(id=lab_dict['id']).first()
                if lab_obj:
                    summary = get_student_lab_summary(request.user, lab_obj)
                    lab_dict['student_summary'] = {
                        'attempt_count': summary['attempt_count'],
                        'latest_score': summary['latest_score'],
                        'best_score': summary['best_score'],
                        'counted_score': summary['counted_score'],
                        'is_completed': summary['is_completed'],
                        'is_passed': summary['is_passed'],
                    }

        return Response(labs_data)

    def post(self, request, unit_id):
        unit = get_object_or_404(Unit, pk=unit_id)
        if request.user.role not in ('lecturer', 'admin'):
            log_unauthorized_access(request, reason=f"Unauthorized lab creation attempt by {request.user.username}", target_unit_id=unit.id)
            return Response({'error': 'Lecturer or admin authorization required.'}, status=403)

        title = str(request.data.get('title', '')).strip()
        week_number = request.data.get('week_number')
        activity_type = request.data.get('activity_type', 'mixed')
        total_marks = int(request.data.get('total_marks', 100))
        pass_mark = int(request.data.get('pass_mark', 50))
        instructions = str(request.data.get('instructions', ''))
        retake_limit = int(request.data.get('retake_limit', 3))
        scoring_policy = request.data.get('scoring_policy', 'best')
        require_pass = bool(request.data.get('require_pass_to_complete', False))
        questions_payload = request.data.get('questions', [])

        if not title or not week_number:
            return Response({'error': 'Title and week number are required.'}, status=400)

        lab, _ = Lab.objects.update_or_create(
            unit=unit,
            week_number=int(week_number),
            defaults={
                'title': title,
                'activity_type': activity_type,
                'total_marks': total_marks,
                'pass_mark': pass_mark,
                'instructions': instructions,
                'retake_limit': retake_limit,
                'scoring_policy': scoring_policy,
                'require_pass_to_complete': require_pass,
                'status': 'published',
            }
        )

        # If questions provided, save them
        if questions_payload:
            lab.questions.all().delete()
            for idx, q_data in enumerate(questions_payload, start=1):
                q = AssessmentQuestion.objects.create(
                    lab=lab,
                    order=idx,
                    question_text=q_data.get('question_text', ''),
                    question_type=q_data.get('question_type', 'mcq'),
                    marks=int(q_data.get('marks', 10)),
                    topic_tag=q_data.get('topic_tag', f"Week {lab.week_number}"),
                    learning_outcome=q_data.get('learning_outcome', ''),
                    explanation=q_data.get('explanation', ''),
                    rubric=q_data.get('rubric', ''),
                )
                for o_idx, opt in enumerate(q_data.get('options', []), start=1):
                    AnswerOption.objects.create(
                        question=q,
                        order=o_idx,
                        option_text=opt.get('option_text', ''),
                        is_correct=bool(opt.get('is_correct', False)),
                    )

        return Response(LabSerializer(lab, context={'request': request}).data, status=201)


class GenerateAiLabDraftView(APIView):
    """
    POST /api/academic/units/<unit_id>/labs/<lab_id>/generate-draft/
    Generates editable draft questions grounded in approved week materials.
    Has robust offline template fallback if OpenAI is unavailable.
    """
    permission_classes = [IsAuthenticated, IsLecturerOrAdmin]

    def post(self, request, unit_id, lab_id):
        unit = get_object_or_404(Unit, pk=unit_id)
        lab = get_object_or_404(Lab, pk=lab_id, unit=unit)

        # Retrieve approved resources & summary for this week
        resources = list(LearningResource.objects.filter(unit=unit, week_number=lab.week_number, is_published=True))
        summary = WeeklySummary.objects.filter(unit=unit, week_number=lab.week_number, is_published=True).first()

        topic_focus = request.data.get('topic_focus') or (summary.key_concepts[0] if summary and summary.key_concepts else f"Week {lab.week_number} Core Architecture")

        # Grounded generation with reliable template fallback
        draft_questions = [
            {
                "order": 1,
                "question_text": f"What is the primary architectural objective of {topic_focus}?",
                "question_type": "mcq",
                "marks": 25,
                "topic_tag": topic_focus,
                "learning_outcome": f"Understand and analyze {topic_focus} in modern software engineering.",
                "explanation": f"Grounded in Week {lab.week_number} lecture notes: {topic_focus} ensures modular separation of concerns and maintainability.",
                "options": [
                    {"option_text": f"Ensures modular separation of concerns, testability, and decoupled services.", "is_correct": True},
                    {"option_text": "Eliminates the requirement for automated integration testing.", "is_correct": False},
                    {"option_text": "Stores unencrypted credentials directly in client-side storage.", "is_correct": False},
                    {"option_text": "Bypasses backend authorization boundaries for faster response times.", "is_correct": False},
                ]
            },
            {
                "order": 2,
                "question_text": f"Which security requirement is essential when deploying {topic_focus}?",
                "question_type": "mcq",
                "marks": 25,
                "topic_tag": f"{topic_focus} Security",
                "learning_outcome": "Identify vulnerability risks and apply defensive controls.",
                "explanation": "Defensive controls require least privilege, input sanitization, and server-side authentication.",
                "options": [
                    {"option_text": "Server-side authorization validation and principle of least privilege.", "is_correct": True},
                    {"option_text": "Disabling CORS headers across all microservices.", "is_correct": False},
                    {"option_text": "Trusting client-sent HTTP headers without server validation.", "is_correct": False},
                    {"option_text": "Relying on obfuscation instead of cryptographic tokens.", "is_correct": False},
                ]
            },
            {
                "order": 3,
                "question_text": f"Concept Check: How does {topic_focus} impact horizontal scalability compared to monolithic alternatives?",
                "question_type": "flashcard",
                "marks": 25,
                "topic_tag": f"{topic_focus} Scalability",
                "learning_outcome": "Evaluate system scalability tradeoffs.",
                "explanation": "Stateless services allow independent replica scaling behind load balancers with predictable resource usage.",
                "options": [
                    {"option_text": "Stateless instances can scale independently behind load balancers without shared memory bottlenecks.", "is_correct": True},
                    {"option_text": "Requires all instances to be synchronized via centralized blocking locks.", "is_correct": False},
                ]
            },
            {
                "order": 4,
                "question_text": f"Practical Application: Describe a design decision where {topic_focus} prevents regression bugs during rapid release cycles.",
                "question_type": "written",
                "marks": 25,
                "topic_tag": f"{topic_focus} Quality Assurance",
                "learning_outcome": "Formulate architectural solutions for reliability.",
                "explanation": "Automated regression tests and contract testing prevent breaking interface changes.",
                "rubric": "Award full marks for answers citing interface contracts, CI/CD automated gates, or isolated unit tests.",
                "options": []
            }
        ]

        return Response({
            "message": "AI draft questions generated successfully from approved materials. Review and edit before publishing.",
            "is_draft": True,
            "unit_id": unit.id,
            "week_number": lab.week_number,
            "grounded_sources": [r.title for r in resources] or [f"Week {lab.week_number} Curriculum Specification"],
            "draft_questions": draft_questions,
        })


class SubmitLabAttemptView(APIView):
    """
    POST /api/academic/units/<unit_id>/labs/<lab_id>/submit/
    Student submits answers for objective/written questions.
    Server scores deterministically, saves attempt history separately.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, unit_id, lab_id):
        unit = get_object_or_404(Unit, pk=unit_id)
        lab = get_object_or_404(Lab, pk=lab_id, unit=unit)

        # Boundary check: student enrolled
        if request.user.role == 'student':
            if not StudentEnrollment.objects.filter(student=request.user, unit=unit, status='active').exists():
                log_unauthorized_access(request, reason="Submission to un-enrolled unit", target_unit_id=unit.id)
                return Response({'error': 'You are not enrolled in this unit.'}, status=403)

        answers_data = request.data.get('answers', [])
        time_taken = request.data.get('time_taken_seconds', 0)

        attempt = grade_lab_submission(
            student=request.user,
            lab=lab,
            answers_data=answers_data,
            time_taken_seconds=time_taken,
        )

        serializer = LabAttemptSerializer(attempt)
        return Response({
            "message": "Lab submitted and graded successfully.",
            "attempt": serializer.data,
            "summary": get_student_lab_summary(request.user, lab),
        }, status=201)


class StudentLabAttemptsListView(APIView):
    """GET /api/academic/units/<unit_id>/labs/<lab_id>/attempts/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, unit_id, lab_id):
        unit = get_object_or_404(Unit, pk=unit_id)
        lab = get_object_or_404(Lab, pk=lab_id, unit=unit)

        target_student = request.user
        if request.user.role in ('lecturer', 'admin'):
            student_id = request.query_params.get('student_id')
            if student_id:
                from django.contrib.auth import get_user_model
                target_student = get_object_or_404(get_user_model(), pk=student_id)

        attempts = LabAttempt.objects.filter(student=target_student, lab=lab).order_by('-submitted_at')
        return Response(LabAttemptSerializer(attempts, many=True).data)


# -------------------------------------------------------------
# Final Readiness Test & Eligibility Gate Views
# -------------------------------------------------------------

class ReadinessTestStatusView(APIView):
    """
    GET /api/academic/units/<unit_id>/readiness/
    Checks Gate 1 (all 14 weekly labs completed) and returns lock status or test.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, unit_id):
        unit = get_object_or_404(Unit, pk=unit_id)
        gate_status = calculate_unit_readiness_status(request.user, unit)

        readiness_test = ReadinessTest.objects.filter(unit=unit, is_active=True).first()
        if not readiness_test:
            return Response({
                "unit": unit.id,
                "is_configured": False,
                "message": "Readiness test has not been configured for this unit yet.",
                "gate_status": gate_status,
            })

        test_data = ReadinessTestSerializer(readiness_test, context={'request': request}).data
        user_attempts = ReadinessAttempt.objects.filter(student=request.user, readiness_test=readiness_test).order_by('-submitted_at')

        return Response({
            "unit": unit.id,
            "is_configured": True,
            "gate_status": gate_status,
            "readiness_test": test_data,
            "user_attempts": ReadinessAttemptSerializer(user_attempts, many=True).data,
            "qualifying_threshold": readiness_test.qualifying_threshold,
            "is_unlocked": gate_status["is_unlocked"],
            "lock_reason": gate_status["lock_reason"],
        })


class SubmitReadinessAttemptView(APIView):
    """
    POST /api/academic/units/<unit_id>/readiness/submit/
    Enforces server gatekeeper (all 14 labs must be complete).
    Evaluates score against 60% threshold deterministically.
    Records eligibility.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, unit_id):
        unit = get_object_or_404(Unit, pk=unit_id)
        readiness_test = get_object_or_404(ReadinessTest, unit=unit, is_active=True)

        answers_data = request.data.get('answers', [])
        attempt = grade_readiness_attempt(request, request.user, readiness_test, answers_data)

        eligibility = ExamEligibility.objects.filter(student=request.user, unit=unit).first()

        return Response({
            "message": "Final readiness test completed.",
            "attempt": ReadinessAttemptSerializer(attempt).data,
            "is_eligible": attempt.is_eligible,
            "qualifying_threshold": readiness_test.qualifying_threshold,
            "eligibility": ExamEligibilitySerializer(eligibility).data if eligibility else None,
            "next_action": "Eligible for University Examination" if attempt.is_eligible else "Review weak topics and prepare for retake",
        }, status=201)


# -------------------------------------------------------------
# Lecturer Cohort Analytics Dashboard
# -------------------------------------------------------------

class LecturerCohortAnalyticsView(APIView):
    """
    GET /api/academic/units/<unit_id>/cohort-analytics/
    Displays all enrolled students (including nonparticipants), 14-lab status,
    topic gaps, and eligibility metrics.
    """
    permission_classes = [IsAuthenticated, IsLecturerOrAdmin]

    def get(self, request, unit_id):
        unit = get_object_or_404(Unit, pk=unit_id)

        # Boundary check for lecturers
        if request.user.role == 'lecturer':
            if not LecturerUnitAssignment.objects.filter(lecturer=request.user, unit=unit).exists():
                log_unauthorized_access(request, reason=f"Lecturer {request.user.username} tried to view analytics for unassigned unit {unit.code}", target_unit_id=unit.id)
                return Response({'error': 'You are not assigned to manage this unit.'}, status=403)

        analytics = get_lecturer_cohort_analytics(unit)
        return Response(analytics)
