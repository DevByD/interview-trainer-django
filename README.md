# Interview Trainer

> **Smarter Online Interview Assessments with Timed Tests, Automated Grading, and Performance Analytics.**

---

## Project Overview

**Interview Trainer** is a full-featured, secure, and production-ready online assessment SaaS platform built with **Python 3.12, Django 5+, MySQL 8, Vanilla JavaScript, and Chart.js**. It empowers recruiters and hiring managers to configure multi-section assessments (covering Logical Reasoning, Quantitative Aptitude, and Technical Aptitude), schedule exams with strict time windows, and evaluate candidate submissions via automated grading and skill-matrix visualizations.

Candidates receive secure cryptographic exam links, take timed tests with interactive question palettes and authoritative server-side countdown timers, and view detailed performance analytics upon completion.

---

## Problem Statement

Traditional technical recruitment suffers from:
1. **Manual Assessment Scheduling**: Lack of centralized scheduling and invitation workflows.
2. **Unenforced Test Timers**: Relying solely on client-side clocks exposes exams to tampering and clock manipulation.
3. **Slow Grading Cycles**: Manual grading delays hiring pipelines and feedback loops.
4. **Poor Attendance & Expiry Tracking**: No automated handling of unattempted or expired candidate assessments.
5. **Security Gaps**: Exposing answer keys in frontend code or allowing cross-tenant assessment access.

---

## Solution

Interview Trainer provides an automated, secure recruitment assessment engine:
- **Strict Role-Based Access Control (RBAC)**: Clear partition between Candidate and Employer portals.
- **Authoritative Server-Side Deadlines**: Submissions are validated against the server-enforced deadline: `min(start_time + duration, expire_time)`.
- **Zero Answer Key Exposure**: Question options are provided to candidates without revealing correct answer keys in DOM, JSON payloads, or data attributes.
- **Automated Grading Engine**: Submissions are graded atomically on final submission, updating section breakdowns and percentage scores.
- **Automated Expiry Lifecycle**: Background service and management command automatically mark unattempted past-due assessments as `EXPIRED` / `NOT_ATTENDED` (`MISSED TEST`).
- **Interactive Visualizations**: High-performance Chart.js doughnut charts and progress meters for candidates and recruiters.

---

## Features

- **Authentication & Profiles**: Dual registration pipelines (Candidate & Employer) using Django's PBKDF2 password hashing.
- **Profile Strength Meter**: Real-time profile completion percentage tracking and secure resume uploads (`.pdf`, `.doc`, `.docx` up to 5MB).
- **Recruiter Dashboard**: Real-time counter metrics (Total Candidates, Active Tests, Completed Tests, Missed Tests) and candidate directory search.
- **Configurable Assessments**: Multi-section question distribution, customized durations, and custom scheduling windows.
- **Cryptographic Tokens**: Unique, high-entropy tokens (`secrets.token_urlsafe(32)`) generating secure test URLs (`/test/<token>/`).
- **Email Invitation Service**: Multi-part plain text and responsive HTML email delivery with direct CTA buttons.
- **Interactive Exam Interface**: Single-question navigation, question palette with status indicators (Current, Answered, Unanswered), and background AJAX auto-saving.
- **Countdown Timer**: Synchronized JavaScript timer with visual warning under 2 minutes and auto-submission on expiration.
- **Skill Analytics & Reports**: Section-by-section breakdown (Logical, Quantitative, Technical) and responsive Chart.js doughnut charts.
- **Automated Expiry / Missed Tests**: Management command (`expire_assessments`) and secure webhook endpoint (`/api/cron/expire-assessments/`).

---

## User Roles

### 1. Candidate
- Register and log in with email and password.
- Complete professional profile (education, phone, experience, skills, resume upload).
- View assigned assessments categorized by status (Pending, Ongoing, Completed, Missed).
- Take timed tests within authorized scheduling windows.
- View personal performance scorecards and section analytics.

### 2. Employer / Recruiter
- Register company account and access recruitment dashboard.
- Browse and search candidate directory by skills, education, or name.
- Create and configure assessments with custom question distributions.
- Monitor active tests and track candidate attendance.
- Review candidate results, overall percentages, and skill matrix charts.

---

## Workflows

### Candidate Workflow
```text
Register / Login
       │
       ▼
Complete Profile (Skills, Education, Resume)
       │
       ▼
Receive Assessment Invitation (Email / Dashboard)
       │
       ▼
Open Secure Link (/test/<token>/) ──► Validates window & token
       │
       ▼
Review Instructions ──► Click "START ASSESSMENT" (Status: ONGOING)
       │
       ▼
Interactive Test (Timer, Question Palette, Auto-Save)
       │
       ▼
Submit Test ──► Auto-Grading Engine ──► View Result & Analytics
```

### Employer Workflow
```text
Employer Register / Login
       │
       ▼
Recruiter Dashboard ──► Browse Candidate Directory
       │
       ▼
Select Candidate ──► Configure Sections & Question Counts
       │
       ▼
Set Schedule (Start, Expiry, Duration) ──► Generate Secure Token
       │
       ▼
Dispatch Invitation Email ──► Monitor Candidate Status
       │
       ▼
Evaluate Candidate Score & Section Breakdown Chart
```

### Missed Test / Expiry Workflow
```text
Assessment Scheduled (Status: PENDING / ONGOING)
       │
       ▼
Candidate Does Not Complete Before Expiry Window
       │
       ▼
Trigger Expiry Command (`python manage.py expire_assessments` or Cron)
       │
       ▼
Status Transitions to EXPIRED & Candidate Status to NOT_ATTENDED
       │
       ▼
Both Dashboards Display "MISSED TEST" (Test Locked From Starting)
```

