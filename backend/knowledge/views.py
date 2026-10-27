from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from security.models import SecurityEvent

from .models import Document
from .serializers import DocumentSerializer
from .services import (
    extract_pdf_text,
    chunk_text,
    create_embeddings,
    store_document_chunks,
    delete_document_chunks,
)

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB


class DocumentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'admin':
            return Response(
                {'error': 'Administrator access is required.'},
                status=status.HTTP_403_FORBIDDEN
            )
        documents = Document.objects.all().order_by('-created_at')
        return Response([
            {
                'id': d.id,
                'title': d.title,
                'created_at': d.created_at,
            }
            for d in documents
        ])


class DocumentDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, document_id):
        if request.user.role != 'admin':
            return Response(
                {'error': 'Administrator access is required.'},
                status=status.HTTP_403_FORBIDDEN
            )
        try:
            document = Document.objects.get(pk=document_id)
        except Document.DoesNotExist:
            return Response({'error': 'Document not found.'}, status=404)

        delete_document_chunks(document.id)
        document.file.delete(save=False)
        document.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class DocumentUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file = request.FILES.get('file')
        title = request.data.get('title')
        if request.user.role != 'admin':
            return Response(
                {
                    'error': 'Only administrators can upload educational material.'
                },
                status=status.HTTP_403_FORBIDDEN
            )

        if not file:
            return Response(
                {'error': 'PDF file is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if file.size > MAX_UPLOAD_BYTES:
            return Response(
                {'error': 'File is too large (20 MB maximum).'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 1. Check file extension
        if not file.name.lower().endswith('.pdf'):
            SecurityEvent.objects.create(
                user=request.user,
                event_type='malicious_upload',
                severity='MEDIUM',
                description=f'Blocked non-PDF upload: {file.name}',
                ip_address=request.META.get('REMOTE_ADDR'),
            )

            return Response(
                {'error': 'Only PDF files are supported.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. Check MIME type
        if file.content_type != 'application/pdf':
            SecurityEvent.objects.create(
                user=request.user,
                event_type='malicious_upload',
                severity='HIGH',
                description=(
                    f'Blocked upload with invalid MIME type: '
                    f'{file.name} ({file.content_type})'
                ),
                ip_address=request.META.get('REMOTE_ADDR'),
            )

            return Response(
                {'error': 'Invalid PDF MIME type.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 3. Check actual PDF file signature
        file.seek(0)
        header = file.read(5)
        file.seek(0)

        if header != b'%PDF-':
            SecurityEvent.objects.create(
                user=request.user,
                event_type='malicious_upload',
                severity='HIGH',
                description=(
                    f'Blocked file pretending to be a PDF: {file.name}'
                ),
                ip_address=request.META.get('REMOTE_ADDR'),
            )

            return Response(
                {'error': 'File is not a valid PDF.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 4. Save the document
        document = Document.objects.create(
            title=title or file.name,
            file=file,
            uploaded_by=request.user
        )

        # 5. Extract text
        text = extract_pdf_text(document.file.path)

        if not text.strip():
            document.delete()

            return Response(
                {'error': 'Could not extract text from PDF.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 6. Create chunks
        chunks = chunk_text(text)

        # 7. Create local embeddings
        embeddings = create_embeddings(chunks)

        # 8. Store chunks in ChromaDB
        store_document_chunks(
            document.id,
            chunks,
            embeddings,
            title=document.title,
        )

        return Response(
            {
                'message': 'Document uploaded successfully.',
                'document_id': document.id,
                'title': document.title,
                'chunks_created': len(chunks),
            },
            status=status.HTTP_201_CREATED
        )