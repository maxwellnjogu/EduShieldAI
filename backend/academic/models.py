from django.conf import settings
from django.db import models


class University(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    is_demo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Universities'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"


class Course(models.Model):
    university = models.ForeignKey(
        University,
        on_delete=models.CASCADE,
        related_name='courses'
    )
    title = models.CharField(max_length=255)
    code = models.CharField(max_length=50)
    department = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['title']
        unique_together = ('university', 'code')

    def __str__(self):
        return f"{self.title} - {self.university.code}"


class Unit(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='units'
    )
    code = models.CharField(max_length=50)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    total_weeks = models.PositiveIntegerField(default=14)
    is_primary_demo = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['code']
        unique_together = ('course', 'code')

    def __str__(self):
        return f"{self.code}: {self.title}"


class LecturerUnitAssignment(models.Model):
    lecturer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='lecturer_assignments'
    )
    unit = models.ForeignKey(
        Unit,
        on_delete=models.CASCADE,
        related_name='lecturer_assignments'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('lecturer', 'unit')

    def __str__(self):
        return f"Lecturer {self.lecturer.username} -> {self.unit.code}"


class StudentEnrollment(models.Model):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('dropped', 'Dropped'),
    )

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='enrollments'
    )
    unit = models.ForeignKey(
        Unit,
        on_delete=models.CASCADE,
        related_name='enrollments'
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    class Meta:
        unique_together = ('student', 'unit')

    def __str__(self):
        return f"Student {self.student.username} -> {self.unit.code} ({self.status})"


class LearningResource(models.Model):
    RESOURCE_TYPES = (
        ('pdf', 'PDF Document'),
        ('notes', 'Lecture Notes'),
        ('slides', 'Lecture Slides'),
        ('diagram', 'Diagram / Image'),
        ('youtube', 'YouTube Link'),
    )

    INDEXING_STATES = (
        ('pending', 'Pending'),
        ('indexed', 'Indexed'),
        ('failed', 'Failed'),
    )

    unit = models.ForeignKey(
        Unit,
        on_delete=models.CASCADE,
        related_name='resources'
    )
    week_number = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=255)
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPES, default='pdf')
    file = models.FileField(upload_to='academic_resources/', null=True, blank=True)
    external_url = models.URLField(blank=True, default='')
    uploader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    is_published = models.BooleanField(default=True)
    indexing_state = models.CharField(max_length=20, choices=INDEXING_STATES, default='indexed')
    indexing_error = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['week_number', 'created_at']

    def __str__(self):
        return f"Week {self.week_number}: {self.title} ({self.unit.code})"


class WeeklySummary(models.Model):
    unit = models.ForeignKey(
        Unit,
        on_delete=models.CASCADE,
        related_name='weekly_summaries'
    )
    week_number = models.PositiveSmallIntegerField()
    summary_text = models.TextField()
    key_concepts = models.JSONField(default=list, blank=True)
    learning_outcomes = models.JSONField(default=list, blank=True)
    is_published = models.BooleanField(default=True)
    published_at = models.DateTimeField(null=True, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('unit', 'week_number')
        ordering = ['week_number']

    def __str__(self):
        return f"{self.unit.code} - Week {self.week_number} Summary"


class ConsolidatedRevisionPack(models.Model):
    unit = models.ForeignKey(
        Unit,
        on_delete=models.CASCADE,
        related_name='revision_packs'
    )
    version = models.CharField(max_length=20, default='v1.0')
    title = models.CharField(max_length=255)
    content = models.JSONField(default=dict)
    is_published = models.BooleanField(default=True)
    published_at = models.DateTimeField(auto_now_add=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    class Meta:
        ordering = ['-published_at']

    def __str__(self):
        return f"{self.unit.code} Revision Pack {self.version}"


class Lab(models.Model):
    ACTIVITY_TYPES = (
        ('mcq', 'Multiple Choice Quiz'),
        ('flashcard', 'Flashcards'),
        ('written', 'Written Response'),
        ('mixed', 'Mixed Mode Assessment'),
    )

    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('closed', 'Closed'),
        ('archived', 'Archived'),
    )

    SCORING_POLICIES = (
        ('latest', 'Latest Attempt'),
        ('best', 'Best Attempt'),
        ('official_counted', 'Official Counted Score'),
    )

    unit = models.ForeignKey(
        Unit,
        on_delete=models.CASCADE,
        related_name='labs'
    )
    week_number = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=255)
    instructions = models.TextField(blank=True, default='')
    learning_outcomes = models.JSONField(default=list, blank=True)
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES, default='mixed')
    total_marks = models.PositiveIntegerField(default=100)
    pass_mark = models.PositiveIntegerField(default=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='published')
    deadline = models.DateTimeField(null=True, blank=True)
    time_limit_minutes = models.PositiveIntegerField(null=True, blank=True)
    retake_limit = models.PositiveIntegerField(default=3)
    scoring_policy = models.CharField(max_length=30, choices=SCORING_POLICIES, default='best')
    require_pass_to_complete = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('unit', 'week_number')
        ordering = ['week_number']

    def __str__(self):
        return f"{self.unit.code} Week {self.week_number} Lab: {self.title}"


