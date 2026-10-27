# EduShield AI — Security Guide & Threat Model

> **Mini SOC Architecture, Threat Mitigation, Prompt-Injection Defense & Testing**
> *Prepared 16 October 2026 | Illustrative Sample / Demo Platform*

---

## 1. Threat Model & Trust Boundaries

EduShield AI operates under a Zero Trust defense-in-depth model across three primary roles: `student`, `lecturer`, and `admin` (SOC Operator).

```
[Untrusted Client: Web Browser / Adversary]
       │
       ▼  (HTTPS / TLS)
[EduShield WAF & Security Middleware]
  ├── IP Blocklist Filter (Reject blocked IPs with 403)
  ├── Rate Limiter (Block abnormal spikes / DDoS)
  ├── Prompt Injection Analyzer (Keyword, Regex & Semantic Heuristics)
  └── API Request Logger (Sanitized, zero secret leakage)
       │
       ▼  (Allowed Traffic)
[Django Application Core & Role-Based Authorization]
  ├── JWT Auth Middleware
  ├── IsLecturerOrAdmin / IsStudentUser Boundaries
  └── Object-Level Unit Ownership Verification
       │
       ▼
[Database / Knowledge Retrieval / External LLM]
```

### 1.1 Priority Threat Vectors & Defenses

| Threat Vector | Potential Impact | EduShield Countermeasure |
| :--- | :--- | :--- |
| **Prompt Injection** | LLM jailbreak, system prompt extraction, student cheating. | Server-side `detect_prompt_injection()` scans input **prior** to any LLM invocation. Block-worthy payloads return `403 Forbidden` immediately and log a high-severity `SecurityEvent`. |
| **Direct Gatekeeper Bypass** | Student submitting to readiness test without completing 14 labs. | Server-side Gate 1 validation in `grade_readiness_attempt()`. Direct API calls are rejected with `403 Forbidden` and trigger an `unauthorized_access` event. |
| **Cross-Unit Lecturer Tampering** | Lecturer viewing or editing unassigned unit exams/notes. | Backend permission `IsLecturerOrAdmin` verifies `LecturerUnitAssignment` in PostgreSQL. Unauthorized access attempts log source IP, user, and endpoint. |
| **Malicious File Upload** | Remote Code Execution via poisoned document payloads. | Multi-stage upload validation: file extension check, maximum size ceiling (10MB), and binary signature verification (`%PDF-` magic header). |
| **Brute Force & Credential Stuffing** | Account compromise. | Automatic failed-login tracking. Repeated failures from an IP trigger automated incident escalation and IP blocklist containment. |

---

## 2. Server-Side Prompt-Injection Defense

EduShield AI adheres to the principle: **Logging alone is not prevention.**

When a user submits a question to the AI Tutor or requests AI drafting:
1. `detect_prompt_injection(question)` analyzes the prompt against adversarial attack signatures (e.g. `ignore all previous instructions`, `system prompt override`, `jailbreak`, `DAN`, `roleplay`).
2. If classified as malicious:
   - The protected AI action is **aborted immediately**.
   - No tokens are consumed or sent to external LLMs.
   - An event with type `prompt_injection`, severity `CRITICAL`, and the offending query is logged into `SecurityEvent`.
   - The API returns HTTP `403 Forbidden`.

---

## 3. Safe Logging & Data Sanitization Rules

- **Zero Secret Leakage**: Passwords, JWT refresh tokens, API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`), and database connection strings are strictly scrubbed from all API request logs and security event metadata.
- **Payload Privacy**: Student written answers and uploaded resource contents are never dumped in plaintext into logging streams.
- **Client IP Tracking**: Extracted safely via `X-Forwarded-For` or `REMOTE_ADDR`.

---

## 4. SOC Testing & Verification Procedures

### 4.1 Test Case 1: Prompt-Injection Blocking
1. Log in as any user.
2. Click **⚡ Test Prompt Injection** in the top navigation header.
3. **Observed Result**: Browser displays a security warning modal confirming HTTP `403 Forbidden`. The protected AI call was rejected.
4. Log in as `maxadmin` and navigate to **Maxwell's SOC**:
   - The event appears in the Security Events table with type `prompt_injection` and severity `CRITICAL`.

### 4.2 Test Case 2: Unauthorized Unit Boundary Violation
1. Log in as student `student2` (Bob) or click **⚡ Test Unauthorized Access (403)**.
2. Attempt to fetch restricted lecturer cohort analytics for an unassigned unit.
3. **Observed Result**: Backend returns HTTP `403 Forbidden`.
4. Navigate to **Maxwell's SOC**:
   - The event is recorded as `unauthorized_access` with user `student2` and the attempted endpoint `/api/academic/units/999/cohort-analytics/`.
