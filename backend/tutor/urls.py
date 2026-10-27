from django.urls import path
from .views import (
    AskTutorView,
    ConversationClearView,
    ConversationDetailView,
    ConversationListView,
)

urlpatterns = [
    path('ask/', AskTutorView.as_view(), name='ask-tutor'),
    path('conversations/', ConversationListView.as_view(), name='tutor-conversations'),
    path('conversations/<int:pk>/', ConversationDetailView.as_view(), name='tutor-conversation-detail'),
    path('conversations/clear/', ConversationClearView.as_view(), name='tutor-conversations-clear'),
]