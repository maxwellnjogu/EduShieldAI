from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import TutorConversation
from .serializers import TutorConversationSerializer
from .services import generate_tutor_answer

from security.detectors.prompt_injection import detect_prompt_injection
from security.services import create_security_event


class AskTutorView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        question = (request.data.get('question') or '').strip()

        if not question:
            return Response(
                {'error': 'Question is required.'},
                status=400
            )

        # Security: detect prompt injection
        if detect_prompt_injection(question):
            create_security_event(
                event_type="prompt_injection",
                severity="HIGH",
                description="Possible prompt injection attempt detected",
                user=request.user,
                endpoint=request.path,
                request=request,
                metadata={
                    "question": question[:500]
                }
            )

            return Response(
                {
                    "error": "Potentially malicious request detected."
                },
                status=403
            )

        # Retrieve recent conversation turns for context
        recent_turns = list(
            TutorConversation.objects.filter(user=request.user)
            .order_by('-created_at')[:4]
            .values('question', 'answer')
        )
        recent_turns.reverse()

        # Generate AI response with history context
        answer, sources = generate_tutor_answer(question, history=recent_turns)

        # Save conversation including sources
        conversation = TutorConversation.objects.create(
            user=request.user,
            question=question,
            answer=answer,
            sources=sources,
        )

        # Security: record the question so the SOC has visibility
        create_security_event(
            event_type="tutor_question",
            severity="LOW",
            description=f"Tutor question: {question[:120]}",
            user=request.user,
            endpoint=request.path,
            request=request,
            metadata={
                "conversation_id": conversation.id,
                "question": question[:500],
                "sources": len(sources),
            },
            is_informational=True,
        )

        return Response(TutorConversationSerializer(conversation).data, status=200)


class ConversationListView(APIView):
    """
    GET /api/tutor/conversations/
    Returns the student's conversation history in chronological order.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Fetch the last 100 turns in ascending order for seamless chat thread rendering
        conversations = list(
            TutorConversation.objects.filter(user=request.user)
            .order_by('-created_at')[:100]
        )
        conversations.reverse()
        return Response(TutorConversationSerializer(conversations, many=True).data)


class ConversationDetailView(APIView):
    """
    DELETE /api/tutor/conversations/<id>/
    Delete a specific conversation turn.
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        conversation = get_object_or_404(TutorConversation, pk=pk, user=request.user)
        conversation.delete()
        return Response({'message': 'Conversation deleted.'})


class ConversationClearView(APIView):
    """
    DELETE /api/tutor/conversations/clear/
    Clears all conversation history for the current user.
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        count, _ = TutorConversation.objects.filter(user=request.user).delete()
        return Response({'message': f'Cleared {count} conversations.'})