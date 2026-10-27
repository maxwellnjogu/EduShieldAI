from decimal import Decimal
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from academic.models import (
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
from security.models import SecurityEvent

User = get_user_model()


class AcademicBaseTestCase(APITestCase):
    def setUp(self):
        # Users
        self.admin = User.objects.create_user(username='admin_u', password='password123', role='admin')
        self.lecturer1 = User.objects.create_user(username='lecturer1', password='password123', role='lecturer')
        self.lecturer2 = User.objects.create_user(username='lecturer2', password='password123', role='lecturer')
        self.student1 = User.objects.create_user(username='student1', password='password123', role='student')
        self.student2 = User.objects.create_user(username='student2', password='password123', role='student')

        # Catalog
        self.uni = University.objects.create(name='Riara University', code='RU', is_demo=True)
        self.course = Course.objects.create(university=self.uni, title='Software Engineering', code='BSSE')
        self.unit = Unit.objects.create(course=self.course, code='SE301', title='Software Engineering', total_weeks=14, is_primary_demo=True)
        self.other_unit = Unit.objects.create(course=self.course, code='SE302', title='Advanced Database Systems', total_weeks=14)

        # Lecturer assignment
        LecturerUnitAssignment.objects.create(lecturer=self.lecturer1, unit=self.unit)
        LecturerUnitAssignment.objects.create(lecturer=self.lecturer2, unit=self.other_unit)

        # Student enrollment
        StudentEnrollment.objects.create(student=self.student1, unit=self.unit, status='active')
        StudentEnrollment.objects.create(student=self.student2, unit=self.unit, status='active')

        # Create 14 labs for self.unit
        self.labs = []
        for w in range(1, 15):
            lab = Lab.objects.create(
                unit=self.unit,
                week_number=w,
                title=f"Week {w} Lab",
                pass_mark=50,
                total_marks=100,
                status='published',
            )
            q = AssessmentQuestion.objects.create(
                lab=lab,
                order=1,
                question_text=f"Question for Week {w}",
                marks=100,
                topic_tag=f"Topic Week {w}",
            )
            AnswerOption.objects.create(question=q, order=1, option_text="Correct Option", is_correct=True)
            AnswerOption.objects.create(question=q, order=2, option_text="Incorrect Option", is_correct=False)
            self.labs.append(lab)

        # Readiness Test
        self.readiness_test = ReadinessTest.objects.create(
            unit=self.unit,
            title='SE301 Readiness Test',
            qualifying_threshold=60,
            is_active=True,
        )
        for i in range(1, 11):
            rq = ReadinessQuestion.objects.create(
                readiness_test=self.readiness_test,
                order=i,
                question_text=f"Readiness Q{i}",
                marks=10,
                topic_tag=f"Readiness Topic {i}",
            )
            ReadinessAnswerOption.objects.create(question=rq, order=1, option_text="Correct", is_correct=True)
            ReadinessAnswerOption.objects.create(question=rq, order=2, option_text="Wrong", is_correct=False)


class CatalogAndBoundaryTests(AcademicBaseTestCase):
    def test_student_catalog_and_enrolled_units(self):
        self.client.force_authenticate(self.student1)
        res = self.client.get('/api/academic/units/enrolled/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['code'], 'SE301')

    def test_student_cannot_access_unenrolled_unit_resources(self):
        self.client.force_authenticate(self.student1)
        # student1 is not enrolled in other_unit (SE302)
        res = self.client.get(f'/api/academic/units/{self.other_unit.id}/resources/')
        self.assertEqual(res.status_code, 403)
        self.assertIn('not enrolled', res.json()['error'])
        # SOC security event was generated
        self.assertTrue(SecurityEvent.objects.filter(event_type='unauthorized_access').exists())

    def test_lecturer_cannot_manage_unassigned_unit(self):
        self.client.force_authenticate(self.lecturer1)
        # lecturer1 is not assigned to other_unit
        res = self.client.get(f'/api/academic/units/{self.other_unit.id}/cohort-analytics/')
        self.assertEqual(res.status_code, 403)
        self.assertTrue(SecurityEvent.objects.filter(event_type='unauthorized_access').exists())


class LabExecutionAndAttemptRetentionTests(AcademicBaseTestCase):
    def test_submit_lab_scores_server_side_and_retains_history(self):
        self.client.force_authenticate(self.student1)
        lab1 = self.labs[0]
        q1 = lab1.questions.first()
        correct_opt = q1.options.get(is_correct=True)
        wrong_opt = q1.options.get(is_correct=False)

        # Attempt 1: Wrong answer
        res1 = self.client.post(f'/api/academic/units/{self.unit.id}/labs/{lab1.id}/submit/', {
            'answers': [{'question_id': q1.id, 'selected_option_ids': [wrong_opt.id]}],
            'time_taken_seconds': 120,
        }, format='json')
        self.assertEqual(res1.status_code, 201)
        self.assertEqual(res1.json()['attempt']['attempt_number'], 1)
        self.assertEqual(float(res1.json()['attempt']['percentage']), 0.0)

        # Attempt 2: Correct answer
        res2 = self.client.post(f'/api/academic/units/{self.unit.id}/labs/{lab1.id}/submit/', {
            'answers': [{'question_id': q1.id, 'selected_option_ids': [correct_opt.id]}],
            'time_taken_seconds': 150,
        }, format='json')
        self.assertEqual(res2.status_code, 201)
        self.assertEqual(res2.json()['attempt']['attempt_number'], 2)
        self.assertEqual(float(res2.json()['attempt']['percentage']), 100.0)

        # Verify historical attempts are NOT overwritten
        attempts = LabAttempt.objects.filter(student=self.student1, lab=lab1).order_by('attempt_number')
        self.assertEqual(attempts.count(), 2)
        self.assertEqual(attempts[0].attempt_number, 1)
        self.assertEqual(float(attempts[0].percentage), 0.0)
        self.assertEqual(attempts[1].attempt_number, 2)
        self.assertEqual(float(attempts[1].percentage), 100.0)


class ReadinessGatekeeperTests(AcademicBaseTestCase):
    def test_readiness_test_locked_when_labs_incomplete(self):
        self.client.force_authenticate(self.student1)
        # Student 1 has not completed any lab yet
        status_res = self.client.get(f'/api/academic/units/{self.unit.id}/readiness/')
        self.assertEqual(status_res.status_code, 200)
        self.assertFalse(status_res.json()['is_unlocked'])
        self.assertIn('Readiness exam locked', status_res.json()['lock_reason'])

        # Attempting direct submit should be blocked by backend gatekeeper with 403
        direct_res = self.client.post(f'/api/academic/units/{self.unit.id}/readiness/submit/', {
            'answers': []
        }, format='json')
        self.assertEqual(direct_res.status_code, 403)
        # SOC security event created
        self.assertTrue(SecurityEvent.objects.filter(event_type='unauthorized_access').exists())

    def test_readiness_test_unlocked_after_all_14_labs_completed(self):
        self.client.force_authenticate(self.student1)
        # Complete all 14 labs
        for lab in self.labs:
            q = lab.questions.first()
            correct_opt = q.options.get(is_correct=True)
            self.client.post(f'/api/academic/units/{self.unit.id}/labs/{lab.id}/submit/', {
                'answers': [{'question_id': q.id, 'selected_option_ids': [correct_opt.id]}],
            }, format='json')

        # Readiness is now UNLOCKED!
        status_res = self.client.get(f'/api/academic/units/{self.unit.id}/readiness/')
        self.assertEqual(status_res.status_code, 200)
        self.assertTrue(status_res.json()['is_unlocked'])

        # Submit readiness test answers (6 out of 10 correct = 60% -> Pass!)
        answers = []
        for idx, rq in enumerate(self.readiness_test.questions.all(), start=1):
            if idx <= 6:
                corr = rq.options.get(is_correct=True)
                answers.append({'question_id': rq.id, 'selected_option_ids': [corr.id]})
            else:
                wrong = rq.options.get(is_correct=False)
                answers.append({'question_id': rq.id, 'selected_option_ids': [wrong.id]})

        submit_res = self.client.post(f'/api/academic/units/{self.unit.id}/readiness/submit/', {
            'answers': answers
        }, format='json')
        self.assertEqual(submit_res.status_code, 201)
        self.assertTrue(submit_res.json()['is_eligible'])
        self.assertEqual(float(submit_res.json()['attempt']['percentage']), 60.0)

        # Check ExamEligibility database record
        elig = ExamEligibility.objects.get(student=self.student1, unit=self.unit)
        self.assertTrue(elig.is_eligible)
        self.assertEqual(float(elig.readiness_score), 60.0)


class LecturerCohortAnalyticsTests(AcademicBaseTestCase):
    def test_analytics_includes_all_enrolled_and_nonparticipants(self):
        self.client.force_authenticate(self.lecturer1)
        # student1 completes 1 lab; student2 has 0 labs (nonparticipant)
        lab1 = self.labs[0]
        q = lab1.questions.first()
        corr = q.options.get(is_correct=True)
        LabAttempt.objects.create(
            student=self.student1,
            lab=lab1,
            attempt_number=1,
            score=Decimal("100.0"),
            max_score=Decimal("100.0"),
            percentage=Decimal("100.0"),
            is_passed=True,
            is_completed=True,
        )

        res = self.client.get(f'/api/academic/units/{self.unit.id}/cohort-analytics/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['total_enrolled'], 2)
        self.assertEqual(data['active_participants'], 1)
        self.assertEqual(data['nonparticipants_count'], 1)
        # Both students appear in roster
        usernames = [s['username'] for s in data['students']]
        self.assertIn('student1', usernames)
        self.assertIn('student2', usernames)
