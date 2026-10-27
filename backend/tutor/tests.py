from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from tutor.llm import build_prompt, generate_with_llm

HITS = [{'text': 'Passage', 'metadata': {'document_id': 1, 'title': 'T'}, 'score': 0.9}]


class LlmTests(SimpleTestCase):
    def test_prompt_numbers_excerpts(self):
        prompt = build_prompt('What?', ['one', 'two'])
        self.assertIn('[1] one', prompt)
        self.assertIn('[2] two', prompt)

    def test_returns_none_when_ollama_down(self):
        with patch('tutor.llm.urllib.request.urlopen', side_effect=OSError('down')):
            self.assertIsNone(generate_with_llm('q', ['p']))

    def test_service_uses_llm_answer(self):
        from tutor.services import generate_tutor_answer
        with patch('tutor.services.search_knowledge', return_value=HITS), \
             patch('tutor.services.generate_with_llm', return_value='LLM says hi'):
            answer, sources = generate_tutor_answer('q')
        self.assertEqual(answer, 'LLM says hi')
        self.assertEqual(len(sources), 1)

    def test_service_falls_back_to_passages(self):
        from tutor.services import generate_tutor_answer
        with patch('tutor.services.search_knowledge', return_value=HITS), \
             patch('tutor.services.generate_with_llm', return_value=None):
            answer, _ = generate_tutor_answer('q')
        self.assertIn('Passage', answer)

    def test_gemini_answer_used_and_key_sent_in_header_only(self):
        import io
        import json
        body = {'candidates': [{'content': {'parts': [{'text': 'Gemini says hi'}]}}]}
        fake = io.BytesIO(json.dumps(body).encode())
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key-123'}), \
             patch('tutor.llm.urllib.request.urlopen') as urlopen:
            urlopen.return_value.__enter__.return_value = fake
            answer = generate_with_llm('q', ['p'])
        self.assertEqual(answer, 'Gemini says hi')
        request = urlopen.call_args[0][0]
        self.assertNotIn('test-key-123', request.full_url)
        self.assertEqual(request.get_header('X-goog-api-key'), 'test-key-123')

    def test_gemini_failure_falls_back_to_none_when_ollama_down(self):
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key-123'}), \
             patch('tutor.llm.urllib.request.urlopen', side_effect=OSError('down')):
            self.assertIsNone(generate_with_llm('q', ['p']))

    def test_gemini_skipped_without_key(self):
        from tutor.llm import _generate_with_gemini
        with patch.dict('os.environ', {}, clear=True), \
             patch('tutor.llm.urllib.request.urlopen') as urlopen:
            self.assertIsNone(_generate_with_gemini([]))
        urlopen.assert_not_called()


class TutorSocLoggingTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        self.user = get_user_model().objects.create_user(username='stu', password='pw-12345-xyz')
        token = RefreshToken.for_user(self.user).access_token
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_question_creates_soc_event_and_attributes_api_log(self):
        from security.models import APIRequestLog, SecurityEvent
        with patch('tutor.views.generate_tutor_answer', return_value=('A', [])):
            res = self.client.post('/api/tutor/ask/', {'question': 'What is TCP?'}, format='json')
        self.assertEqual(res.status_code, 200)

        event = SecurityEvent.objects.get(event_type='tutor_question')
        self.assertEqual(event.severity, 'LOW')
        self.assertTrue(event.is_informational)
        self.assertFalse(event.is_resolved)
        self.assertEqual(event.user, self.user)

        log = APIRequestLog.objects.get(endpoint='/api/tutor/ask/')
        self.assertEqual(log.user, self.user)

    def test_get_conversations_and_clear(self):
        from tutor.models import TutorConversation
        TutorConversation.objects.create(user=self.user, question='Q1', answer='A1', sources=[{'title': 'Doc 1'}])
        TutorConversation.objects.create(user=self.user, question='Q2', answer='A2', sources=[])

        res = self.client.get('/api/tutor/conversations/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 2)
        self.assertEqual(res.data[0]['question'], 'Q1')
        self.assertEqual(res.data[0]['sources'][0]['title'], 'Doc 1')

        del_res = self.client.delete('/api/tutor/conversations/clear/')
        self.assertEqual(del_res.status_code, 200)
        self.assertEqual(TutorConversation.objects.filter(user=self.user).count(), 0)