---

## Technology Stack

| Layer | Technology |
|---|---|
| **Backend Framework** | Python 3.12, Django 5.x / 6.x |
| **Database** | MySQL 8.0+ (Local), Cloud Database via `DATABASE_URL` (Production) |
| **Frontend / Templates** | Django Templates, HTML5, Modern CSS3 (Variables & Grid), Vanilla JS |
| **Data Visualization** | Chart.js 4.x (Responsive Doughnut Charts) |
| **Static File Handling** | WhiteNoise (Compressed & Manifest Storage) |
| **Security & Auth** | Django Authentication (PBKDF2), CSRF Protection, Role Decorators |
| **Deployment Target** | Vercel Serverless Python Runtime (`@vercel/python`) |

---

## Folder Structure

```text
interview-trainer/
├── accounts/                  # Auth, CandidateProfile & EmployerProfile models/views
├── assessments/               # Assessment engine, questions, exam taking, timer & grading
│   ├── management/commands/   # seed_questions.py, expire_assessments.py
│   ├── email_service.py       # Multi-part invitation email delivery
│   ├── forms.py               # Assessment configuration forms
│   ├── models.py              # Question, Assessment, AssessmentQuestion, Answer
│   ├── services.py            # Auto-grading and expiration domain logic
│   ├── tests.py               # Comprehensive 30-scenario test suite
│   ├── urls.py                # Assessment routing and cron webhook
│   └── views.py               # Employer creation and candidate test taking views
├── candidates/                # Candidate dashboard, profile editor, resume upload
├── dashboard/                 # Employer dashboard, candidate directory & error views
├── results/                   # Result models, evaluation views, and Chart.js analytics
├── config/                    # Core Django settings, URLs, WSGI, ASGI
├── templates/                 # Reusable semantic HTML5 Django templates
│   ├── accounts/              # Candidate & Employer login / registration templates
│   ├── assessments/           # Creation, list, instructions, test taking, gate templates
│   ├── candidates/            # Candidate dashboard & profile templates
│   ├── dashboard/             # Employer dashboard & candidate directory templates
│   ├── results/               # Candidate & Employer result templates
│   ├── base.html              # Base layout with responsive navigation & footer
│   ├── home.html              # SaaS landing page
│   ├── 404.html, 403.html, 500.html # Custom error pages
├── static/                    # Design system stylesheets & assets
│   └── css/                   # global.css, auth.css, dashboard.css, assessment.css, results.css, responsive.css
├── manage.py                  # Django CLI management script
├── requirements.txt           # Production dependencies
├── vercel.json                # Vercel deployment configuration
├── .env.example               # Environment variables specification
└── README.md                  # Project documentation
```

---

## Installation & Setup

### 1. Prerequisites
- Python 3.12+
- MySQL Server 8.0+
- Git

### 2. Clone Repository & Setup Virtual Environment
```bash
git clone <repository-url>
cd interview-trainer

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux / macOS:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your database credentials:
```bash
cp .env.example .env
```

Example `.env` for local MySQL:
```ini
SECRET_KEY=your-secure-random-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,.vercel.app

DB_NAME=interview_trainer
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_HOST=localhost
DB_PORT=3306

EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=noreply@interviewtrainer.local
CRON_SECRET_KEY=dev-cron-secret-key-12345
SITE_DOMAIN=localhost:8000
```

### 5. Apply Migrations & Seed Question Bank
```bash
python manage.py migrate
python manage.py seed_questions
```

### 6. Start Development Server
```bash
python manage.py runserver
```
Open [http://localhost:8000](http://localhost:8000) in your browser.

---

## Scheduled Expiry Automation

To mark past-due uncompleted assessments as `EXPIRED` and `NOT_ATTENDED`:

### 1. Management Command (CLI / Task Scheduler / Cron):
```bash
python manage.py expire_assessments
```

### 2. HTTP Webhook Endpoint (Vercel Cron / External Trigger):
```http
GET /api/cron/expire-assessments/ HTTP/1.1
Host: localhost:8000
Authorization: Bearer dev-cron-secret-key-12345
```

---

## Automated Test Suite

To run all automated validation tests:
```bash
python manage.py check
python manage.py test -v 2
```

---

## Security Audit & Compliance

- **Role-Based Access Control**: View decorators ([`@candidate_required`](file:///C:/Users/intel/interview-trainer/accounts/decorators.py), [`@employer_required`](file:///C:/Users/intel/interview-trainer/accounts/decorators.py)) enforce strict isolation.
- **Tenant & Record Isolation**:
  - Candidate A cannot view Candidate B's assessments or results (HTTP 403).
  - Employer A cannot view Employer B's assessments or candidate results (HTTP 403).
- **Server-Authoritative Timers**: Submission timestamps are checked against `min(start_time + duration, expire_time)`.
- **File Upload Protection**: Validates resume extensions (`.pdf`, `.doc`, `.docx`), rejects executable/script formats, and limits uploads to 5MB.
- **Zero Leakage**: Candidate test views never render or transmit the `correct_answer` field.

---

## Vercel Deployment Readiness

The project is structured and configured for Vercel deployment:
- **`vercel.json`**: Configured with `@vercel/python` routing `config/wsgi.py`.
- **`config/wsgi.py`**: Exports `app = application` for serverless compatibility.
- **Static Assets**: Handled by `WhiteNoise` with manifest caching.
- **Environment Driven**: Fully supports `DATABASE_URL`, `DEBUG=False`, and custom `ALLOWED_HOSTS`.

---

## License

This project is open-source and available under the **MIT License**.
