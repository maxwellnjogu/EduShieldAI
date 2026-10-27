from django.urls import path

from .views import (
    SecurityEventListView,
    APIRequestLogListView,
    SecurityStatsView,
    FlagEventView,
    IPBlocklistView,
    IPBlockDetailView,
    IncidentListCreateView,
    IncidentDetailView,
    IncidentEscalateView,
    IncidentResolveView,
)

urlpatterns = [
    path('events/', SecurityEventListView.as_view(), name='security-events'),
    path('events/<int:event_id>/flag/', FlagEventView.as_view(), name='security-event-flag'),
    path('api-logs/', APIRequestLogListView.as_view(), name='api-logs'),
    path('stats/', SecurityStatsView.as_view(), name='security-stats'),
    path('ip-blocks/', IPBlocklistView.as_view(), name='ip-blocks'),
    path('ip-blocks/<int:pk>/', IPBlockDetailView.as_view(), name='ip-block-detail'),
    path('incidents/', IncidentListCreateView.as_view(), name='incidents'),
    path('incidents/<int:pk>/', IncidentDetailView.as_view(), name='incident-detail'),
    path('incidents/<int:pk>/escalate/', IncidentEscalateView.as_view(), name='incident-escalate'),
    path('incidents/<int:pk>/resolve/', IncidentResolveView.as_view(), name='incident-resolve'),
]