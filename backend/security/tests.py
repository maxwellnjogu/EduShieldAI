from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from .models import SecurityEvent, IPBlocklist, Incident

User = get_user_model()


class IncidentResponseTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='sec_admin', password='pw-12345-xyz', role='admin')
        self.student = User.objects.create_user(username='student_user', password='pw-12345-xyz', role='student')
        self.event = SecurityEvent.objects.create(
            event_type='prompt_injection',
            severity='HIGH',
            description='Test injection attack',
            ip_address='198.51.100.22',
            endpoint='/api/tutor/ask/',
        )

    def test_flag_event_requires_admin(self):
        self.client.force_authenticate(self.student)
        res = self.client.post(f'/api/security/events/{self.event.id}/flag/', {'note': 'Suspicious'})
        self.assertEqual(res.status_code, 403)

    def test_flag_event_and_create_incident(self):
        self.client.force_authenticate(self.admin)
        res = self.client.post(f'/api/security/events/{self.event.id}/flag/', {
            'note': 'Reviewed prompt pattern, clearly adversarial.',
            'create_incident': True,
        })
        self.assertEqual(res.status_code, 200)
        self.event.refresh_from_db()
        self.assertTrue(self.event.metadata.get('flagged'))
        self.assertEqual(len(self.event.metadata.get('analyst_notes', [])), 1)

        # Check created incident
        incident = Incident.objects.get(related_events=self.event)
        self.assertEqual(incident.status, 'INVESTIGATING')
        self.assertEqual(incident.severity, 'HIGH')
        self.assertEqual(incident.source_ip, '198.51.100.22')

    def test_block_ip_and_middleware_rejection(self):
        self.client.force_authenticate(self.admin)
        # Block IP
        res = self.client.post('/api/security/ip-blocks/', {
            'ip_address': '198.51.100.22',
            'reason': 'Repeated prompt injection',
        })
        self.assertEqual(res.status_code, 201)
        self.assertTrue(IPBlocklist.objects.filter(ip_address='198.51.100.22', is_active=True).exists())

        # Test middleware blocking for that IP
        client_blocked = self.client_class(REMOTE_ADDR='198.51.100.22')
        req = client_blocked.get('/api/security/stats/')
        self.assertEqual(req.status_code, 403)
        self.assertIn('blocked by EduShield', req.json().get('error', ''))

    def test_self_block_safeguard(self):
        self.client.force_authenticate(self.admin)
        # Try to block own IP (127.0.0.1 by default in APITestCase)
        res = self.client.post('/api/security/ip-blocks/', {
            'ip_address': '127.0.0.1',
            'reason': 'Self block test',
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn('Safety block prevented', res.json().get('error', ''))

    def test_escalate_and_resolve_incident_lifecycle(self):
        self.client.force_authenticate(self.admin)
        # Create incident
        inc_res = self.client.post('/api/security/incidents/', {
            'title': 'Investigate brute force',
            'severity': 'HIGH',
            'source_ip': '198.51.100.33',
            'analyst_notes': 'Initial triage notes',
            'event_ids': [self.event.id],
        })
        self.assertEqual(inc_res.status_code, 201)
        inc_id = inc_res.json()['id']

        # Escalate to L2
        esc_res = self.client.post(f'/api/security/incidents/{inc_id}/escalate/', {
            'reason': 'Advanced evasion technique detected across multiple sessions.',
        })
        self.assertEqual(esc_res.status_code, 200)
        self.assertEqual(esc_res.json()['status'], 'ESCALATED_L2')

        # Resolve incident
        resolve_res = self.client.post(f'/api/security/incidents/{inc_id}/resolve/', {
            'resolution_notes': 'WAF rules tuned and attacker IP confirmed isolated.',
        })
        self.assertEqual(resolve_res.status_code, 200)
        self.assertEqual(resolve_res.json()['status'], 'RESOLVED')

        # Related security event should be marked resolved
        self.event.refresh_from_db()
        self.assertTrue(self.event.is_resolved)
