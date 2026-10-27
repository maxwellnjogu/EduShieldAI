from django.urls import path
from .views import (
    UniversityListView,
    CourseListView,
    UnitListView,
    EnrolledUnitsView,
    EnrollStudentView,
    UnitResourcesView,
    UnitSummariesView,
    ConsolidatedRevisionPackView,
    StudentWeaknessRecommendationsView,
    UnitLabsView,
    GenerateAiLabDraftView,
    SubmitLabAttemptView,
    StudentLabAttemptsListView,
    ReadinessTestStatusView,
    SubmitReadinessAttemptView,
    LecturerCohortAnalyticsView,
)

urlpatterns = [
    # Catalog & Enrollment
    path('universities/', UniversityListView.as_view(), name='universities_list'),
    path('courses/', CourseListView.as_view(), name='courses_list'),
    path('units/', UnitListView.as_view(), name='units_list'),
    path('units/enrolled/', EnrolledUnitsView.as_view(), name='enrolled_units'),
    path('units/<int:unit_id>/enroll/', EnrollStudentView.as_view(), name='enroll_student'),

    # 14-Week Learning Resources & Summaries
    path('units/<int:unit_id>/resources/', UnitResourcesView.as_view(), name='unit_resources'),
    path('units/<int:unit_id>/summaries/', UnitSummariesView.as_view(), name='unit_summaries'),
    path('units/<int:unit_id>/revision-pack/', ConsolidatedRevisionPackView.as_view(), name='revision_pack'),
    path('units/<int:unit_id>/revision-pack/publish/', ConsolidatedRevisionPackView.as_view(), name='publish_revision_pack'),
    path('units/<int:unit_id>/weaknesses/', StudentWeaknessRecommendationsView.as_view(), name='student_weaknesses'),

    # Labs & Assessment Builder
    path('units/<int:unit_id>/labs/', UnitLabsView.as_view(), name='unit_labs'),
    path('units/<int:unit_id>/labs/<int:lab_id>/generate-draft/', GenerateAiLabDraftView.as_view(), name='generate_lab_draft'),
    path('units/<int:unit_id>/labs/<int:lab_id>/submit/', SubmitLabAttemptView.as_view(), name='submit_lab_attempt'),
    path('units/<int:unit_id>/labs/<int:lab_id>/attempts/', StudentLabAttemptsListView.as_view(), name='student_lab_attempts'),

    # Final Readiness Test & Gate
    path('units/<int:unit_id>/readiness/', ReadinessTestStatusView.as_view(), name='readiness_status'),
    path('units/<int:unit_id>/readiness/submit/', SubmitReadinessAttemptView.as_view(), name='submit_readiness'),

    # Lecturer Cohort Dashboard
    path('units/<int:unit_id>/cohort-analytics/', LecturerCohortAnalyticsView.as_view(), name='cohort_analytics'),
]
