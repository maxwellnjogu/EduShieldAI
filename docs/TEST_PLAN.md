# EduShield AI — Test Plan & Verification Evidence

> **Comprehensive Test Suites, Security Verification & Regression Results**
> *Prepared 16 October 2026 | Illustrative Sample / Demo Platform*

---

## 1. Test Automation Architecture

The test suite covers backend models, role-based permissions, deterministic scoring engines, the 14-lab gatekeeper, and the Mini SOC threat pipeline.

- **Backend Framework**: Django Test Runner (`django.test.TestCase`, `rest_framework.test.APITestCase`).
- **Database**: PostgreSQL test instance automatically instantiated by Django.
- **Frontend Validation**: TypeScript compiler strict type checking (`tsc -b`) and Vite production bundle compilation (`vite build`).

---

## 2. Test Execution & Evidence

### 2.1 Backend Academic Suite
Execute command:
```bash
cd backend
.\venv\Scripts\python.exe manage.py test academic
```

**Results**:
```
Creating test database for alias 'default'...
.......
----------------------------------------------------------------------
Ran 7 tests in 53.269s

OK
Destroying test database for alias 'default'...
```

#### Detailed Test Case Matrix:
1. `test_catalog_and_enrollment_boundaries`:
   - Verifies Riara University demo catalog is seeded.
   - Verifies students can only access units they are enrolled in.
   - Verifies unauthorized units return empty/denied sets.
2. `test_lab_deterministic_scoring_and_attempt_retention`:
   - Submits initial attempt to Week 1 lab; asserts deterministic server-calculated score.
   - Submits retake; asserts attempt number increments from 1 to 2.
   - Asserts previous attempt is retained with identical score and timestamp (zero overwrite).
3. `test_readiness_gatekeeper_enforcement_and_bypass_prevention`:
   - Enrolls student with only 12 completed labs (Weeks 1-12).
   - Attempts direct POST to `/api/academic/units/{id}/readiness/submit/`.
   - Asserts server responds with HTTP `403 Forbidden`.
   - Asserts `unauthorized_access` event is automatically logged to `SecurityEvent` in Mini SOC.
4. `test_readiness_eligibility_qualification_threshold`:
   - Completes all 14 weekly labs.
   - Submits readiness answers scoring 80% (above the 60% threshold).
   - Asserts server marks attempt as `is_passed: true` and certifies `ExamEligibility: eligible`.
5. `test_lecturer_cohort_analytics_includes_nonparticipants`:
   - Enrolls 4 students including David (0 submissions).
   - Asserts lecturer cohort analytics endpoint returns all 4 students.
   - Asserts David is correctly identified as `completed_labs: 0` (nonparticipant).
6. `test_shared_revision_pack_identical_across_cohort`:
   - Fetches revision pack as Alice (`student1`) and Bob (`student2`).
   - Asserts payload, version (`1.0`), and weekly contents are byte-for-byte identical.
7. `test_personalized_weakness_recommendations`:
   - Submits incorrect answers tagged with topic `CI/CD Pipelines`.
   - Verifies topic error rate calculation and generated study recommendations.

---

### 2.2 Frontend Build & Typecheck Verification
Execute command:
```bash
cd frontend
npm run build
```

**Results**:
```
> frontend@0.0.0 build
> tsc -b && vite build

vite v8.3.3 building client environment for production...
transforming...
✓ 74 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.46 kB │ gzip:   0.29 kB
dist/assets/index-DFyUt7ZG.css   33.14 kB │ gzip:   6.90 kB
dist/assets/index-Dbo0ErVs.js   326.34 kB │ gzip: 100.23 kB
✓ built in 1.78s
```
**Exit Code**: `0` (Zero compiler errors, zero warnings).