class AssessmentQuestion(models.Model):
    QUESTION_TYPES = (
        ('mcq', 'Multiple Choice'),
        ('flashcard', 'Flashcard'),
        ('written', 'Written Response'),
    )

    lab = models.ForeignKey(
        Lab,
        on_delete=models.CASCADE,
        related_name='questions'
    )
    order = models.PositiveSmallIntegerField(default=1)
    question_text = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES, default='mcq')
    marks = models.PositiveIntegerField(default=10)
    topic_tag = models.CharField(max_length=150, blank=True, default='')
    learning_outcome = models.CharField(max_length=255, blank=True, default='')
    explanation = models.TextField(blank=True, default='')
    rubric = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Q{self.order}: {self.question_text[:50]}"


class AnswerOption(models.Model):
    question = models.ForeignKey(
        AssessmentQuestion,
        on_delete=models.CASCADE,
        related_name='options'
    )
    order = models.PositiveSmallIntegerField(default=1)
    option_text = models.TextField()
    is_correct = models.BooleanField(default=False)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{'✓' if self.is_correct else '✗'} {self.option_text[:40]}"


class LabAttempt(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='lab_attempts'
    )
    lab = models.ForeignKey(
        Lab,
        on_delete=models.CASCADE,
        related_name='attempts'
    )
    attempt_number = models.PositiveIntegerField(default=1)
    score = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    max_score = models.DecimalField(max_digits=5, decimal_places=2, default=100.0)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    is_passed = models.BooleanField(default=False)
    is_completed = models.BooleanField(default=True)
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    time_taken_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.student.username} - {self.lab.title} (Attempt #{self.attempt_number}: {self.percentage}%)"


class SubmittedAnswer(models.Model):
    attempt = models.ForeignKey(
        LabAttempt,
        on_delete=models.CASCADE,
        related_name='submitted_answers'
    )
    question = models.ForeignKey(
        AssessmentQuestion,
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    selected_option_ids = models.JSONField(default=list, blank=True)
    written_response = models.TextField(blank=True, default='')
    score_awarded = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    max_marks = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    is_correct = models.BooleanField(default=False)
    feedback = models.TextField(blank=True, default='')

    def __str__(self):
        return f"Attempt #{self.attempt.id} Q{self.question.id} ({self.score_awarded}/{self.max_marks})"


class ReadinessTest(models.Model):
    unit = models.OneToOneField(
        Unit,
        on_delete=models.CASCADE,
        related_name='readiness_test'
    )
    title = models.CharField(max_length=255)
    instructions = models.TextField(blank=True, default='')
    qualifying_threshold = models.PositiveIntegerField(default=60)
    time_limit_minutes = models.PositiveIntegerField(default=45)
    retake_limit = models.PositiveIntegerField(default=2)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.unit.code} Final Readiness Test ({self.qualifying_threshold}% required)"


class ReadinessQuestion(models.Model):
    readiness_test = models.ForeignKey(
        ReadinessTest,
        on_delete=models.CASCADE,
        related_name='questions'
    )
    order = models.PositiveSmallIntegerField(default=1)
    question_text = models.TextField()
    marks = models.PositiveIntegerField(default=10)
    topic_tag = models.CharField(max_length=150, blank=True, default='')
    learning_outcome = models.CharField(max_length=255, blank=True, default='')
    explanation = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"RQ{self.order}: {self.question_text[:50]}"


class ReadinessAnswerOption(models.Model):
    question = models.ForeignKey(
        ReadinessQuestion,
        on_delete=models.CASCADE,
        related_name='options'
    )
    order = models.PositiveSmallIntegerField(default=1)
    option_text = models.TextField()
    is_correct = models.BooleanField(default=False)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{'✓' if self.is_correct else '✗'} {self.option_text[:40]}"


class ReadinessAttempt(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='readiness_attempts'
    )
    readiness_test = models.ForeignKey(
        ReadinessTest,
        on_delete=models.CASCADE,
        related_name='attempts'
    )
    attempt_number = models.PositiveIntegerField(default=1)
    score = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    max_score = models.DecimalField(max_digits=5, decimal_places=2, default=100.0)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    is_passed = models.BooleanField(default=False)
    is_eligible = models.BooleanField(default=False)
    answers_payload = models.JSONField(default=dict)
    weak_topics_identified = models.JSONField(default=list, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.student.username} - Readiness Attempt #{self.attempt_number}: {self.percentage}% ({'Eligible' if self.is_eligible else 'Not Eligible'})"


class ExamEligibility(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='exam_eligibilities'
    )
    unit = models.ForeignKey(
        Unit,
        on_delete=models.CASCADE,
        related_name='exam_eligibilities'
    )
    is_eligible = models.BooleanField(default=False)
    readiness_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    verified_at = models.DateTimeField(auto_now=True)
    reason = models.TextField(blank=True, default='')

    class Meta:
        unique_together = ('student', 'unit')

    def __str__(self):
        return f"{self.student.username} -> {self.unit.code}: {'ELIGIBLE' if self.is_eligible else 'LOCKED'}"
