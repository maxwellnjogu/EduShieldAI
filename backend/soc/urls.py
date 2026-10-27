from django.urls import path

from .views import (
    BulkResolveView,
    EventDetailView,
    EventListView,
    ResolveEventView,
    SocSummaryView,
)

urlpatterns = [
    path('summary/', SocSummaryView.as_view(), name='soc-summary'),
    path('events/', EventListView.as_view(), name='soc-events'),
    path('events/bulk-resolve/', BulkResolveView.as_view(), name='soc-bulk-resolve'),
    path('events/<int:event_id>/', EventDetailView.as_view(), name='soc-event-detail'),
    path('events/<int:event_id>/resolve/', ResolveEventView.as_view(), name='soc-resolve-event'),
]