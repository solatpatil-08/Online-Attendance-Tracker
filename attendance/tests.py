import datetime
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone
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

        self.today = timezone.localdate()

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


class AttendanceValidationTests(TestCase):
    def setUp(self):
        self.teacher_assigned = User.objects.create_user(
            username='assigned_teacher',
            email='assigned@example.com',
            password='Password123!',
            role=User.Role.TEACHER
        )
        self.teacher_unassigned = User.objects.create_user(
            username='unassigned_teacher',
            email='unassigned@example.com',
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
            class_teacher=self.teacher_assigned
        )
        self.class_10b = Classroom.objects.create(
            name='Grade 10',
            section='B',
            academic_year=self.academic_year
        )
        self.subject = Subject.objects.create(
            name='Physics',
            code='PHY-101'
        )
        self.assignment = ClassSubjectAssignment.objects.create(
            classroom=self.class_10a,
            subject=self.subject,
            teacher=self.teacher_assigned
        )
        self.student_10a = Student.objects.create(
            student_id='STU-10A-01',
            first_name='Harry',
            last_name='Potter',
            classroom=self.class_10a,
            roll_number=1
        )
        self.student_10b = Student.objects.create(
            student_id='STU-10B-01',
            first_name='Ron',
            last_name='Weasley',
            classroom=self.class_10b,
            roll_number=1
        )
        self.today = timezone.localdate()

    def test_unassigned_teacher_cannot_record_bulk_attendance(self):
        """Teachers cannot record attendance for classes/subjects not assigned to them."""
        roster_data = [{'student': self.student_10a, 'status': Attendance.Status.PRESENT}]
        with self.assertRaises(ValidationError) as ctx:
            AttendanceSession.record_bulk_attendance(
                classroom=self.class_10a,
                subject=self.subject,
                date=self.today,
                recorded_by=self.teacher_unassigned,
                student_records=roster_data
            )
        self.assertIn("not assigned", str(ctx.exception))

    def test_inactive_teacher_cannot_record_bulk_attendance(self):
        """Inactive teacher accounts cannot record attendance."""
        self.teacher_assigned.is_active = False
        self.teacher_assigned.save()

        roster_data = [{'student': self.student_10a, 'status': Attendance.Status.PRESENT}]
        with self.assertRaises(ValidationError) as ctx:
            AttendanceSession.record_bulk_attendance(
                classroom=self.class_10a,
                subject=self.subject,
                date=self.today,
                recorded_by=self.teacher_assigned,
                student_records=roster_data
            )
        self.assertIn("Inactive users cannot record attendance", str(ctx.exception))

    def test_unenrolled_student_rejected_in_bulk_attendance(self):
        """A student not enrolled in the target classroom is rejected during bulk attendance."""
        roster_data = [{'student': self.student_10b, 'status': Attendance.Status.PRESENT}]
        with self.assertRaises(ValidationError) as ctx:
            AttendanceSession.record_bulk_attendance(
                classroom=self.class_10a,
                subject=self.subject,
                date=self.today,
                recorded_by=self.teacher_assigned,
                student_records=roster_data
            )
        self.assertIn("is enrolled in", str(ctx.exception))

    def test_inactive_classroom_rejected(self):
        """Attendance cannot be taken for a deactivated classroom."""
        self.class_10a.is_active = False
        self.class_10a.save()
        roster_data = [{'student': self.student_10a, 'status': Attendance.Status.PRESENT}]
        with self.assertRaises(ValidationError):
            AttendanceSession.record_bulk_attendance(
                classroom=self.class_10a,
                subject=self.subject,
                date=self.today,
                recorded_by=self.teacher_assigned,
                student_records=roster_data
            )

    def test_transaction_rollback_on_failed_bulk_submission(self):
        """If any record in bulk submission fails, database transaction rolls back completely."""
        # Record 1 is valid, Record 2 has student belonging to another classroom
        roster_data = [
            {'student': self.student_10a, 'status': Attendance.Status.PRESENT},
            {'student': self.student_10b, 'status': Attendance.Status.PRESENT},
        ]
        with self.assertRaises(ValidationError):
            AttendanceSession.record_bulk_attendance(
                classroom=self.class_10a,
                subject=self.subject,
                date=self.today,
                recorded_by=self.teacher_assigned,
                student_records=roster_data
            )

        # Confirm nothing was saved in the database
        self.assertEqual(
            AttendanceSession.objects.filter(classroom=self.class_10a, subject=self.subject, date=self.today).count(),
            0
        )
        self.assertEqual(
            Attendance.objects.filter(classroom=self.class_10a, date=self.today).count(),
            0
        )

    def test_missing_or_invalid_status_raises_validation_error(self):
        """Attendance entries with missing or invalid statuses are rejected; unmarked is not allowed."""
        invalid_data = [{'student': self.student_10a, 'status': 'NOT_A_VALID_STATUS'}]
        with self.assertRaises(ValidationError) as ctx:
            AttendanceSession.record_bulk_attendance(
                classroom=self.class_10a,
                subject=self.subject,
                date=self.today,
                recorded_by=self.teacher_assigned,
                student_records=invalid_data
            )
        self.assertIn("Invalid or missing attendance status", str(ctx.exception))

    def test_future_date_rejected(self):
        """Attendance cannot be recorded for a future date."""
        tomorrow = self.today + datetime.timedelta(days=1)
        roster_data = [{'student': self.student_10a, 'status': Attendance.Status.PRESENT}]
        with self.assertRaises(ValidationError) as ctx:
            AttendanceSession.record_bulk_attendance(
                classroom=self.class_10a,
                subject=self.subject,
                date=tomorrow,
                recorded_by=self.teacher_assigned,
                student_records=roster_data
            )
        self.assertIn("cannot be in the future", str(ctx.exception))

    def test_backdated_attendance_limit_for_teacher(self):
        """Teachers cannot record attendance older than the configured limit."""
        old_date = self.today - datetime.timedelta(days=15)
        roster_data = [{'student': self.student_10a, 'status': Attendance.Status.PRESENT}]
        with self.assertRaises(ValidationError) as ctx:
            AttendanceSession.record_bulk_attendance(
                classroom=self.class_10a,
                subject=self.subject,
                date=old_date,
                recorded_by=self.teacher_assigned,
                student_records=roster_data
            )
        self.assertIn("exceeds limit", str(ctx.exception))

    def test_duplicate_submission_updates_existing_session_without_duplication(self):
        """Bulk submission for an existing session updates the records without creating duplicates."""
        roster_1 = [{'student': self.student_10a, 'status': Attendance.Status.PRESENT}]
        AttendanceSession.record_bulk_attendance(
            classroom=self.class_10a,
            subject=self.subject,
            date=self.today,
            recorded_by=self.teacher_assigned,
            student_records=roster_1
        )

        # Submit update with new status
        roster_2 = [{'student': self.student_10a, 'status': Attendance.Status.LATE, 'remarks': 'Traffic delay'}]
        AttendanceSession.record_bulk_attendance(
            classroom=self.class_10a,
            subject=self.subject,
            date=self.today,
            recorded_by=self.teacher_assigned,
            student_records=roster_2
        )

        self.assertEqual(
            AttendanceSession.objects.filter(classroom=self.class_10a, subject=self.subject, date=self.today).count(),
            1
        )
        self.assertEqual(
            Attendance.objects.filter(classroom=self.class_10a, subject=self.subject, date=self.today).count(),
            1
        )
        rec = Attendance.objects.get(student=self.student_10a, date=self.today)
        self.assertEqual(rec.status, Attendance.Status.LATE)
        self.assertEqual(rec.remarks, 'Traffic delay')


