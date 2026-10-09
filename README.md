# Online Attendance Tracking System

An industry-standard, role-based academic web application built using **Python**, **Django**, and **Bootstrap 5**. The system provides streamlined attendance recording, academic structure management (classes, subjects, and assignments), student profiles, and analytical reporting with CSV exports.

---

## 🚀 Key Features & Architectural Highlights

- **Role & Permission Management**:
  - Custom `User` model ([`accounts.User`](file:///c:/Users/pratap%20solat/OneDrive/Online%20Attendance%20Tracking%20System/accounts/models.py)) integrated with Django Groups (`Administrator`, `Teacher`) and Django Permissions (`can_mark_attendance`, `can_view_reports`, `can_export_attendance`).
  - Automated role-group synchronization upon user save and post-migration signals.
- **Academic Hierarchy**:
  - `AcademicYear` with automated single-active-year enforcement.
  - `Classroom` (Class & Section) with unique constraint `(name, section, academic_year)`.
  - `Subject` catalog with unique indexing on `code`.
  - `ClassSubjectAssignment` mapping classes and subjects to teachers with conflict prevention.
- **Student Information**:
  - `Student` model with unique `student_id`, personal data, guardian contact, class assignment, and per-class unique `roll_number`.
- **Attendance Architecture**:
  - `AttendanceSession` aggregating class, subject, date, teacher, and notes.
  - `Attendance` records with statuses: `Present`, `Absent`, `Late`, `Excused`.
  - Database constraint preventing duplicate records per student, class, subject, and date.
  - Model-level validation enforcing that students belong to the selected classroom.
  - ACID-compliant transactional bulk recording via `@transaction.atomic`.
- **Comprehensive Django Admin**:
  - Registered with search fields, list filters, inline allocations, read-only timestamps, and autocomplete widgets.
- **Responsive Dashboard**:
  - Live metric computation from ORM models for Administrators and Teachers.

---

## 🛠️ Technology Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.13, Django 5.1 |
| **Database** | SQLite3 |
| **Authentication & Roles** | Django Auth + Custom `AbstractUser` + Django Groups & Permissions |
| **Frontend** | Django Templates, Bootstrap 5.3, Bootstrap Icons |
| **Forms & Styling** | Django Crispy Forms (Bootstrap 5 pack), Custom CSS |
| **Client-side Interactivity** | Vanilla JavaScript |

---

## 📁 Project Directory Structure

```text
Online Attendance Tracking System/
├── .env                              # Local environment variables (git-ignored)
├── .env.example                      # Template for environment configuration
├── .gitignore                        # Git ignore rules for Django & Python
├── manage.py                         # Django administrative runner
├── requirements.txt                  # Python dependencies
├── README.md                         # Documentation & runbook
├── db.sqlite3                        # Initialized SQLite database
│
├── config/                           # Project configuration
│   ├── settings.py                   # Central settings (env-aware)
│   ├── urls.py                       # Root URL dispatcher
│   ├── asgi.py                       # ASGI entrypoint
│   └── wsgi.py                       # WSGI entrypoint
│
├── accounts/                         # User authentication, roles & permissions
│   ├── management/commands/
│   │   ├── create_dev_users.py       # Seeds default dev accounts with groups
│   │   └── seed_sample_data.py       # Seeds complete academic & student dataset
│   ├── admin.py                      # Custom UserAdmin & TeacherProfileAdmin
│   ├── forms.py                      # Login & profile forms
│   ├── models.py                     # Custom User & TeacherProfile
│   ├── signals.py                    # Group synchronization & role permissions
│   ├── tests.py                      # Authentication & role unit tests
│   ├── urls.py                       # /accounts/ routes
│   └── views.py                      # Login, logout, profile handlers
│
├── academics/                        # Classes, divisions, and subjects
│   ├── admin.py                      # AcademicYear, Classroom, Subject, Assignment admin
│   ├── apps.py
│   ├── models.py                     # AcademicYear, Classroom, Subject, ClassSubjectAssignment
│   ├── tests.py                      # Academic model constraint tests
│   └── urls.py
│
├── students/                         # Student records & enrollments
│   ├── admin.py                      # StudentAdmin with filters, search & fieldsets
│   ├── apps.py
│   ├── models.py                     # Student model with validation
│   ├── tests.py                      # Student model uniqueness & validation tests
│   └── urls.py
│
├── attendance/                       # Attendance sessions & logs
│   ├── admin.py                      # AttendanceSessionAdmin with inlines & AttendanceAdmin
│   ├── apps.py
│   ├── models.py                     # AttendanceSession, Attendance records & transactions
│   ├── tests.py                      # Session & record constraint & class validation tests
│   └── urls.py
│
├── dashboard/                        # Central role-based landing views
│   ├── apps.py
│   ├── urls.py
│   └── views.py                      # Admin & Teacher live database metric routers
│
├── static/                           # Global static assets
│   ├── css/
│   │   └── style.css                 # Custom design system & theme
│   ├── js/
│   │   └── main.js                   # Client interactivity & helpers
│   └── images/
│
└── templates/                        # Global templates
    ├── base.html                     # Standard layout & navigation bar
    ├── accounts/
    │   ├── login.html                # Modern login page
    │   └── profile.html              # User & profile management
    ├── dashboard/
    │   ├── admin_dashboard.html      # Administrative portal (live metrics)
    │   └── teacher_dashboard.html    # Teacher portal (live assignments)
    ├── academics/
    ├── students/
    ├── attendance/
    └── reports/
```

---

## 💻 Setup & Installation Guide

### 1. Prerequisites
- Python 3.10 or higher installed on your system.

### 2. Create and Activate Virtual Environment

**Windows (PowerShell / Command Prompt):**
```powershell
python -m venv .venv
.venv\Scripts\activate
```

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Apply Database Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### 5. Create Seed Accounts & Sample Data
Two management commands are provided for immediate testing:

```bash
# 1. Create standard Administrator & Teacher test accounts
python manage.py create_dev_users

# 2. Populate complete sample academic structure, classes, students, and attendance
python manage.py seed_sample_data
```

**Default Test Credentials:**
- **Administrator**:
  - Username: `admin`
  - Password: `admin123`
- **Teacher**:
  - Username: `teacher`
  - Password: `teacher123`

### 6. Run System Checks & Automated Tests
```bash
# Verify system integrity
python manage.py check

# Run full automated test suite (22 tests across all apps)
python manage.py test
```

### 7. Start the Development Server
```bash
python manage.py runserver
```
Visit the application in your browser at:
`http://127.0.0.1:8000/`

Django Admin interface:
`http://127.0.0.1:8000/admin/`

---

## 🗺️ Next Development Phase: Frontend Views & Workflows

With the database layer and admin operational:
1. **Academics & Student Management UI**:
   - Web views to list, create, edit classes, subjects, and student rosters.
2. **Interactive Attendance Sheet UI**:
   - Dedicated teacher attendance taking sheet with quick toggle (Present / Absent / Late / Excused), select-all helpers, and single-click submit.
3. **Analytics, Reporting & CSV Export**:
   - Date-range and class-specific filters, percentage calculations, and CSV downloads.
