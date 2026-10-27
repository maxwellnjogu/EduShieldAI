from django.urls import path

from .views import DocumentDeleteView, DocumentListView, DocumentUploadView


urlpatterns = [
    path(
        'upload/',
        DocumentUploadView.as_view(),
        name='document-upload'
    ),
    path(
        'documents/',
        DocumentListView.as_view(),
        name='document-list'
    ),
    path(
        'documents/<int:document_id>/',
        DocumentDeleteView.as_view(),
        name='document-delete'
    ),
]