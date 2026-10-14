import datetime
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from accounts.models import User
from .models import AcademicYear, Classroom, Subject, ClassSubjectAssignment


class AcademicsModelTests(TestCase):
    def setUp(self):
        self.teacher_user = User.objects.create_user(
            username='prof_smith',
            email='smith@example.com',
            password='Password123!',
            role=User.Role.TEACHER
        )
        self.admin_user = User.objects.create_user(
            username='admin_boss',
            email='boss@example.com',
            password='Password123!',
            role=User.Role.ADMIN
        )

        self.year_2026 = AcademicYear.objects.create(
            name='2026-2027',
            start_date=datetime.date(2026, 6, 1),
            end_date=datetime.date(2027, 4, 30),
            is_current=True
        )

    def test_academic_year_date_validation(self):
        """End date must be strictly after start date."""
        invalid_year = AcademicYear(
            name='Invalid Year',
            start_date=datetime.date(2026, 12, 1),
            end_date=datetime.date(2026, 11, 1),
            is_current=False
        )
        with self.assertRaises(ValidationError):
            invalid_year.clean()

    def test_single_current_academic_year(self):
        """Setting a new academic year to is_current=True sets others to False."""
        year_2027 = AcademicYear.objects.create(
            name='2027-2028',
            start_date=datetime.date(2027, 6, 1),
            end_date=datetime.date(2028, 4, 30),
            is_current=True
        )
        self.year_2026.refresh_from_db()
        self.assertFalse(self.year_2026.is_current)
        self.assertTrue(year_2027.is_current)

    def test_classroom_creation_and_uniqueness(self):
        """Classroom with duplicate name, section, and academic year violates constraint."""
        Classroom.objects.create(
            name='Grade 10',
            section='A',
            academic_year=self.year_2026,
            class_teacher=self.teacher_user
        )

        duplicate_class = Classroom(
            name='Grade 10',
            section='A',
            academic_year=self.year_2026
        )
        with self.assertRaises((ValidationError, IntegrityError)):
            duplicate_class.save()

    def test_classroom_teacher_role_validation(self):
        """Only users with TEACHER role can be assigned as class_teacher."""
        classroom = Classroom(
            name='Grade 9',
            section='B',
            academic_year=self.year_2026,
            class_teacher=self.admin_user
        )
        with self.assertRaises(ValidationError):
            classroom.clean()

    def test_subject_unique_code(self):
        """Subject code must be unique."""
        Subject.objects.create(name='Mathematics', code='MATH-101')
        duplicate_subject = Subject(name='Adv Mathematics', code='MATH-101')
        with self.assertRaises((ValidationError, IntegrityError)):
            duplicate_subject.save()

    def test_class_subject_assignment(self):
        """Ensure class subject assignments and teacher validations work."""
        classroom = Classroom.objects.create(
            name='Grade 10',
            section='B',
            academic_year=self.year_2026,
            class_teacher=self.teacher_user
        )
        subject = Subject.objects.create(name='Physics', code='PHY-101')

        assignment = ClassSubjectAssignment.objects.create(
            classroom=classroom,
            subject=subject,
            teacher=self.teacher_user
        )
        self.assertEqual(str(assignment), f"Grade 10 - B - Physics (Teacher: prof_smith)")

        # Duplicate assignment for same classroom and subject should fail
        dup_assignment = ClassSubjectAssignment(
            classroom=classroom,
            subject=subject,
            teacher=self.teacher_user
        )
        with self.assertRaises((ValidationError, IntegrityError)):
            dup_assignment.save()
