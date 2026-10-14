import datetime
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from academics.models import AcademicYear, Classroom
from .models import Student


class StudentModelTests(TestCase):
    def setUp(self):
        self.academic_year = AcademicYear.objects.create(
            name='2026-2027',
            start_date=datetime.date(2026, 6, 1),
            end_date=datetime.date(2027, 4, 30),
            is_current=True
        )
        self.classroom = Classroom.objects.create(
            name='Grade 10',
            section='A',
            academic_year=self.academic_year
        )

    def test_student_creation_and_attributes(self):
        """Student created with valid attributes renders proper string representation."""
        student = Student.objects.create(
            student_id='STU-001',
            first_name='Alex',
            last_name='Morgan',
            gender=Student.Gender.FEMALE,
            date_of_birth=datetime.date(2010, 5, 14),
            classroom=self.classroom,
            roll_number=1,
            email='alex@example.com'
        )
        self.assertEqual(student.full_name, 'Alex Morgan')
        self.assertIn('STU-001', str(student))

    def test_unique_student_id(self):
        """Student ID must be globally unique."""
        Student.objects.create(
            student_id='STU-UNIQUE',
            first_name='John',
            last_name='Doe',
            classroom=self.classroom
        )
        duplicate = Student(
            student_id='STU-UNIQUE',
            first_name='Jane',
            last_name='Doe',
            classroom=self.classroom
        )
        with self.assertRaises((ValidationError, IntegrityError)):
            duplicate.save()

    def test_unique_roll_number_per_classroom(self):
        """Roll numbers must be unique within a single classroom."""
        Student.objects.create(
            student_id='STU-101',
            first_name='Sam',
            last_name='Taylor',
            classroom=self.classroom,
            roll_number=5
        )
        duplicate_roll = Student(
            student_id='STU-102',
            first_name='Robin',
            last_name='Williams',
            classroom=self.classroom,
            roll_number=5
        )
        with self.assertRaises((ValidationError, IntegrityError)):
            duplicate_roll.save()

    def test_date_of_birth_future_validation(self):
        """Date of birth cannot be in the future."""
        future_date = datetime.date.today() + datetime.timedelta(days=10)
        student = Student(
            student_id='STU-FUTURE',
            first_name='Baby',
            last_name='Future',
            classroom=self.classroom,
            date_of_birth=future_date
        )
        with self.assertRaises(ValidationError):
            student.clean()

    def test_inactive_classroom_validation(self):
        """Cannot assign active student to inactive classroom."""
        inactive_classroom = Classroom.objects.create(
            name='Grade 12',
            section='Z',
            academic_year=self.academic_year,
            is_active=False
        )
        student = Student(
            student_id='STU-INACTIVE-CLASS',
            first_name='Mark',
            last_name='Spencer',
            classroom=inactive_classroom,
            is_active=True
        )
        with self.assertRaises(ValidationError):
            student.clean()
