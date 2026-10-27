from knowledge.services import search_knowledge

from .llm import generate_with_llm

NOT_FOUND_MESSAGE = (
    "I could not find relevant information in the approved "
    "educational knowledge base."
)


def generate_tutor_answer(question, history=None):
    """
    Returns (answer_text, sources). Sources are de-duplicated documents
    that contributed to the answer. The answer is written by the local
    LLM when available, otherwise the retrieved passages are returned.
    """
    results = search_knowledge(question, top_k=4)

    if not results:
        return NOT_FOUND_MESSAGE, []

    passages = [result["text"] for result in results]

    sources = []
    seen = set()
    for result in results:
        meta = result["metadata"] or {}
        doc_id = meta.get("document_id")
        if doc_id in seen:
            continue
        seen.add(doc_id)
        sources.append({
            "document_id": doc_id,
            "title": meta.get("title") or f"Document {doc_id}",
            "relevance": result["score"],
        })

    answer = generate_with_llm(question, passages, history=history)

    if answer is None:
        answer = (
            "Based on the approved educational material:\n\n"
            + "\n\n".join(passages)
        )

    return answer, sources