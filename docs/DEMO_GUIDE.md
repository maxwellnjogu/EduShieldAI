# EduShield AI — Demonstration Script & Guide

> **3–5 Minute Step-by-Step Evaluator Presentation Script**
> *Prepared 16 October 2026 | Illustrative Sample / Demo Platform*

---

## 1. Demo Narrative Overview (30 Seconds)

1. **The Higher Education Challenge**:
   - Students frequently arrive at final exams unsure of their specific weak topics or whether they are truly prepared.
   - Lecturers lack real-time visibility into weekly class participation, struggling to identify disengaged nonparticipants before it is too late.
   - Introducing AI into universities creates major security vulnerabilities: prompt injections, leaked answer keys, and exam eligibility bypasses.
2. **The EduShield Solution**:
   - A lecturer-led platform structuring learning into 14 weeks.
   - An evidence-based diagnostic engine providing shared revision notes and individualized weakness recommendations.
   - A deterministic backend gatekeeper that verifies all 14 weekly labs are completed before permitting final exam eligibility.
   - An integrated Mini SOC that protects institutional integrity.

---

## 2. Interactive Persona Walkthrough (3 Minutes)

### Step 1: Alice — The Eligible Student (45 Seconds)
1. On the login screen or header demo bar, click **🎓 Alice (14 Labs/Eligible)** (`student1`).
2. Point out:
   - **14 Weekly Labs Completed**: Alice has completed all 14 labs (Average score: 91.4%).
   - **Shared 14-Week Revision Pack**: Click *Shared 14-Week Revision Pack*; expand Week 1 (SDLC) and Week 8 (Cloud Architecture). Emphasize that this pack is identical for all students in the class.
   - **Exam Readiness Gate**: Click *Final Exam Readiness Gate*. Show the green badge: **Certified Eligible for University Examination** (Readiness score: 80%).

### Step 2: Bob — The Gatekeeper in Action (45 Seconds)
1. Switch persona to **⏳ Bob (12 Labs/Locked)** (`student2`).
2. Point out:
   - Bob has completed Weeks 1 through 12, but has not completed Weeks 13 and 14.
   - Click *Final Exam Readiness Gate*: The test is **LOCKED**.
   - Show the exact lock reason: *"Gate 1 Incomplete: Missing required submissions for Week 13, Week 14."*
   - Explain that even direct API calls cannot bypass this gatekeeper.
3. Open Week 13 lab from the dashboard, answer the questions, and submit.
4. Show that Bob now has 13/14 labs completed and the gate remains securely locked until Week 14 is also submitted.

### Step 3: Charles & David — Diagnostic Gaps & Nonparticipants (30 Seconds)
1. Switch persona to **⚠️ Charles** (`student3`):
   - Click *Personal Weakness Recommendations*: Show the diagnosed error rates in *CI/CD Pipelines* and *SQL Injection Defense* with direct links to approved lecture notes.
2. Switch persona to **👩‍🏫 Dr. Grace (Lecturer)** (`lecturer_grace`):
   - Point out the **Cohort Student Roster**.
   - Highlight **💤 David** (`student4`): 0/14 labs completed. Point out that nonparticipants are clearly surfaced so lecturers can intervene early.
   - Show the **Cohort Most-Missed Topics** analytics derived from actual student submissions.

### Step 4: Maxwell — The Mini SOC & Live Threat Interception (45 Seconds)
1. Click the top button: **⚡ Test Prompt Injection**.
2. Show the instant security block: The adversarial prompt was rejected with `403 Forbidden` *before* reaching the AI.
3. Switch persona to **🛡️ Maxwell (SOC)** (`maxadmin`):
   - Show the real-time event appearing in **Maxwell's SOC**: Type `prompt_injection`, Severity `CRITICAL`, with safe sanitized evidence.
   - Click **⚡ Test Unauthorized Access (403)**: Show that student attempts to access unauthorized cohort endpoints are intercepted and logged to the SOC immediately.

---

## 3. Demo Reset & Recovery Steps

If data needs to be restored to its pristine demo state at any time:
```bash
cd backend
python manage.py seed_academic_demo
```
This re-seeds all 14 weeks, resets Alice, Bob, Charles, and David, and restores all clean demo baselines within seconds.