class AttendanceTakeViewTests(TestCase):
    def setUp(self):
        self.password = 'Password123!'
        self.admin = User.objects.create_superuser(
            username='admin_boss',
            email='admin@school.com',
            password=self.password
        )
        self.teacher = User.objects.create_user(
            username='teacher_john',
            email='john@school.com',
            password=self.password,
            role=User.Role.TEACHER
        )
        self.unassigned_teacher = User.objects.create_user(
            username='teacher_unassigned',
            email='unassigned@school.com',
            password=self.password,
            role=User.Role.TEACHER
        )
        self.academic_year = AcademicYear.objects.create(
            name='2026-2027',
            start_date=datetime.date(2026, 6, 1),
            end_date=datetime.date(2027, 4, 30),
            is_current=True
        )
        self.classroom = Classroom.objects.create(
            name='Grade 11',
            section='A',
            academic_year=self.academic_year,
            class_teacher=self.teacher
        )
        self.other_classroom = Classroom.objects.create(
            name='Grade 12',
            section='A',
            academic_year=self.academic_year
        )
        self.subject = Subject.objects.create(
            name='Biology',
            code='BIO-101'
        )
        self.assignment = ClassSubjectAssignment.objects.create(
            classroom=self.classroom,
            subject=self.subject,
            teacher=self.teacher
        )
        self.student = Student.objects.create(
            student_id='STU-BIO-01',
            first_name='Luna',
            last_name='Lovegood',
            classroom=self.classroom,
            roll_number=1
        )
        self.student_2 = Student.objects.create(
            student_id='STU-BIO-02',
            first_name='Neville',
            last_name='Longbottom',
            classroom=self.classroom,
            roll_number=2
        )
        self.today = timezone.localdate()

    def test_assigned_teacher_can_access_take_attendance_get(self):
        self.client.login(username='teacher_john', password=self.password)
        url = reverse('attendance:take_attendance')
        response = self.client.get(url, {
            'class_id': self.classroom.id,
            'subject_id': self.subject.id,
            'date': self.today.isoformat()
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Luna Lovegood')
        self.assertContains(response, 'Biology')

    def test_unassigned_teacher_access_take_attendance_forbidden(self):
        self.client.login(username='teacher_unassigned', password=self.password)
        url = reverse('attendance:take_attendance')
        response = self.client.get(url, {
            'class_id': self.classroom.id,
            'subject_id': self.subject.id,
            'date': self.today.isoformat()
        })
        self.assertEqual(response.status_code, 403)

    def test_assigned_teacher_post_attendance_success(self):
        self.client.login(username='teacher_john', password=self.password)
        url = reverse('attendance:take_attendance')
        post_data = {
            'classroom_id': self.classroom.id,
            'subject_id': self.subject.id,
            'date': self.today.isoformat(),
            f'status_{self.student.id}': Attendance.Status.PRESENT,
            f'remarks_{self.student.id}': 'Attentive in lab',
            f'status_{self.student_2.id}': Attendance.Status.ABSENT,
            f'remarks_{self.student_2.id}': 'Sick leave',
            'notes': 'Cell biology microscope lesson'
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)

        session = AttendanceSession.objects.filter(classroom=self.classroom, subject=self.subject, date=self.today).first()
        self.assertIsNotNone(session)
        self.assertEqual(session.records.count(), 2)
        rec1 = session.records.get(student=self.student)
        rec2 = session.records.get(student=self.student_2)
        self.assertEqual(rec1.status, Attendance.Status.PRESENT)
        self.assertEqual(rec1.remarks, 'Attentive in lab')
        self.assertEqual(rec2.status, Attendance.Status.ABSENT)
        self.assertEqual(rec2.remarks, 'Sick leave')

    def test_update_attendance_preserves_records_and_updates_data(self):
        """Controlled edit workflow updates previously recorded session when confirmed."""
        self.client.login(username='teacher_john', password=self.password)
        # Create initial session
        AttendanceSession.record_bulk_attendance(
            classroom=self.classroom,
            subject=self.subject,
            date=self.today,
            recorded_by=self.teacher,
            student_records=[
                {'student': self.student, 'status': Attendance.Status.PRESENT},
                {'student': self.student_2, 'status': Attendance.Status.PRESENT},
            ]
        )

        url = reverse('attendance:take_attendance')
        # Submit confirmed edit updating student 1 to LATE
        post_data = {
            'classroom_id': self.classroom.id,
            'subject_id': self.subject.id,
            'date': self.today.isoformat(),
            'confirm_edit': '1',
            f'status_{self.student.id}': Attendance.Status.LATE,
            f'remarks_{self.student.id}': 'Dentist appointment',
            f'status_{self.student_2.id}': Attendance.Status.PRESENT,
            'notes': 'Updated session notes'
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)

        self.assertEqual(
            AttendanceSession.objects.filter(classroom=self.classroom, subject=self.subject, date=self.today).count(),
            1
        )
        rec1 = Attendance.objects.get(student=self.student, date=self.today)
        self.assertEqual(rec1.status, Attendance.Status.LATE)
        self.assertEqual(rec1.remarks, 'Dentist appointment')

    def test_unconfirmed_edit_does_not_silently_overwrite(self):
        """Attempting to save over an existing session without confirmation is blocked with a warning."""
        self.client.login(username='teacher_john', password=self.password)
        AttendanceSession.record_bulk_attendance(
            classroom=self.classroom,
            subject=self.subject,
            date=self.today,
            recorded_by=self.teacher,
            student_records=[
                {'student': self.student, 'status': Attendance.Status.PRESENT},
                {'student': self.student_2, 'status': Attendance.Status.PRESENT},
            ]
        )

        url = reverse('attendance:take_attendance')
        post_data = {
            'classroom_id': self.classroom.id,
            'subject_id': self.subject.id,
            'date': self.today.isoformat(),
            # Omit confirm_edit
            f'status_{self.student.id}': Attendance.Status.ABSENT,
            f'status_{self.student_2.id}': Attendance.Status.ABSENT,
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)

        # Original records must be preserved
        rec1 = Attendance.objects.get(student=self.student, date=self.today)
        self.assertEqual(rec1.status, Attendance.Status.PRESENT)

    def test_post_with_unmarked_students_rejected_and_preserves_values(self):
        """Unmarked students are not treated as absent; submission is rejected and user entries are preserved."""
        self.client.login(username='teacher_john', password=self.password)
        url = reverse('attendance:take_attendance')
        post_data = {
            'classroom_id': self.classroom.id,
            'subject_id': self.subject.id,
            'date': self.today.isoformat(),
            f'status_{self.student.id}': Attendance.Status.PRESENT,
            f'remarks_{self.student.id}': 'Luna is here',
            # student_2 is left unmarked
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'All students must be marked')
        # Check that submitted value was preserved for student 1
        self.assertContains(response, 'Luna is here')
        # No session was created
        self.assertEqual(AttendanceSession.objects.filter(classroom=self.classroom, date=self.today).count(), 0)

    def test_post_with_missing_fields_redirects_with_error(self):
        """Missing classroom or date triggers an error."""
        self.client.login(username='teacher_john', password=self.password)
        url = reverse('attendance:take_attendance')
        response = self.client.post(url, {
            'classroom_id': '',
            'subject_id': self.subject.id,
            'date': self.today.isoformat(),
        })
        self.assertEqual(response.status_code, 302)

    def test_unassigned_teacher_post_attendance_forbidden(self):
        self.client.login(username='teacher_unassigned', password=self.password)
        url = reverse('attendance:take_attendance')
        post_data = {
            'classroom_id': self.classroom.id,
            'subject_id': self.subject.id,
            'date': self.today.isoformat(),
            f'status_{self.student.id}': Attendance.Status.PRESENT,
            f'status_{self.student_2.id}': Attendance.Status.PRESENT,
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 403)

    def test_admin_can_record_attendance_for_any_class(self):
        self.client.login(username='admin_boss', password=self.password)
        url = reverse('attendance:take_attendance')
        post_data = {
            'classroom_id': self.classroom.id,
            'subject_id': self.subject.id,
            'date': self.today.isoformat(),
            f'status_{self.student.id}': Attendance.Status.LATE,
            f'remarks_{self.student.id}': 'Bus delay',
            f'status_{self.student_2.id}': Attendance.Status.PRESENT,
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)
        record = Attendance.objects.get(student=self.student, date=self.today)
        self.assertEqual(record.status, Attendance.Status.LATE)

    def test_post_with_invalid_status_rejected_with_error(self):
        """Submitting an invalid status is rejected and no attendance is saved."""
        self.client.login(username='teacher_john', password=self.password)
        url = reverse('attendance:take_attendance')
        post_data = {
            'classroom_id': self.classroom.id,
            'subject_id': self.subject.id,
            'date': self.today.isoformat(),
            f'status_{self.student.id}': 'INVALID_STATUS',
            f'status_{self.student_2.id}': Attendance.Status.PRESENT,
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Every student must be marked Present, Absent, Late, or Excused')
        self.assertEqual(AttendanceSession.objects.filter(classroom=self.classroom, date=self.today).count(), 0)

    def test_teacher_invalid_subject_assignment_forbidden(self):
        """Teacher assigned to subject A cannot take attendance for unassigned subject B in the same class."""
        unassigned_subject = Subject.objects.create(name='History', code='HIST-101')
        self.client.login(username='teacher_john', password=self.password)
        url = reverse('attendance:take_attendance')
        post_data = {
            'classroom_id': self.classroom.id,
            'subject_id': unassigned_subject.id,
            'date': self.today.isoformat(),
            f'status_{self.student.id}': Attendance.Status.PRESENT,
            f'status_{self.student_2.id}': Attendance.Status.PRESENT,
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 403)

    def test_teacher_invalid_classroom_assignment_forbidden(self):
        """Teacher assigned to class A cannot take attendance for unassigned class B."""
        self.client.login(username='teacher_john', password=self.password)
        url = reverse('attendance:take_attendance')
        post_data = {
            'classroom_id': self.other_classroom.id,
            'subject_id': self.subject.id,
            'date': self.today.isoformat(),
            f'status_{self.student.id}': Attendance.Status.PRESENT,
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 403)

    def test_inactive_teacher_forbidden_from_posting_attendance(self):
        """Deactivated teacher account is forbidden from submitting attendance (redirected to login)."""
        self.teacher.is_active = False
        self.teacher.save()
        self.client.force_login(self.teacher)
        url = reverse('attendance:take_attendance')
        post_data = {
            'classroom_id': self.classroom.id,
            'subject_id': self.subject.id,
            'date': self.today.isoformat(),
            f'status_{self.student.id}': Attendance.Status.PRESENT,
            f'status_{self.student_2.id}': Attendance.Status.PRESENT,
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
        self.assertEqual(AttendanceSession.objects.filter(classroom=self.classroom, date=self.today).count(), 0)


class AttendanceHistoryAndReportingTests(TestCase):
    """
    Comprehensive tests for:
    1. Attendance History (saved records display, pagination, responsive tables)
    2. Search and Filters (date, date range, student, class, section, subject, teacher, status)
    3. Role-based record scoping (teachers only see authorized records, admins see all)
    4. Student Attendance Report (applicable sessions, formula documentation, enrollment date exclusion)
    5. Class-Wise Report (unmarked vs absent distinction)
    6. CSV Export (permissions, headers, Unicode, formula injection defense)
    """
    def setUp(self):
        self.password = 'SecretPass123!'

        # Users
        self.admin = User.objects.create_superuser(
            username='admin_boss',
            email='admin@school.test',
            password=self.password
        )
        self.teacher_assigned = User.objects.create_user(
            username='teacher_alice',
            email='alice@school.test',
            password=self.password,
            role=User.Role.TEACHER,
            first_name='Alice',
            last_name='Smith'
        )
        self.teacher_other = User.objects.create_user(
            username='teacher_bob',
            email='bob@school.test',
            password=self.password,
            role=User.Role.TEACHER,
            first_name='Bob',
            last_name='Jones'
        )

        # Grant teacher_assigned the CSV export permission
        from django.contrib.auth.models import Permission
        export_perm = Permission.objects.get(codename='can_export_attendance')
        self.teacher_assigned.user_permissions.add(export_perm)
        self.teacher_assigned.save()

        # Academic Setup
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
            class_teacher=self.teacher_assigned
        )
        self.class_10b = Classroom.objects.create(
            name='Grade 10',
            section='B',
            academic_year=self.academic_year,
            class_teacher=self.teacher_other
        )

        self.subj_math = Subject.objects.create(name='Mathematics', code='MATH-101')
        self.subj_science = Subject.objects.create(name='Physics', code='PHYS-101')

        ClassSubjectAssignment.objects.create(
            classroom=self.class_10a,
            subject=self.subj_math,
            teacher=self.teacher_assigned,
            is_active=True
        )
        ClassSubjectAssignment.objects.create(
            classroom=self.class_10b,
            subject=self.subj_science,
            teacher=self.teacher_other,
            is_active=True
        )

        # Students
        # Student 1 enrolled on Oct 1, 2026
        self.student_1 = Student.objects.create(
            student_id='STU-10A-01',
            first_name='Hermione',
            last_name='Granger',
            classroom=self.class_10a,
            roll_number=1,
            enrollment_date=datetime.date(2026, 10, 1)
        )
        # Student 2 enrolled on Oct 10, 2026 (late enrollment)
        self.student_2 = Student.objects.create(
            student_id='STU-10A-02',
            first_name='Ron',
            last_name='Weasley',
            classroom=self.class_10a,
            roll_number=2,
            enrollment_date=datetime.date(2026, 10, 10)
        )
        # Student 3 in Class 10B
        self.student_3 = Student.objects.create(
            student_id='STU-10B-01',
            first_name='Draco',
            last_name='Malfoy',
            classroom=self.class_10b,
            roll_number=1,
            enrollment_date=datetime.date(2026, 10, 1)
        )

        # Populate Sample Attendance Records across multiple dates
        self.date_oct_05 = datetime.date(2026, 10, 5)
        self.date_oct_10 = datetime.date(2026, 10, 10)
        self.date_oct_12 = datetime.date(2026, 10, 12)

        # Session on Oct 5 (Hermione attended; Ron not enrolled yet!)
        self.session_oct_05 = AttendanceSession.objects.create(
            classroom=self.class_10a,
            subject=self.subj_math,
            date=self.date_oct_05,
            recorded_by=self.teacher_assigned
        )
        self.rec_05_1 = Attendance.objects.create(
            session=self.session_oct_05,
            student=self.student_1,
            classroom=self.class_10a,
            subject=self.subj_math,
            date=self.date_oct_05,
            status=Attendance.Status.PRESENT,
            recorded_by=self.teacher_assigned,
            remarks='On time'
        )

        # Session on Oct 10 for 10A
        self.session_oct_10 = AttendanceSession.objects.create(
            classroom=self.class_10a,
            subject=self.subj_math,
            date=self.date_oct_10,
            recorded_by=self.teacher_assigned
        )
        self.rec_10_1 = Attendance.objects.create(
            session=self.session_oct_10,
            student=self.student_1,
            classroom=self.class_10a,
            subject=self.subj_math,
            date=self.date_oct_10,
            status=Attendance.Status.LATE,
            recorded_by=self.teacher_assigned,
            remarks='Late arrival 10 mins'
        )
        self.rec_10_2 = Attendance.objects.create(
            session=self.session_oct_10,
            student=self.student_2,
            classroom=self.class_10a,
            subject=self.subj_math,
            date=self.date_oct_10,
            status=Attendance.Status.ABSENT,
            recorded_by=self.teacher_assigned,
            remarks='=cmd|/c calc'  # Test CSV injection payload
        )

        # Session on Oct 12 for 10A
        self.session_oct_12 = AttendanceSession.objects.create(
            classroom=self.class_10a,
            subject=self.subj_math,
            date=self.date_oct_12,
            recorded_by=self.teacher_assigned
        )
        self.rec_12_1 = Attendance.objects.create(
            session=self.session_oct_12,
            student=self.student_1,
            classroom=self.class_10a,
            subject=self.subj_math,
            date=self.date_oct_12,
            status=Attendance.Status.EXCUSED,
            recorded_by=self.teacher_assigned,
            remarks='Doctor certificate submitted'
        )
        self.rec_12_2 = Attendance.objects.create(
            session=self.session_oct_12,
            student=self.student_2,
            classroom=self.class_10a,
            subject=self.subj_math,
            date=self.date_oct_12,
            status=Attendance.Status.PRESENT,
            recorded_by=self.teacher_assigned
        )

        # Session for 10B on Oct 10 (Draco)
        self.session_10b = AttendanceSession.objects.create(
            classroom=self.class_10b,
            subject=self.subj_science,
            date=self.date_oct_10,
            recorded_by=self.teacher_other
        )
        self.rec_10b = Attendance.objects.create(
            session=self.session_10b,
            student=self.student_3,
            classroom=self.class_10b,
            subject=self.subj_science,
            date=self.date_oct_10,
            status=Attendance.Status.PRESENT,
            recorded_by=self.teacher_other,
            remarks='Excellent lab work'
        )

    # --------------------------------------------------------------------------
    # 1. Attendance History & Scoping Tests
    # --------------------------------------------------------------------------

    def test_unauthenticated_user_redirected_to_login(self):
        """Anonymous access to attendance list is redirected to login."""
        url = reverse('attendance:attendance_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_admin_views_all_attendance_records(self):
        """Administrators have system-wide access to all student records."""
        self.client.login(username='admin_boss', password=self.password)
        url = reverse('attendance:attendance_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # All 6 records exist across 10A and 10B
        self.assertEqual(response.context['total_records'], 6)
        self.assertContains(response, 'Hermione Granger')
        self.assertContains(response, 'Draco Malfoy')

    def test_teacher_only_views_assigned_records(self):
        """Teachers can only view records for classes/subjects they are assigned to."""
        self.client.login(username='teacher_alice', password=self.password)
        url = reverse('attendance:attendance_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Alice is assigned to 10A (5 records), NOT 10B (1 record for Draco)
        self.assertEqual(response.context['total_records'], 5)
        self.assertContains(response, 'Hermione Granger')
        self.assertContains(response, 'Ron Weasley')
        self.assertNotContains(response, 'Draco Malfoy')

    # --------------------------------------------------------------------------
    # 2. Search & Multi-Filter Tests
    # --------------------------------------------------------------------------

    def test_filter_by_exact_date(self):
        """Filter records by an exact date."""
        self.client.login(username='admin_boss', password=self.password)
        url = reverse('attendance:attendance_list')
        response = self.client.get(url, {'date': '2026-10-05'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_records'], 1)
        self.assertContains(response, 'STU-10A-01')

    def test_filter_by_date_range(self):
        """Filter records by start_date and end_date."""
        self.client.login(username='admin_boss', password=self.password)
        url = reverse('attendance:attendance_list')
        response = self.client.get(url, {
            'start_date': '2026-10-10',
            'end_date': '2026-10-12',
        })
        self.assertEqual(response.status_code, 200)
        # Oct 10 has 3 records, Oct 12 has 2 records = 5 records
        self.assertEqual(response.context['total_records'], 5)

    def test_filter_by_student_name_or_id(self):
        """Search records by student name or student ID."""
        self.client.login(username='admin_boss', password=self.password)
        url = reverse('attendance:attendance_list')

        # By surname
        response = self.client.get(url, {'student': 'Granger'})
        self.assertEqual(response.context['total_records'], 3)

        # By student ID
        response = self.client.get(url, {'student': 'STU-10A-02'})
        self.assertEqual(response.context['total_records'], 2)
        self.assertContains(response, 'Ron Weasley')

    def test_filter_by_class_and_section(self):
        """Filter records by class ID and section."""
        self.client.login(username='admin_boss', password=self.password)
        url = reverse('attendance:attendance_list')

        # Filter 10B
        response = self.client.get(url, {'class_id': self.class_10b.id})
        self.assertEqual(response.context['total_records'], 1)
        self.assertContains(response, 'Draco Malfoy')

        # Filter Section A
        response = self.client.get(url, {'section': 'A'})
        self.assertEqual(response.context['total_records'], 5)

    def test_filter_by_subject(self):
        """Filter records by subject ID."""
        self.client.login(username='admin_boss', password=self.password)
        url = reverse('attendance:attendance_list')
        response = self.client.get(url, {'subject_id': self.subj_science.id})
        self.assertEqual(response.context['total_records'], 1)
        self.assertContains(response, 'Physics')

    def test_filter_by_teacher(self):
        """Filter records by recorded_by teacher ID."""
        self.client.login(username='admin_boss', password=self.password)
        url = reverse('attendance:attendance_list')
        response = self.client.get(url, {'teacher_id': self.teacher_other.id})
        self.assertEqual(response.context['total_records'], 1)
        self.assertContains(response, 'Bob Jones')

    def test_filter_by_attendance_status(self):
        """Filter records by attendance status (PRESENT, LATE, ABSENT, EXCUSED)."""
        self.client.login(username='admin_boss', password=self.password)
        url = reverse('attendance:attendance_list')

        response = self.client.get(url, {'status': 'PRESENT'})
        # Oct 5: Hermione, Oct 10: Draco, Oct 12: Ron = 3 Present
        self.assertEqual(response.context['total_records'], 3)

        response = self.client.get(url, {'status': 'ABSENT'})
        self.assertEqual(response.context['total_records'], 1)
        self.assertContains(response, 'Ron Weasley')

        response = self.client.get(url, {'status': 'EXCUSED'})
        self.assertEqual(response.context['total_records'], 1)
        self.assertContains(response, 'Hermione Granger')

    # --------------------------------------------------------------------------
    # 3. CSV Export & Formula Injection Defense Tests
    # --------------------------------------------------------------------------

    def test_admin_can_export_csv(self):
        """Administrators can download attendance records CSV."""
        self.client.login(username='admin_boss', password=self.password)
        url = reverse('attendance:export_csv')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response['Content-Type'])
        self.assertIn('utf-8-sig', response['Content-Type'])
        self.assertIn('attachment; filename=', response['Content-Disposition'])

        content = response.content.decode('utf-8-sig')
        self.assertIn('Attendance Date,Student ID,Roll Number,Student Name', content)
        self.assertIn('Hermione Granger', content)
        self.assertIn('Draco Malfoy', content)

    def test_user_without_export_permission_forbidden(self):
        """Users without can_export_attendance permission receive 403 Forbidden."""
        # Bob does not have can_export_attendance permission
        self.client.login(username='teacher_bob', password=self.password)
        url = reverse('attendance:export_csv')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_teacher_with_permission_only_exports_scoped_records(self):
        """Teacher with export permission can only export authorized records."""
        self.client.login(username='teacher_alice', password=self.password)
        url = reverse('attendance:export_csv')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8-sig')
        self.assertIn('Hermione Granger', content)
        self.assertIn('Ron Weasley', content)
        # Unauthorized student Draco Malfoy must NOT be present in Alice's export
        self.assertNotIn('Draco Malfoy', content)

    def test_csv_formula_injection_defense(self):
        """Untrusted strings starting with '=', '+', '-', '@', '\t', '\r' are escaped with single quote."""
        self.client.login(username='admin_boss', password=self.password)
        url = reverse('attendance:export_csv')
        response = self.client.get(url, {'student': 'Ron'})
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8-sig')
        # Check that '=cmd|/c calc' remarks was sanitized to "'=cmd|/c calc"
        self.assertIn("'=cmd|/c calc", content)

    # --------------------------------------------------------------------------
    # 4. Class-Wise Report & Unmarked vs Absent Distinction Tests
    # --------------------------------------------------------------------------

    def test_class_wise_report_distinguishes_unmarked_from_absent(self):
        """
        Class report correctly identifies enrolled students, recorded attendance,
        present, late, excused, explicitly marked absent, and unmarked students.
        """
        self.client.login(username='admin_boss', password=self.password)
        url = reverse('attendance:reports')
        # On Oct 10:
        # Class 10A has 2 enrolled students (Hermione, Ron). Both were recorded: 1 LATE, 1 ABSENT.
        # Total enrolled: 2, Recorded: 2, Present: 0, Late: 1, Absent: 1, Excused: 0, Unmarked: 0.
        response = self.client.get(url, {'date': '2026-10-10'})
        self.assertEqual(response.status_code, 200)

        class_summaries = response.context['class_summaries']
        cr_10a_summary = next(c for c in class_summaries if c['classroom'].id == self.class_10a.id)

        self.assertEqual(cr_10a_summary['total_enrolled'], 2)
        self.assertEqual(cr_10a_summary['total_recorded'], 2)
        self.assertEqual(cr_10a_summary['late'], 1)
        self.assertEqual(cr_10a_summary['absent'], 1)
        self.assertEqual(cr_10a_summary['unmarked'], 0)
        self.assertEqual(cr_10a_summary['status_label'], 'Recorded')
        # Rate: (0 + 1) / 2 = 50.0%
        self.assertEqual(cr_10a_summary['percentage'], 50.0)

    def test_unrecorded_class_shows_all_enrolled_as_unmarked_and_not_absent(self):
        """
        If a class has not had attendance recorded on a date, all enrolled students
        are marked as 'Unmarked Students', and absent count remains 0.
        """
        self.client.login(username='admin_boss', password=self.password)
        url = reverse('attendance:reports')
        # On Oct 05: Class 10B had NO attendance taken.
        response = self.client.get(url, {'date': '2026-10-05'})
        self.assertEqual(response.status_code, 200)

        class_summaries = response.context['class_summaries']
        cr_10b_summary = next(c for c in class_summaries if c['classroom'].id == self.class_10b.id)

        self.assertEqual(cr_10b_summary['total_enrolled'], 1)
        self.assertEqual(cr_10b_summary['total_recorded'], 0)
        self.assertEqual(cr_10b_summary['absent'], 0)  # NOT marked absent!
        self.assertEqual(cr_10b_summary['unmarked'], 1)  # 1 unmarked
        self.assertEqual(cr_10b_summary['status_label'], 'Not Recorded')
        self.assertIsNone(cr_10b_summary['percentage'])

    # --------------------------------------------------------------------------
    # 5. Student Attendance Report & Enrollment Date Rule Tests
    # --------------------------------------------------------------------------

    def test_student_report_list_scoping(self):
        """Student report list is scoped by role and active classrooms."""
        self.client.login(username='teacher_alice', password=self.password)
        url = reverse('attendance:student_report_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Alice teaches 10A (Hermione, Ron)
        self.assertContains(response, 'Hermione Granger')
        self.assertContains(response, 'Ron Weasley')
        self.assertNotContains(response, 'Draco Malfoy')

    def test_student_report_detail_authorization(self):
        """Assigned teacher can view student dossier; unassigned teacher is forbidden."""
        url = reverse('attendance:student_report_detail', kwargs={'pk': self.student_1.pk})

        # Alice assigned to 10A -> 200 OK
        self.client.login(username='teacher_alice', password=self.password)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Bob assigned to 10B -> 403 Forbidden
        self.client.login(username='teacher_bob', password=self.password)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_student_attendance_percentage_formula_and_enrollment_scoping(self):
        """
        Sessions prior to student's enrollment date are strictly excluded.
        Formula: (Present + Late) / Total Applicable Sessions * 100%.
        """
        # Ron Weasley enrolled on Oct 10, 2026.
        # Oct 5 session occurred before Ron's enrollment date.
        # Ron has 2 sessions: Oct 10 (ABSENT) and Oct 12 (PRESENT).
        self.client.login(username='admin_boss', password=self.password)
        url = reverse('attendance:student_report_detail', kwargs={'pk': self.student_2.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Total applicable must be 2 (Oct 10 and Oct 12), NOT 3
        self.assertEqual(response.context['total_applicable'], 2)
        self.assertEqual(response.context['present_count'], 1)
        self.assertEqual(response.context['absent_count'], 1)
        self.assertEqual(response.context['late_count'], 0)
        self.assertEqual(response.context['excused_count'], 0)
        # Attended: 1 / 2 = 50.0%
        self.assertEqual(response.context['attendance_percentage'], 50.0)

        # Verify formula documentation is rendered on page
        self.assertContains(response, 'Attendance Percentage Calculation Formula')
        self.assertContains(response, 'Total Applicable Attendance Sessions')

    def test_student_detail_csv_export(self):
        """Single student's attendance history log can be exported to CSV."""
        self.client.login(username='admin_boss', password=self.password)
        url = reverse('attendance:student_report_export_csv', kwargs={'pk': self.student_1.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response['Content-Type'])
        content = response.content.decode('utf-8-sig')
        self.assertIn('Hermione Granger', content)
        self.assertIn('MATH-101', content)

