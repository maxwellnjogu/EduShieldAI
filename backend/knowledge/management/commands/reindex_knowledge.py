from django.core.management.base import BaseCommand

from knowledge.models import Document
from knowledge.services import (
    chunk_text,
    create_embeddings,
    delete_document_chunks,
    extract_pdf_text,
    store_document_chunks,
)


class Command(BaseCommand):
    help = "Re-extract, re-chunk and re-embed every stored document."

    def handle(self, *args, **options):
        for document in Document.objects.all():
            try:
                text = extract_pdf_text(document.file.path)
            except Exception as exc:
                self.stderr.write(f"Skipping {document.id} ({document.title}): {exc}")
                continue

            chunks = chunk_text(text)
            if not chunks:
                self.stderr.write(f"No text in {document.id} ({document.title})")
                continue

            delete_document_chunks(document.id)
            store_document_chunks(
                document.id, chunks, create_embeddings(chunks), title=document.title
            )
            self.stdout.write(f"Indexed {document.id} {document.title}: {len(chunks)} chunks")
