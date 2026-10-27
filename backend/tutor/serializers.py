from rest_framework import serializers
from .models import TutorConversation


class TutorConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = TutorConversation
        fields = [
            'id',
            'question',
            'answer',
            'sources',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']
