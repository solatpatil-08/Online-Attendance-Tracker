import datetime
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from accounts.models import User
from academics.models import AcademicYear, Classroom, Subject, ClassSubjectAssignment
from students.models import Student
from .models import AttendanceSession, Attendance


class AttendanceModelTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            username='teacher_mary',
            email='mary@example.com',
            password='Password123!',
            role=User.Role.TEACHER
        )

        self.academic_year = AcademicYear.objects.create(
            name='2026-2027',
            start_date=datetime.date(2026, 6, 1),
            end_date=datetime.date(2027, 4, 30),
            is_current=True
        )

        self.class_10a = Classroom.objects.create(
            name='Grade 10',
            section='A',
            academic_year=self.academic_year,
            class_teacher=self.teacher
        )
        self.class_10b = Classroom.objects.create(
            name='Grade 10',
            section='B',
            academic_year=self.academic_year,
            class_teacher=self.teacher
        )

        self.subject = Subject.objects.create(
            name='Chemistry',
            code='CHEM-101'
        )

        self.assignment = ClassSubjectAssignment.objects.create(
            classroom=self.class_10a,
            subject=self.subject,
            teacher=self.teacher
        )

        self.student_10a = Student.objects.create(
            student_id='STU-10A-01',
            first_name='Emma',
            last_name='Watson',
            classroom=self.class_10a,
            roll_number=1
        )
        self.student_10b = Student.objects.create(
            student_id='STU-10B-01',
            first_name='Daniel',
            last_name='Radcliffe',
            classroom=self.class_10b,
            roll_number=1
        )

        self.today = datetime.date(2026, 10, 10)

    def test_attendance_session_creation(self):
        """AttendanceSession successfully aggregates class, subject, and date."""
        session = AttendanceSession.objects.create(
            classroom=self.class_10a,
            subject=self.subject,
            date=self.today,
            recorded_by=self.teacher
        )
        self.assertEqual(session.records.count(), 0)
        self.assertIn('Grade 10 - A', str(session))

    def test_student_class_validation(self):
        """A student cannot have attendance marked for a classroom they do not belong to."""
        session = AttendanceSession.objects.create(
            classroom=self.class_10a,
            subject=self.subject,
            date=self.today,
            recorded_by=self.teacher
        )

        # student_10b belongs to class_10b, trying to mark in class_10a must fail
        attendance = Attendance(
            session=session,
            student=self.student_10b,
            classroom=self.class_10a,
            subject=self.subject,
            date=self.today,
            status=Attendance.Status.PRESENT,
            recorded_by=self.teacher
        )
        with self.assertRaises(ValidationError):
            attendance.clean()

    def test_prevent_duplicate_attendance_record(self):
        """The same student cannot have duplicate attendance for the same class, subject, and date."""
        session = AttendanceSession.objects.create(
            classroom=self.class_10a,
            subject=self.subject,
            date=self.today,
            recorded_by=self.teacher
        )

        Attendance.objects.create(
            session=session,
            student=self.student_10a,
            classroom=self.class_10a,
            subject=self.subject,
            date=self.today,
            status=Attendance.Status.PRESENT,
            recorded_by=self.teacher
        )

        duplicate = Attendance(
            session=session,
            student=self.student_10a,
            classroom=self.class_10a,
            subject=self.subject,
            date=self.today,
            status=Attendance.Status.LATE,
            recorded_by=self.teacher
        )
        with self.assertRaises((ValidationError, IntegrityError)):
            duplicate.save()

    def test_bulk_attendance_transactional_record(self):
        """AttendanceSession.record_bulk_attendance atomically creates session and student records."""
        student_2 = Student.objects.create(
            student_id='STU-10A-02',
            first_name='Rupert',
            last_name='Grint',
            classroom=self.class_10a,
            roll_number=2
        )

        roster_data = [
            {'student': self.student_10a, 'status': Attendance.Status.PRESENT},
            {'student': student_2, 'status': Attendance.Status.ABSENT, 'remarks': 'Sick leave'},
        ]

        session = AttendanceSession.record_bulk_attendance(
            classroom=self.class_10a,
            subject=self.subject,
            date=self.today,
            recorded_by=self.teacher,
            student_records=roster_data,
            notes='Mid-term chemistry lab session'
        )

        self.assertEqual(session.records.count(), 2)
        rec1 = Attendance.objects.get(student=self.student_10a, date=self.today)
        rec2 = Attendance.objects.get(student=student_2, date=self.today)

        self.assertEqual(rec1.status, Attendance.Status.PRESENT)
        self.assertEqual(rec2.status, Attendance.Status.ABSENT)
        self.assertEqual(rec2.remarks, 'Sick leave')
