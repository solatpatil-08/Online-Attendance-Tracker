# Online Attendance Tracking System

An industry-standard, role-based academic web application built using **Python**, **Django**, and **Bootstrap 5**. The system provides streamlined attendance recording, academic structure management (classes, subjects, and assignments), student profiles, and analytical reporting with CSV exports.

---

## 🚀 Key Features & Architectural Highlights

- **Role-Based Authentication**:
  - Custom `User` model (`accounts.User`) with distinct roles (`ADMIN`, `TEACHER`).
  - Modular architecture with clean separation of concerns.
- **Academic Hierarchy Ready**:
  - Configured for Classes/Divisions, Subjects, and Teacher assignments.
- **Responsive Dashboard**:
  - Polished modern UI with custom CSS variables, Bootstrap 5, and Bootstrap Icons.
  - Role-tailored dashboards for Administrators and Teachers.
- **Secure Configuration**:
  - Decoupled environment settings (`.env` with `python-dotenv`).
  - Django security features enabled (CSRF, X-Frame-Options, Password validation).
- **Fast Local Development**:
  - SQLite database out-of-the-box.
  - Dedicated development user generation script.

---

## 🛠️ Technology Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.13, Django 5.1 |
| **Database** | SQLite3 |
| **Authentication** | Django Auth + Custom `AbstractUser` |
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
│
├── config/                           # Project configuration
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py                   # Central settings (env-aware)
│   ├── urls.py                       # Root URL dispatcher
│   └── wsgi.py
│
├── accounts/                         # Authentication & user roles
│   ├── management/commands/
│   │   └── create_dev_users.py       # Seeds default dev accounts
│   ├── admin.py                      # Custom UserAdmin
│   ├── forms.py                      # Login & profile forms
│   ├── models.py                     # Custom User & TeacherProfile
│   ├── tests.py                      # Authentication & role unit tests
│   ├── urls.py                       # /accounts/ routes
│   └── views.py                      # Login, logout, profile handlers
│
├── academics/                        # Classes, divisions, and subjects
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   └── urls.py
│
├── students/                         # Student records & enrollments
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   └── urls.py
│
├── attendance/                       # Attendance sessions & logs
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   └── urls.py
│
├── dashboard/                        # Central role-based landing views
│   ├── apps.py
│   ├── urls.py
│   └── views.py
│
├── static/                           # Global static assets
│   ├── css/
│   │   └── style.css                 # Custom design system & theme
│   ├── js/
│   │   └── main.js                   # Client interactivity & helpers
│   └── images/                       # Brand and graphic assets
│
└── templates/                        # Global templates
    ├── base.html                     # Standard layout & navigation bar
    ├── accounts/
    │   ├── login.html                # Modern login page
    │   └── profile.html              # User & profile management
    ├── dashboard/
    │   ├── admin_dashboard.html      # Administrative portal
    │   └── teacher_dashboard.html    # Teacher portal
    ├── academics/                    # Module template directories
    ├── students/
    ├── attendance/
    └── reports/
```

---

## 💻 Setup & Installation Guide

### 1. Prerequisites
- Python 3.10 or higher installed on your system.
- Git (optional, for version control).

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

### 4. Configure Environment Variables
Copy `.env.example` to `.env` (already created for local development):
```bash
cp .env.example .env
```

### 5. Apply Database Migrations
```bash
python manage.py makemigrations accounts
python manage.py migrate
```

### 6. Create Seed Development Users
A custom management command is provided to instantly generate testing accounts:
```bash
python manage.py create_dev_users
```

**Default Test Credentials:**
- **Administrator**:
  - Username: `admin`
  - Password: `admin123`
- **Teacher**:
  - Username: `teacher`
  - Password: `teacher123`

*(Optional) Create your own custom superuser:*
```bash
python manage.py createsuperuser
```

### 7. Run Django System Checks & Tests
```bash
# Verify system integrity
python manage.py check

# Run automated unit test suite
python manage.py test
```

### 8. Start the Development Server
```bash
python manage.py runserver
```
Visit the application in your browser at:
`http://127.0.0.1:8000/`

---

## 🗺️ Next Development Phases

1. **Phase 2 - Academics Module**:
   - Academic Year, Semester/Term models.
   - Class/Section (e.g., Grade 10 - A), Subject catalog.
   - Teacher-to-Class-Subject allocation mappings.
2. **Phase 3 - Students Module**:
   - Student profile model (Admission number, Roll number, Guardian contacts).
   - Student listing, registration, search, and filtering views.
3. **Phase 4 - Attendance Module**:
   - Daily and Subject-wise Attendance Session model.
   - Attendance Record model (Present, Absent, Late, Excused).
   - Fast bulk attendance recording interface for teachers.
4. **Phase 5 - Analytics, Reports & CSV Export**:
   - Percentage calculation engines and low-attendance thresholds (<75%).
   - Date range and class-specific report filters.
   - One-click CSV / tabular exports.
