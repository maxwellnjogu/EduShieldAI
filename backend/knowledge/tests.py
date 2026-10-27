from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase
from rest_framework.test import APITestCase

from knowledge.services import chunk_text

User = get_user_model()


class ChunkingTests(SimpleTestCase):
    def test_empty_text(self):
        self.assertEqual(chunk_text("  \n "), [])

    def test_respects_size_and_keeps_all_sentences(self):
        text = " ".join(f"This is sentence number {i}." for i in range(200))
        chunks = chunk_text(text, chunk_size=300, overlap=50)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c) <= 300 for c in chunks))
        joined = " ".join(chunks)
        for i in (0, 100, 199):
            self.assertIn(f"sentence number {i}.", joined)

    def test_long_unbroken_text_is_split(self):
        chunks = chunk_text("x" * 2500, chunk_size=1000, overlap=100)
        self.assertTrue(all(len(c) <= 1000 for c in chunks))


class DocumentAccessTests(APITestCase):
    def setUp(self):
        self.student = User.objects.create_user('s', password='pw-12345-xyz')

    def test_student_cannot_list_or_delete(self):
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get('/api/knowledge/documents/').status_code, 403)
        self.assertEqual(self.client.delete('/api/knowledge/documents/1/').status_code, 403)


class TutorAnswerTests(SimpleTestCase):
    def test_not_found_when_nothing_relevant(self):
        from tutor.services import generate_tutor_answer, NOT_FOUND_MESSAGE
        with patch('tutor.services.search_knowledge', return_value=[]):
            answer, sources = generate_tutor_answer('anything')
        self.assertEqual(answer, NOT_FOUND_MESSAGE)
        self.assertEqual(sources, [])

    def test_sources_deduplicated(self):
        from tutor.services import generate_tutor_answer
        hits = [
            {'text': 'a', 'metadata': {'document_id': 1, 'title': 'T'}, 'score': 0.9},
            {'text': 'b', 'metadata': {'document_id': 1, 'title': 'T'}, 'score': 0.8},
        ]
        with patch('tutor.services.search_knowledge', return_value=hits):
            _, sources = generate_tutor_answer('q')
        self.assertEqual(len(sources), 1)
