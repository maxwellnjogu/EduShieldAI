from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from security.models import SecurityEvent
from security.services import MAX_FAILED_ATTEMPTS, detect_brute_force

User = get_user_model()


class SocApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin1', password='pw-12345-xyz', role='admin')
        self.student = User.objects.create_user('stud1', password='pw-12345-xyz', role='student')
        self.event = SecurityEvent.objects.create(
            event_type='prompt_injection', severity='HIGH',
            description='test', ip_address='10.0.0.1',
        )

    def test_summary_requires_admin(self):
        self.assertEqual(self.client.get('/api/soc/summary/').status_code, 401)
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get('/api/soc/summary/').status_code, 403)

    def test_summary_for_admin(self):
        self.client.force_authenticate(self.admin)
        data = self.client.get('/api/soc/summary/').json()
        self.assertEqual(data['events_last_24h'], 1)
        self.assertEqual(data['open_events'], 1)
        self.assertEqual(data['top_ips'][0]['ip_address'], '10.0.0.1')

    def test_resolve_event(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'/api/soc/events/{self.event.id}/resolve/', {})
        self.assertEqual(r.status_code, 200)
        self.event.refresh_from_db()
        self.assertTrue(self.event.is_resolved)

    def test_student_cannot_resolve(self):
        self.client.force_authenticate(self.student)
        r = self.client.post(f'/api/soc/events/{self.event.id}/resolve/', {})
        self.assertEqual(r.status_code, 403)

    def test_stats_counts_severity(self):
        self.client.force_authenticate(self.admin)
        data = self.client.get('/api/security/stats/').json()
        self.assertEqual(data['severity']['high'], 1)

    def test_summary_has_breakdowns(self):
        self.client.force_authenticate(self.admin)
        data = self.client.get('/api/soc/summary/').json()
        self.assertEqual(data['by_severity'], {'HIGH': 1})
        self.assertEqual(data['by_type'], {'prompt_injection': 1})
        self.assertIn('top_endpoints', data)


class SocEventListTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin2', password='pw-12345-xyz', role='admin')
        self.student = User.objects.create_user('stud2', password='pw-12345-xyz', role='student')
        for i in range(5):
            SecurityEvent.objects.create(
                event_type='prompt_injection', severity='LOW',
                description=f'low {i}', ip_address='10.0.0.2',
            )
        self.high = SecurityEvent.objects.create(
            event_type='suspicious_login', severity='HIGH',
            description='brute force', ip_address='10.0.0.3',
            metadata={'attempts': 5},
        )

    def test_requires_admin(self):
        self.assertEqual(self.client.get('/api/soc/events/').status_code, 401)
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get('/api/soc/events/').status_code, 403)
        self.assertEqual(self.client.get(f'/api/soc/events/{self.high.id}/').status_code, 403)
        r = self.client.post('/api/soc/events/bulk-resolve/', {'ids': [self.high.id]}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_filters(self):
        self.client.force_authenticate(self.admin)
        data = self.client.get('/api/soc/events/?severity=high').json()
        self.assertEqual(data['count'], 1)
        data = self.client.get('/api/soc/events/?event_type=prompt_injection').json()
        self.assertEqual(data['count'], 5)
        data = self.client.get('/api/soc/events/?ip=10.0.0.3').json()
        self.assertEqual(data['results'][0]['id'], self.high.id)
        data = self.client.get('/api/soc/events/?search=brute').json()
        self.assertEqual(data['count'], 1)
        data = self.client.get('/api/soc/events/?is_resolved=false').json()
        self.assertEqual(data['count'], 6)

    def test_pagination(self):
        self.client.force_authenticate(self.admin)
        data = self.client.get('/api/soc/events/?limit=2&offset=1').json()
        self.assertEqual(data['count'], 6)
        self.assertEqual(len(data['results']), 2)
        self.assertEqual(data['offset'], 1)
        data = self.client.get('/api/soc/events/?limit=99999').json()
        self.assertEqual(data['limit'], 200)

    def test_invalid_params_rejected(self):
        self.client.force_authenticate(self.admin)
        for qs in ('severity=bogus', 'event_type=bogus', 'is_resolved=maybe',
                   'since=notadate', 'limit=abc'):
            self.assertEqual(self.client.get(f'/api/soc/events/?{qs}').status_code, 400, qs)

    def test_detail_includes_metadata(self):
        self.client.force_authenticate(self.admin)
        data = self.client.get(f'/api/soc/events/{self.high.id}/').json()
        self.assertEqual(data['metadata'], {'attempts': 5})
        self.assertEqual(self.client.get('/api/soc/events/999999/').status_code, 404)

    def test_bulk_resolve(self):
        self.client.force_authenticate(self.admin)
        ids = list(SecurityEvent.objects.values_list('id', flat=True))
        r = self.client.post('/api/soc/events/bulk-resolve/', {'ids': ids}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['updated'], 6)
        self.assertFalse(SecurityEvent.objects.filter(is_resolved=False).exists())

    def test_bulk_resolve_validation(self):
        self.client.force_authenticate(self.admin)
        for body in ({}, {'ids': []}, {'ids': 'x'}, {'ids': ['a']}, {'ids': [True]},
                     {'ids': list(range(501))}):
            r = self.client.post('/api/soc/events/bulk-resolve/', body, format='json')
            self.assertEqual(r.status_code, 400, body)

    def test_reopen_with_string_false(self):
        self.client.force_authenticate(self.admin)
        self.client.post(f'/api/soc/events/{self.high.id}/resolve/', {})
        r = self.client.post(f'/api/soc/events/{self.high.id}/resolve/', {'is_resolved': 'false'})
        self.assertEqual(r.status_code, 200)
        self.high.refresh_from_db()
        self.assertFalse(self.high.is_resolved)
        r = self.client.post(f'/api/soc/events/{self.high.id}/resolve/', {'is_resolved': 'junk'})
        self.assertEqual(r.status_code, 400)


class BruteForceTests(APITestCase):
    def test_repeated_failed_logins_raise_alert(self):
        User.objects.create_user('bob', password='right-pass-123')
        for _ in range(MAX_FAILED_ATTEMPTS):
            self.client.post('/api/auth/login/', {'username': 'bob', 'password': 'wrong'})
        self.assertTrue(SecurityEvent.objects.filter(severity='HIGH', event_type='suspicious_login').exists())
        self.assertTrue(detect_brute_force('127.0.0.1'))
