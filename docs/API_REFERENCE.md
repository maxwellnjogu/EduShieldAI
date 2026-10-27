# EduShield AI — API Reference

> **REST Endpoint Specification & Role Matrix**
> *Prepared 16 October 2026 | Illustrative Sample / Demo Platform*

---

## 1. Authentication & Session Management

All secured endpoints require the `Authorization: Bearer <jwt_access_token>` header.

### `POST /api/auth/register/`
- **Access**: Public
- **Payload**:
  ```json
  {
    "username": "student5",
    "password": "Password123!",
    "email": "student5@riara.ac.ke",
    "role": "student",
    "first_name": "Eve",
    "last_name": "Mwangi"
  }
  ```
- **Response `201 Created`**:
  ```json
  { "id": 5, "username": "student5", "role": "student" }
  ```

### `POST /api/auth/login/`
- **Access**: Public
- **Payload**: `{ "username": "student1", "password": "Password123!" }`
- **Response `200 OK`**: `{ "access": "<jwt_token>", "refresh": "<jwt_refresh>" }`
- **Errors**: `401 Unauthorized` for invalid credentials (logged as suspicious login in SOC).

### `GET /api/auth/me/`
- **Access**: Authenticated (`student`, `lecturer`, `admin`)
- **Response `200 OK`**:
  ```json
  {
    "id": 1,
    "username": "student1",
    "email": "student1@riara.ac.ke",
    "role": "student",
    "first_name": "Alice",
    "last_name": "Wambui"
  }
  ```

---

## 2. Academic Catalog & Enrollment

### `GET /api/academic/universities/`
- **Access**: Public / Authenticated
- **Description**: Returns seeded demo institutions (Riara University, USIU-Africa, Daystar, JKUAT).

### `GET /api/academic/units/enrolled/`
- **Access**: Authenticated (`student`, `lecturer`, `admin`)
- **Description**: Returns authorized units. For students, returns enrolled units; for lecturers, returns assigned teaching units.
- **Response `200 OK`**:
  ```json
  [
    {
      "id": 1,
      "course": 1,
      "course_title": "BSc. Software Engineering",
      "university_name": "Riara University",
      "university_code": "RU",
      "code": "SE301",
      "title": "Software Engineering",
      "description": "Comprehensive 14-week software engineering curriculum.",
      "total_weeks": 14,
      "is_primary_demo": true
    }
  ]
  ```

---

## 3. 14-Week Learning Content & Weekly Resources

### `GET /api/academic/units/{unit_id}/resources/?week_number={week}`
- **Access**: Enrolled Student, Assigned Lecturer, Admin
- **Description**: Lists approved resources for the specified academic week.

### `POST /api/academic/units/{unit_id}/resources/`
- **Access**: Assigned Lecturer, Admin
- **Payload (multipart/form-data)**:
  - `title`: string
  - `week_number`: integer (1-14)
  - `resource_type`: `pdf` | `notes` | `slides` | `diagram` | `youtube`
  - `file`: binary (PDF validated by `%PDF-` magic header, max 10MB)
  - `external_url`: string (optional)
- **Response `201 Created`**:
  ```json
  {
    "id": 15,
    "title": "Cloud Native Architecture Notes",
    "week_number": 8,
    "resource_type": "pdf",
    "indexing_state": "indexed"
  }
  ```
- **Errors**: `400 Bad Request` if file signature fails or non-PDF uploaded; `403 Forbidden` if lecturer is unassigned.

---

## 4. Weekly Labs & Assessment Attempts

### `GET /api/academic/units/{unit_id}/labs/`
- **Access**: Enrolled Student, Assigned Lecturer, Admin
- **Description**: Returns all 14 weekly labs with student attempt summaries and scoring policies.

### `POST /api/academic/labs/{lab_id}/submit/`
- **Access**: Enrolled Student
- **Description**: Submits lab answers. Server calculates objective scores deterministically; creates immutable `LabAttempt` record; updates `is_completed` and attempt count.
- **Payload**:
  ```json
  {
    "answers": [
      {
        "question_id": 1,
        "selected_option_ids": [1],
        "written_response": ""
      }
    ]
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "attempt_number": 2,
    "score": 10.0,
    "max_score": 10.0,
    "percentage": 100.0,
    "is_passed": true,
    "submitted_at": "2026-10-16T12:00:00Z"
  }
  ```

---

## 5. Revision Pack & Learning Gap Diagnostics

### `GET /api/academic/units/{unit_id}/revision-pack/`
- **Access**: Enrolled Student, Assigned Lecturer, Admin
- **Description**: Returns the lecturer-reviewed consolidated 14-week revision pack (identical for all students in the same unit/version).

### `GET /api/academic/units/{unit_id}/weaknesses/`
- **Access**: Enrolled Student
- **Description**: Calculates evidence-based topic weaknesses based on stored question attempts; lists recurring mistakes and recommended review notes.

---

## 6. Final Readiness Exam & Gatekeeper

### `GET /api/academic/units/{unit_id}/readiness/`
- **Access**: Enrolled Student
- **Description**: Evaluates Gate 1 (14 labs completed). Returns `is_unlocked: true` only if all 14 labs have completed submissions. If locked, lists missing weeks.

### `POST /api/academic/units/{unit_id}/readiness/submit/`
- **Access**: Enrolled Student
- **Gate Enforcement**: If Gate 1 fails, returns `403 Forbidden` and logs an `unauthorized_access` security event to the Mini SOC.
- **Threshold**: Server-side threshold of 60%. If passed, records `ExamEligibility: eligible`.

---

## 7. Lecturer Cohort Matrix & Analytics

### `GET /api/academic/units/{unit_id}/cohort-analytics/`
- **Access**: Assigned Lecturer, Admin
- **Description**: Returns complete class roster including nonparticipants (0 submissions), 14-week progress matrix, most-missed cohort topics, and retake deltas.
- **Errors**: `403 Forbidden` if accessed by a student or an unassigned lecturer; automatically logged to Mini SOC.

---

## 8. Mini SOC & Threat Intelligence

### `GET /api/security/stats/`
- **Access**: Admin only (`maxadmin`)
- **Description**: Real-time event statistics categorized by threat type and severity.

### `GET /api/soc/events/`
- **Access**: Admin only
- **Description**: Paginated list of security events with user, endpoint, IP, and resolution status.

### `GET /api/security/incidents/`
- **Access**: Admin only
- **Description**: List of security incidents and audit history.
