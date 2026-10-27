import os
import re
from functools import lru_cache

import chromadb
from django.conf import settings
from pypdf import PdfReader


# Retrieval tuning
MIN_RELEVANCE = 0.25   # cosine similarity below this is treated as "not found"
DEFAULT_TOP_K = 4


@lru_cache(maxsize=1)
def get_embedding_model():
    """Load the local embedding model lazily (it is slow to import/load)."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer("all-MiniLM-L6-v2")


@lru_cache(maxsize=1)
def get_collection():
    client = chromadb.PersistentClient(
        path=os.path.join(settings.BASE_DIR, "chroma_db")
    )
    # Cosine distance gives an interpretable relevance score.
    # A new collection name is used because the original collection was
    # created with the default L2 metric; run `manage.py reindex_knowledge`.
    return client.get_or_create_collection(
        name="edushield_knowledge_v2",
        metadata={"hnsw:space": "cosine"},
    )


def extract_pdf_text(file_path):
    reader = PdfReader(file_path)

    text = ""

    for page in reader.pages:
        page_text = page.extract_text()

        if page_text:
            text += page_text + "\n"

    return text


def _clean_text(text):
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text, chunk_size=1000, overlap=200):
    """
    Split text on paragraph/sentence boundaries so chunks don't cut
    sentences in half, carrying a small overlap between chunks.
    """
    text = _clean_text(text)
    if not text:
        return []

    # Break into sentence-ish units, keeping paragraphs apart.
    units = []
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.replace("\n", " ").strip()
        if not paragraph:
            continue
        units.extend(
            s.strip() for s in re.split(r"(?<=[.!?])\s+", paragraph) if s.strip()
        )

    chunks = []
    current = ""

    for unit in units:
        # Hard-split any single unit longer than a chunk.
        while len(unit) > chunk_size:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(unit[:chunk_size])
            unit = unit[chunk_size - overlap:]

        if current and len(current) + len(unit) + 1 > chunk_size:
            chunks.append(current)
            current = current[-overlap:].split(" ", 1)[-1] if overlap else ""

        current = f"{current} {unit}".strip()

    if current:
        chunks.append(current)

    return chunks


def create_embeddings(chunks):
    embeddings = get_embedding_model().encode(
        chunks,
        convert_to_numpy=True,
        normalize_embeddings=True,
        batch_size=32,
    )

    return embeddings.tolist()


def store_document_chunks(document_id, chunks, embeddings, title=""):
    ids = [
        f"document-{document_id}-chunk-{index}"
        for index in range(len(chunks))
    ]

    get_collection().upsert(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=[
            {
                "document_id": document_id,
                "title": title,
                "chunk_index": index,
            }
            for index in range(len(chunks))
        ],
    )


def delete_document_chunks(document_id):
    get_collection().delete(where={"document_id": document_id})


def _relevance(distance):
    # Cosine distance -> similarity in [0, 1].
    return max(0.0, 1.0 - float(distance))


def search_knowledge(question, top_k=DEFAULT_TOP_K, min_relevance=MIN_RELEVANCE):
    collection = get_collection()
    if collection.count() == 0:
        return []

    question_embedding = get_embedding_model().encode(
        [question],
        convert_to_numpy=True,
        normalize_embeddings=True,
    )[0].tolist()

    results = collection.query(
        query_embeddings=[question_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    hits = []
    for document, metadata, distance in zip(documents, metadatas, distances):
        score = _relevance(distance)
        if score >= min_relevance:
            hits.append({
                "text": document,
                "metadata": metadata,
                "score": round(score, 3),
            })

    return hits