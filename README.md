# Online Attendance Tracking System

[![Django](https://img.shields.io/badge/Django-5.1-0C4B33?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Bootstrap 5](https://img.shields.io/badge/Bootstrap-5.3-7952B3?style=for-the-badge&logo=bootstrap&logoColor=white)](https://getbootstrap.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

A secure, modern, role-based web application built with **Django** and **Bootstrap 5** for academic institutions to manage classrooms, subjects, teacher allocations, student rosters, daily roll-call attendance, and analytical reporting.

---

## 📋 Table of Contents

- [Project Overview](#-project-overview)
- [Problem Statement](#-problem-statement)
- [Project Objectives](#-project-objectives)
- [Main Features](#-main-features)
- [Technology Stack](#-technology-stack)
- [Application Architecture](#-application-architecture)
- [Database Model Overview](#-database-model-overview)
- [Project Directory Structure](#-project-directory-structure)
- [Prerequisites](#-prerequisites)
- [Installation Instructions](#-installation-instructions)
- [Database Migrations & Setup](#-database-migrations--setup)
- [Demo Data Setup](#-demo-data-setup)
- [Creating an Administrator Account](#-creating-an-administrator-account)
- [Running the Application](#-running-the-application)
- [Production Deployment](#-production-deployment)
- [Testing Instructions](#-testing-instructions)
- [Screenshots & Visual Layouts](#-screenshots--visual-layouts)
- [Security Considerations](#-security-considerations)
- [Known Limitations](#-known-limitations)
- [Future Enhancements](#-future-enhancements)
- [License](#-license)

---

## 📖 Project Overview

The **Online Attendance Tracking System** provides schools, colleges, and educational organizations with a streamlined digital platform to monitor and analyze student attendance in real time. Designed with a strict **Role-Based Access Control (RBAC)** architecture, it cleanly separates administrative oversight from teacher workflows, eliminating paper registers, preventing unauthorized backdating, and offering instant data exports.

---

## ❗ Problem Statement

Traditional attendance tracking in educational institutions suffers from:
1. **Paper Inefficiencies:** Physical attendance registers are vulnerable to damage, loss, manual tally errors, and cumbersome archival.
2. **Lack of Role Enforcement:** Unregulated roll-calling makes it difficult to audit which instructor recorded or altered student attendance.
3. **Data Silos & Delayed Reporting:** Calculating attendance percentages, identifying habitual absenteeism, and preparing compliance reports requires hours of manual aggregation.
4. **Security Vulnerabilities:** Spreadsheets shared across departments often suffer from data tampering, unauthenticated alterations, and spreadsheet formula injection risks.

---

## 🎯 Project Objectives

- **Digitize Roll Call:** Enable instructors to submit class-wide attendance in seconds via an intuitive, touch-friendly UI.
- **Enforce Academic Integrity:** Prevent duplicate attendance submissions and restrict backdating through server-side business rules.
- **Provide Actionable Analytics:** Automate attendance percentage calculations, highlight at-risk students, and visualize attendance trends across academic divisions.
- **Ensure Enterprise-Grade Security:** Incorporate defense-in-depth security against CSRF, XSS, SQL injection, open redirects, and CSV formula execution.
- **Universal Responsiveness:** Ensure full operational functionality across desktop workstations, tablets, and smartphones.

---

## ✨ Main Features

### 1. Role-Based Access Control (RBAC)
- **Administrators:** Complete operational authority over academic calendars, classrooms, subject catalogs, teacher profiles, student enrollments, system logs, and global analytics.
- **Teachers:** Scoped workspace displaying only their assigned classes and subjects, enabling rapid roll call, attendance modification within permissible windows, and assigned student dossiers.

### 2. Academic Hierarchy Management
- **Academic Years:** Manage multi-year academic cycles with automated single-active-year enforcement.
- **Classrooms & Sections:** Standard grade and division management with unique constraints per academic year.
- **Subject Catalog:** Standardized curriculum subject registry with unique subject code indexing.
- **Teaching Assignments:** Explicit mappings between classrooms, subjects, and instructors to prevent overlapping allocations.

### 3. Student Information Management
- Comprehensive student directory with automated student ID verification, roll numbers, guardian contacts, and enrollment dates.
- Real-time search by student ID or name substring.
- Multi-parameter filtering by classroom, section, and enrollment status.
- Soft deactivation preserving historical attendance logs.

### 4. Daily Attendance Tracking
- **Interactive Sheet:** Bulk roll-call interface with one-click quick actions (*Mark All Present*, *Mark All Absent*).
- **Supported Statuses:** `Present`, `Absent`, `Late`, `Excused`.
- **Duplicate Prevention:** Database-level uniqueness constraints prevent duplicate submissions for any class, subject, and date.
- **Backdating Guards:** Configurable threshold (default: 7 days) prevents instructors from retroactively altering attendance without administrative override.

### 5. Reporting, Analytics & Exports
- **Student Dossiers:** Detailed breakdown showing total sessions, presence count, late arrivals, excused absences, and attendance percentage.
- **Documented Percentage Formula:**
  $$\text{Attendance \%} = \left(\frac{\text{Present} + \text{Late}}{\text{Total Applicable Sessions}}\right) \times 100$$
  *(Sessions prior to a student's enrollment date are excluded from their metric).*
- **Class Summaries & Visual Trends:** Chart.js visualizations illustrating daily presence rates and status distributions.
- **Hardened CSV Exports:** One-click exports formatted in UTF-8 with BOM for seamless Microsoft Excel compatibility, protected against CSV formula injection.

---

## 🛠️ Technology Stack

| Layer | Component | Description |
|---|---|---|
| **Backend Framework** | Django 5.1 | High-level Python web framework enforcing MVC/MVT architecture |
| **Language** | Python 3.10+ | Clean, readable, and type-annotated application code |
| **Database** | SQLite 3 | Zero-configuration relational database (PostgreSQL ready) |
| **Frontend UI** | Bootstrap 5.3 & Icons | Responsive styling, flexbox grids, and clean visual components |
| **Form Management** | Django Crispy Forms | Bootstrap 5 template pack rendering accessible HTML forms |
| **Data Visualization** | Chart.js 4.4 | Dynamic client-side line, bar, and donut charts |
| **Image Processing** | Pillow 10.4+ | Validation and handling of student and profile avatars |
| **Environment** | python-dotenv | Secure decoupled environment variable configuration |

---

## 🏗️ Application Architecture

The system follows Django's decoupled modular architecture:

```text
               +-------------------------------------------------+
               |                   Web Browser                   |
               |       (Desktop / Tablet / Mobile Viewports)      |
               +-------------------------------------------------+
                                       |
                                HTTP / HTTPS
                                       |
               +-------------------------------------------------+
               |              Django Middleware Layer            |
               |  SecurityMiddleware | SessionMiddleware | CSRF  |
               +-------------------------------------------------+
                                       |
                     +-----------------+-----------------+
                     |                                   |
           [Admin Workflows]                    [Teacher Workflows]
                     |                                   |
         +-----------v------------+         +------------v-----------+
         | accounts (RBAC/Users)  |         | attendance (Roll Call) |
         | academics (Classes/Sub)|         | attendance (Reports)   |
         | students (Enrollments) |         | dashboard (Workspaces) |
         +------------------------+         +------------------------+
                     |                                   |
                     +-----------------+-----------------+
                                       |
               +-----------------------v-------------------------+
               |                    ORM Layer                    |
               |  ACID Transactions | Constraints | Validations  |
               +-------------------------------------------------+
                                       |
               +-----------------------v-------------------------+
               |                SQLite Database                  |
               +-------------------------------------------------+
```

---

## 🗄️ Database Model Overview

```mermaid
erDiagram
    AcademicYear ||--o{ Classroom : contains
    User ||--o{ TeacherProfile : has
    User ||--o{ Classroom : supervises
    Classroom ||--o{ Student : enrolls
    Classroom ||--o{ ClassSubjectAssignment : offers
    Subject ||--o{ ClassSubjectAssignment : taught_in
    User ||--o{ ClassSubjectAssignment : instructs
    Classroom ||--o{ AttendanceSession : scheduled_for
    Subject ||--o{ AttendanceSession : relates_to
    AttendanceSession ||--o{ Attendance : records
    Student ||--o{ Attendance : receives
```

### Core Entities & Constraints
1. **`accounts.User`**: Custom user model extending `AbstractUser` with role choices (`ADMINISTRATOR`, `TEACHER`), profile avatar, phone number, and RBAC helper methods.
2. **`accounts.TeacherProfile`**: One-to-one extension storing employee ID, qualifications, department, and joining date.
3. **`academics.AcademicYear`**: Academic calendar session with validation enforcing `end_date > start_date` and automated deactivation of older sessions when a new year is marked active.
4. **`academics.Classroom`**: Grade and section entity with a `UniqueConstraint(name, section, academic_year)` to prevent duplicate sections within an academic cycle.
5. **`academics.Subject`**: Course catalog with unique alphanumeric course codes.
6. **`academics.ClassSubjectAssignment`**: Relational bridge assigning a teacher to a specific class and subject, guarded by `UniqueConstraint(classroom, subject)`.
7. **`students.Student`**: Student directory record with unique `student_id`, class reference, roll number, and enrollment date.
8. **`attendance.AttendanceSession`**: Session header tracking `(classroom, subject, date)` with uniqueness constraints.
9. **`attendance.Attendance`**: Individual record linking `session`, `student`, `status`, and remarks with `UniqueConstraint(session, student)`.

---

## 📂 Project Directory Structure

```text
Online Attendance Tracking System/
├── .env                              # Local environment variables (git-ignored)
├── .env.example                      # Documented configuration template
├── .gitignore                        # Production-grade git exclusion rules
├── manage.py                         # Django administrative CLI runner
├── requirements.txt                  # Pinned Python package dependencies
├── README.md                         # Project documentation
│
├── config/                           # Project configuration & settings
│   ├── settings.py                   # Central settings with security guards
│   ├── urls.py                       # Root URL routing dispatcher
│   ├── asgi.py                       # ASGI deployment interface
│   └── wsgi.py                       # WSGI deployment interface
│
├── accounts/                         # Authentication, User profiles & RBAC
│   ├── management/commands/
│   │   ├── create_dev_users.py       # Seeds basic development accounts
│   │   └── seed_demo_data.py         # Populates realistic institutional demo data
│   ├── models.py                     # Custom User & TeacherProfile models
│   ├── views.py                      # Login, logout, profile & teacher views
│   ├── forms.py                      # Authentication & teacher management forms
│   ├── permissions.py                # Role verification mixins (AdminRequired, etc.)
│   └── tests.py                      # 100% passing RBAC & security tests
│
├── academics/                        # Institutional structure
│   ├── models.py                     # AcademicYear, Classroom, Subject, Assignment
│   ├── views.py                      # CRUD views for classes, subjects, assignments
│   ├── forms.py                      # Academic model forms with validation
│   └── tests.py                      # Model validation and constraint tests
│
├── students/                         # Student registry & profiles
│   ├── models.py                     # Student model with uniqueness constraints
│   ├── views.py                      # Directory, search, filter, detail & CRUD views
│   ├── forms.py                      # Student creation & modification forms
│   └── tests.py                      # Enrollment, roll number, & scoping tests
│
├── attendance/                       # Attendance recording & reporting engine
│   ├── models.py                     # AttendanceSession & Attendance models
│   ├── views.py                      # Roll call, history, CSV export & analytics views
│   ├── forms.py                      # Attendance filter and sheet forms
│   └── tests.py                      # Atomic transaction and calculation tests
│
├── dashboard/                        # Central landing workspaces
│   ├── views.py                      # Role-aware dashboard routing (Admin vs Teacher)
│   └── urls.py                       # Root application landing routes
│
├── static/                           # Static assets
│   ├── css/style.css                 # Custom responsive design system & palette
│   ├── js/main.js                    # UI interactivity & client helpers
│   └── images/                       # Branding and image assets
│
└── templates/                        # Modular HTML templates
    ├── base.html                     # Master layout with navbar & sidebar
    ├── includes/                     # Reusable layout partials (topbar, sidebar)
    ├── accounts/                     # Login and profile templates
    ├── academics/                    # Classroom and subject templates
    ├── students/                     # Student directory and detail templates
    ├── attendance/                   # Roll call taking and history templates
    ├── reports/                      # Analytics and student report dossiers
    └── dashboard/                    # Admin and Teacher dashboard views
```

---

## ⚙️ Prerequisites

- **Python:** Version `3.10` or higher (`3.11`, `3.12`, `3.13` supported).
- **Git:** Installed on your local workstation.
- **Web Browser:** Any modern browser (Google Chrome, Firefox, Microsoft Edge, Safari).

---

## 🚀 Installation Instructions

### 1. Clone the Repository
```bash
git clone https://github.com/solatpatil-08/Online-Attendance-Tracker.git
cd Online-Attendance-Tracker
```

### 2. Set Up a Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Package Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy the template to create your local `.env` file:

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

**macOS / Linux:**
```bash
cp .env.example .env
```

*Note: For local development, the default settings in `.env.example` will work out of the box.*

---

## 💾 Database Migrations & Setup

Initialize your local SQLite database and apply all model migrations:

```bash
python manage.py makemigrations
python manage.py migrate
```

---

## 🏫 Demo Data Setup

The project includes an institutional data generator that populates realistic fictional school data (administrators, teachers, subjects, classes, student rosters, and 30 days of attendance history):

```bash
python manage.py seed_demo_data
```

### Optional Command Flags:
- `--days <N>`: Number of days of attendance history to generate (default: `30`).
- `--password <pass>`: Default password for seeded accounts (default: `DemoPass@123`).
- `--reset`: Safely clears existing demo records before re-seeding.

```bash
# Example: Seed with 60 days of history
python manage.py seed_demo_data --days 60
```

### Default Demo Credentials:
| Role | Username | Password |
|---|---|---|
| **Administrator** | `admin` | `DemoPass@123` |
| **Teacher** | `teacher` | `DemoPass@123` |

---

## 👤 Creating an Administrator Account

If you prefer to start with a fresh administrator without using demo data, run:

```bash
python manage.py createsuperuser
```

Follow the prompts to enter a username, email, and secure password.

---

## 🖥️ Running the Application (Local Development)

Start the Django development server:

```bash
python manage.py runserver
```

Open your browser and navigate to:
- **Application Portal:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Django Admin Interface:** [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)

---

## 🚀 Production Deployment

For complete, step-by-step production setup, systemd unit definitions, Nginx SSL configuration, and environment variable references, refer to the [Production Deployment Guide](DEPLOYMENT.md).

### Quick Production Deployment Summary:

1. **Configure Production Environment (`.env`):**
   ```ini
   DEBUG=False
   SECRET_KEY=your-cryptographically-strong-secret-key
   ALLOWED_HOSTS=attendance.yourinstitution.edu
   CSRF_TRUSTED_ORIGINS=https://attendance.yourinstitution.edu
   DATABASE_URL=postgresql://attendance_user:password@localhost:5432/attendance_db
   SECURE_SSL_REDIRECT=True
   USE_X_FORWARDED_PROTO=True
   ```

2. **Install Production Requirements & Drivers:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Apply Database Migrations:**
   ```bash
   python manage.py migrate
   ```

4. **Collect and Compress Static Files (WhiteNoise):**
   ```bash
   python manage.py collectstatic --noinput
   ```

5. **Create Initial Administrator:**
   ```bash
   python manage.py createsuperuser
   ```

6. **Verify Security Deployment Checks:**
   ```bash
   python manage.py check --deploy
   ```

7. **Launch Production WSGI Server:**
   - **Linux:** `gunicorn --workers 4 --bind 127.0.0.1:8000 config.wsgi:application`
   - **Windows:** `waitress-serve --listen=127.0.0.1:8000 config.wsgi:application`

---

## 🧪 Testing Instructions

The project features a comprehensive test suite of **148 automated tests** covering authentication, model constraints, role permissions, attendance calculations, CSV sanitization, production guards, and open-redirect defenses.

### Run All Tests:
```bash
python manage.py test
```

### Run Tests for a Specific Application:
```bash
# Test authentication and security protections
python manage.py test accounts

# Test student management
python manage.py test students

# Test attendance and calculations
python manage.py test attendance

# Test academics and constraints
python manage.py test academics
```

### Run System Health Check:
```bash
python manage.py check
```

---

## 📸 Screenshots & Visual Layouts

### 1. Administrative Overview Dashboard
*Displays live institutional metrics, active enrollments, and status breakdowns.*
```text
+-----------------------------------------------------------------------------------+
|  [Logo] School Portal        [Search...]              (🔔)  (👤 Admin Rajesh ▼)   |
+-------------------+---------------------------------------------------------------+
| 📊 Dashboard      |  Overview Metrics                                             |
| 👨‍🏫 Teachers       |  +-------------+ +-------------+ +-------------+ +----------+ |
| 🏫 Classes        |  | Students    | | Teachers    | | Classes     | | Today %  | |
| 📚 Subjects       |  | 200 Active  | | 10 Active   | | 8 Sections  | | 94.2%    | |
| 👥 Students       |  +-------------+ +-------------+ +-------------+ +----------+ |
| 📝 Attendance     |                                                               |
| 📈 Reports        |  Attendance Rate Trend (Past 30 Days)    Status Breakdown     |
| ⚙️ Settings       |  [~~~~~~ Line Chart ~~~~~~]             [ (O) Donut Chart ]   |
+-------------------+---------------------------------------------------------------+
```

### 2. Teacher Attendance Taking Sheet
*Quick-mark actions, real-time counts, and student table.*
```text
+-----------------------------------------------------------------------------------+
| Class: Grade 10 - Section A  |  Subject: Physics  |  Date: 2026-10-19             |
+-----------------------------------------------------------------------------------+
| Quick Actions:  [ ✓ Mark All Present ]  [ ✗ Mark All Absent ]                     |
|                                                                                   |
| Roll # | Student ID   | Student Name    | Status Selection          | Remarks     |
|--------|--------------|-----------------|---------------------------|-------------|
| 01     | STU-10A-001  | Aarav Sharma    | (•) Pres  ( ) Abs ( ) Late| [         ] |
| 02     | STU-10A-002  | Ananya Patil    | (•) Pres  ( ) Abs ( ) Late| [         ] |
| 03     | STU-10A-003  | Rohan Deshmukh  | ( ) Pres  (•) Abs ( ) Late| [ Excused ] |
+-----------------------------------------------------------------------------------+
| [ Submit Attendance Records ]                                                     |
+-----------------------------------------------------------------------------------+
```

---

## 🔒 Security Considerations

The application implements defense-in-depth security best practices:

- **CSRF Protection:** Enabled on all state-changing forms. The logout flow strictly enforces `POST` requests with CSRF token verification to prevent Logout-CSRF attacks.
- **Open Redirect Neutralization:** All dynamic redirect parameters (`?next=`) are validated using Django's `url_has_allowed_host_and_scheme()`. External and malicious URLs are stripped and redirected to default safe views.
- **CSV Formula Injection (DDE) Defense:** Exported fields beginning with dangerous spreadsheet triggers (`=`, `+`, `-`, `@`, `|`, `%`, `\t`, `\r`) are sanitized by prepending a single quote `'` to prevent formula execution in Microsoft Excel and Google Sheets.
- **SQL Injection Prevention:** 100% of database interactions utilize Django's parameterized ORM. No raw SQL or unescaped cursor queries are used.
- **Cross-Site Scripting (XSS) Prevention:** Context variables are automatically HTML-escaped by the Django template engine. Zero `|safe` or `mark_safe` bypasses are present in student or attendance views.
- **Session & Cookie Security:** `SESSION_COOKIE_HTTPONLY` is active. Production configurations support `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `X_FRAME_OPTIONS = 'DENY'`, and strict HTTP Strict Transport Security (HSTS).
- **Production Guard:** `settings.py` enforces that `SECRET_KEY` must be set via environment variable when `DEBUG=False`.

---

## ⚠️ Known Limitations

1. **SQLite Concurrency:** SQLite is configured for local development and demonstration. For high-concurrency production deployments with thousands of concurrent roll calls, configure **PostgreSQL**.
2. **Synchronous CSV Generation:** Large reports (>100,000 rows) generate synchronously within the request-response cycle. For enterprise datasets, delegating exports to a background worker (e.g., Celery) is recommended.

---

## 🔮 Future Enhancements

- **Automated SMS & Email Alerts:** Instant notification to guardians upon student absence or tardiness.
- **Biometric & RFID Integration:** Direct API endpoints to ingest logs from turnstiles and biometric scanners.
- **Progressive Web App (PWA):** Offline roll-call caching for instructors with delayed background synchronization.
- **Leave Request Workflow:** Student and teacher portal for submitting and approving leave applications.

---

## 📄 License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.
