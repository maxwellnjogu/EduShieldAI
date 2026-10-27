# EduShield AI — AI & RAG Engineering Guide

> **Document Retrieval, Grounding Rules, Provider Failover & Deterministic Fallbacks**
> *Prepared 16 October 2026 | Illustrative Sample / Demo Platform*

---

## 1. Core Architectural Principle

> **AI must never be the authority for scores, deadlines, gates, or exam eligibility.**
> Deterministic backend code calculates all percentages, attempt counts, topic weakness metrics, and qualification decisions.
> AI is strictly utilized for retrieval augmented tutoring and drafting question suggestions under lecturer review.

---

## 2. Document Extraction & Vector Indexing Pipeline

1. **Document Validation**:
   - Files are validated server-side for PDF format using binary signature verification (`%PDF-`).
   - Size limit: 10MB per document.
2. **Text Chunking**:
   - Extracted text is split into semantic paragraphs (500–1000 characters) with 100-character overlap.
3. **Embeddings & ChromaDB**:
   - Vectors are generated using `sentence-transformers/all-MiniLM-L6-v2`.
   - Embeddings are indexed in ChromaDB collection with metadata (`unit_id`, `week_number`, `resource_id`, `title`).
4. **Failure State Reporting**:
   - If extraction fails (e.g. corrupt PDF or scanned image without OCR), the resource's `indexing_state` is set to `failed` with an explicit error message. EduShield never silently reports success when indexing has failed.

---

## 3. Lecturer AI Draft Generation & Review

Lecturers can use approved weekly materials to draft assessments:
- **Endpoint**: `POST /api/academic/units/{unit_id}/generate-lab-draft/`
- **Workflow**:
  1. The lecturer selects an academic week (e.g. Week 4: Agile Frameworks).
  2. The system retrieves the approved summaries and notes for that week.
  3. AI drafts 3–5 candidate questions (MCQs with distractors, flashcards, or written questions with rubrics).
  4. **Human-in-the-Loop Requirement**: The AI output remains a `draft` in the lecturer dashboard until explicitly reviewed, edited, and published by the lecturer. Students cannot see draft questions.

---

## 4. Provider Outage & Quota Fallback Behavior

If the external AI provider is unavailable, times out, or exceeds rate quotas:
1. **Zero Data Loss**: Existing uploaded materials, student answers, and draft assessments are preserved completely without modification.
2. **Deterministic Template Fallback**: When AI generation is requested during an outage, the system automatically falls back to curated curriculum templates grounded in the unit's approved syllabus topics.
3. **Transparent Notification**: The interface informs the lecturer: *"AI provider currently unavailable; generated draft using approved curriculum template."*
