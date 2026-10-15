import datetime
from django.test import TestCase, Client
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from accounts.models import User
from academics.models import AcademicYear, Classroom, Subject, ClassSubjectAssignment
from attendance.models import Attendance, AttendanceSession
from .models import Student
from .forms import StudentForm


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
        self.assertEqual(student.get_absolute_url(), f'/students/{student.pk}/')

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

    def test_delete_prevented_when_attendance_exists(self):
        """Model level delete() prevents accidental loss of attendance history."""
        teacher = User.objects.create_user(
            username='teacher_m', role=User.Role.TEACHER, password='Password123!'
        )
        subject = Subject.objects.create(name='Math', code='MATH-1')
        student = Student.objects.create(
            student_id='STU-ATT-01',
            first_name='Harry',
            last_name='Potter',
            classroom=self.classroom
        )
        session = AttendanceSession.objects.create(
            classroom=self.classroom,
            subject=subject,
            date=datetime.date(2026, 10, 1),
            recorded_by=teacher
        )
        Attendance.objects.create(
            session=session,
            student=student,
            classroom=self.classroom,
            subject=subject,
            date=datetime.date(2026, 10, 1),
            status=Attendance.Status.PRESENT,
            recorded_by=teacher
        )
        with self.assertRaises(ValidationError):
            student.delete()


class StudentFormTests(TestCase):
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
            academic_year=self.academic_year,
            is_active=True
        )
        self.inactive_classroom = Classroom.objects.create(
            name='Grade 11',
            section='B',
            academic_year=self.academic_year,
            is_active=False
        )

    def test_valid_form_data(self):
        form_data = {
            'student_id': 'STU-FORM-001',
            'first_name': 'Hermione',
            'last_name': 'Granger',
            'classroom': self.classroom.pk,
            'roll_number': 1,
            'gender': Student.Gender.FEMALE,
            'date_of_birth': '2010-09-19',
            'enrollment_date': '2026-06-01',
            'email': 'hermione@hogwarts.edu',
            'phone_number': '1234567890',
            'guardian_name': 'Mr. Granger',
            'guardian_phone': '0987654321',
            'is_active': True,
        }
        form = StudentForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_duplicate_student_id(self):
        Student.objects.create(
            student_id='STU-EXISTING',
            first_name='Ron',
            last_name='Weasley',
            classroom=self.classroom
        )
        form_data = {
            'student_id': 'STU-EXISTING',
            'first_name': 'George',
            'last_name': 'Weasley',
            'classroom': self.classroom.pk,
            'enrollment_date': '2026-06-01',
            'is_active': True,
        }
        form = StudentForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('student_id', form.errors)

    def test_form_inactive_classroom_for_active_student(self):
        form_data = {
            'student_id': 'STU-INACTIVE-TEST',
            'first_name': 'Percy',
            'last_name': 'Weasley',
            'classroom': self.inactive_classroom.pk,
            'enrollment_date': '2026-06-01',
            'is_active': True,
        }
        form = StudentForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('classroom', form.errors)

    def test_form_duplicate_roll_number(self):
        Student.objects.create(
            student_id='STU-ROLL-1',
            first_name='Luna',
            last_name='Lovegood',
            classroom=self.classroom,
            roll_number=3
        )
        form_data = {
            'student_id': 'STU-ROLL-2',
            'first_name': 'Neville',
            'last_name': 'Longbottom',
            'classroom': self.classroom.pk,
            'roll_number': 3,
            'enrollment_date': '2026-06-01',
            'is_active': True,
        }
        form = StudentForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('roll_number', form.errors)


class StudentViewsTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Admin user
        self.admin_user = User.objects.create_user(
            username='admin_boss',
            email='admin@school.edu',
            password='Password123!',
            role=User.Role.ADMIN
        )

        # Teacher user
        self.teacher_user = User.objects.create_user(
            username='teacher_john',
            email='john@school.edu',
            password='Password123!',
            role=User.Role.TEACHER
        )

        # Other teacher
        self.other_teacher = User.objects.create_user(
            username='teacher_other',
            email='other@school.edu',
            password='Password123!',
            role=User.Role.TEACHER
        )

        # Academic structure
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
            class_teacher=self.teacher_user,
            is_active=True
        )
        self.class_10b = Classroom.objects.create(
            name='Grade 10',
            section='B',
            academic_year=self.academic_year,
            class_teacher=self.other_teacher,
            is_active=True
        )

        self.subject = Subject.objects.create(name='Physics', code='PHY-101')
        ClassSubjectAssignment.objects.create(
            classroom=self.class_10a,
            subject=self.subject,
            teacher=self.teacher_user
        )

        # Create students
        self.student_10a = Student.objects.create(
            student_id='STU-10A-001',
            first_name='Alice',
            last_name='Smith',
            classroom=self.class_10a,
            roll_number=1,
            email='alice@school.edu',
            phone_number='1112223333',
            is_active=True
        )
        self.student_10a_inactive = Student.objects.create(
            student_id='STU-10A-002',
            first_name='Bob',
            last_name='Jones',
            classroom=self.class_10a,
            roll_number=2,
            is_active=False
        )
        self.student_10b = Student.objects.create(
            student_id='STU-10B-001',
            first_name='Charlie',
            last_name='Brown',
            classroom=self.class_10b,
            roll_number=1,
            is_active=True
        )

    # 1. Student List View & Security
    def test_admin_can_view_student_list(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('students:student_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alice Smith')
        self.assertContains(response, 'STU-10A-001')
        self.assertContains(response, 'Grade 10 - A')

    def test_teacher_sees_only_assigned_students(self):
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('students:student_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alice Smith')
        self.assertNotContains(response, 'Charlie Brown')

    def test_unauthenticated_user_redirected_to_login(self):
        response = self.client.get(reverse('students:student_list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response.url)

    # 2. Searching
    def test_search_by_student_id(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('students:student_list'), {'q': '10A-001'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alice Smith')
        self.assertNotContains(response, 'Charlie Brown')

    def test_search_by_name(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('students:student_list'), {'q': 'Charlie'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Charlie Brown')
        self.assertNotContains(response, 'Alice Smith')

    # 3. Filtering
    def test_filter_by_classroom(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('students:student_list'), {'classroom': str(self.class_10b.pk)})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Charlie Brown')
        self.assertNotContains(response, 'Alice Smith')

    def test_filter_by_section(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('students:student_list'), {'section': 'B'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Charlie Brown')
        self.assertNotContains(response, 'Alice Smith')

    def test_filter_by_active_status(self):
        self.client.force_login(self.admin_user)
        # Inactive only
        response = self.client.get(reverse('students:student_list'), {'status': 'inactive'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Bob Jones')
        self.assertNotContains(response, 'Alice Smith')

        # Active only
        response = self.client.get(reverse('students:student_list'), {'status': 'active'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alice Smith')
        self.assertNotContains(response, 'Bob Jones')

        # All statuses
        response = self.client.get(reverse('students:student_list'), {'status': 'all'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alice Smith')
        self.assertContains(response, 'Bob Jones')

    # 4. Pagination & Query Parameters Preservation
    def test_pagination_and_query_preservation(self):
        self.client.force_login(self.admin_user)
        # Create 12 more students in 10A to trigger pagination (>10)
        for i in range(3, 16):
            Student.objects.create(
                student_id=f'STU-10A-{i:03d}',
                first_name=f'Student{i}',
                last_name='Test',
                classroom=self.class_10a,
                roll_number=i,
                is_active=True
            )
        response = self.client.get(reverse('students:student_list'), {'classroom': str(self.class_10a.pk), 'page': '2'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_paginated'])
        self.assertEqual(response.context['page_obj'].number, 2)
        # Check query_string in context preserves classroom filter without page
        self.assertIn(f'classroom={self.class_10a.pk}', response.context['query_string'])
        self.assertNotIn('page=', response.context['query_string'])

    # 5. Add Student (CreateView)
    def test_admin_can_create_student(self):
        self.client.force_login(self.admin_user)
        create_url = reverse('students:student_create')
        post_data = {
            'student_id': 'STU-NEW-001',
            'first_name': 'David',
            'last_name': 'Miller',
            'classroom': self.class_10a.pk,
            'roll_number': 20,
            'enrollment_date': '2026-06-01',
            'email': 'david@school.edu',
            'phone_number': '555-0101',
            'is_active': True,
        }
        response = self.client.post(create_url, post_data)
        self.assertEqual(response.status_code, 302)
        new_student = Student.objects.get(student_id='STU-NEW-001')
        self.assertEqual(new_student.full_name, 'David Miller')
        self.assertEqual(new_student.classroom, self.class_10a)

    def test_teacher_cannot_create_student_forbidden(self):
        self.client.force_login(self.teacher_user)
        create_url = reverse('students:student_create')
        response = self.client.get(create_url)
        self.assertEqual(response.status_code, 403)

    def test_create_duplicate_student_id_fails(self):
        self.client.force_login(self.admin_user)
        create_url = reverse('students:student_create')
        post_data = {
            'student_id': self.student_10a.student_id,  # duplicate
            'first_name': 'Duplicate',
            'last_name': 'Student',
            'classroom': self.class_10a.pk,
            'enrollment_date': '2026-06-01',
            'is_active': True,
        }
        response = self.client.post(create_url, post_data)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'student_id', f"A student with enrollment ID '{self.student_10a.student_id}' already exists. Student IDs must be unique.")

    # 6. Edit Student (UpdateView)
    def test_admin_can_edit_student(self):
        self.client.force_login(self.admin_user)
        edit_url = reverse('students:student_edit', kwargs={'pk': self.student_10a.pk})
        post_data = {
            'student_id': self.student_10a.student_id,
            'first_name': 'Alice Updated',
            'last_name': 'Smith',
            'classroom': self.class_10a.pk,
            'roll_number': 1,
            'enrollment_date': '2026-06-01',
            'email': 'alice.updated@school.edu',
            'is_active': True,
        }
        response = self.client.post(edit_url, post_data)
        self.assertEqual(response.status_code, 302)
        self.student_10a.refresh_from_db()
        self.assertEqual(self.student_10a.first_name, 'Alice Updated')
        self.assertEqual(self.student_10a.email, 'alice.updated@school.edu')

    def test_teacher_cannot_edit_student_forbidden(self):
        self.client.force_login(self.teacher_user)
        edit_url = reverse('students:student_edit', kwargs={'pk': self.student_10a.pk})
        response = self.client.get(edit_url)
        self.assertEqual(response.status_code, 403)

    # 7. Student Detail View & Calculations
    def test_admin_can_view_any_student_detail(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('students:student_detail', kwargs={'pk': self.student_10b.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Charlie Brown')
        self.assertContains(response, 'Attendance Performance Summary')

    def test_teacher_can_view_assigned_student_detail(self):
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('students:student_detail', kwargs={'pk': self.student_10a.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alice Smith')

    def test_teacher_cannot_view_unassigned_student_detail_forbidden(self):
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('students:student_detail', kwargs={'pk': self.student_10b.pk}))
        self.assertEqual(response.status_code, 403)

    def test_attendance_summary_calculated_from_database(self):
        # Create attendance records for student_10a
        session1 = AttendanceSession.objects.create(
            classroom=self.class_10a, subject=self.subject,
            date=datetime.date(2026, 10, 1), recorded_by=self.teacher_user
        )
        Attendance.objects.create(
            session=session1, student=self.student_10a, classroom=self.class_10a,
            subject=self.subject, date=datetime.date(2026, 10, 1),
            status=Attendance.Status.PRESENT, recorded_by=self.teacher_user
        )

        session2 = AttendanceSession.objects.create(
            classroom=self.class_10a, subject=self.subject,
            date=datetime.date(2026, 10, 2), recorded_by=self.teacher_user
        )
        Attendance.objects.create(
            session=session2, student=self.student_10a, classroom=self.class_10a,
            subject=self.subject, date=datetime.date(2026, 10, 2),
            status=Attendance.Status.LATE, recorded_by=self.teacher_user
        )

        session3 = AttendanceSession.objects.create(
            classroom=self.class_10a, subject=self.subject,
            date=datetime.date(2026, 10, 3), recorded_by=self.teacher_user
        )
        Attendance.objects.create(
            session=session3, student=self.student_10a, classroom=self.class_10a,
            subject=self.subject, date=datetime.date(2026, 10, 3),
            status=Attendance.Status.ABSENT, recorded_by=self.teacher_user
        )

        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('students:student_detail', kwargs={'pk': self.student_10a.pk}))
        self.assertEqual(response.status_code, 200)

        summary = response.context['attendance_summary']
        self.assertEqual(summary['total_sessions'], 3)
        self.assertEqual(summary['present_count'], 1)
        self.assertEqual(summary['late_count'], 1)
        self.assertEqual(summary['absent_count'], 1)
        self.assertEqual(summary['attended_count'], 2)  # Present + Late = 2
        self.assertEqual(summary['percentage'], 66.7)  # 2/3 = 66.7%

    # 8. Delete & Deactivate Workflow
    def test_admin_cannot_delete_student_with_attendance_history(self):
        # Add attendance record to student_10a
        session = AttendanceSession.objects.create(
            classroom=self.class_10a, subject=self.subject,
            date=datetime.date(2026, 10, 1), recorded_by=self.teacher_user
        )
        Attendance.objects.create(
            session=session, student=self.student_10a, classroom=self.class_10a,
            subject=self.subject, date=datetime.date(2026, 10, 1),
            status=Attendance.Status.PRESENT, recorded_by=self.teacher_user
        )

        self.client.force_login(self.admin_user)
        delete_url = reverse('students:student_delete', kwargs={'pk': self.student_10a.pk})

        # GET should show the warning page stating deletion is blocked
        response = self.client.get(delete_url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['has_attendance_history'])
        self.assertContains(response, 'Permanent Deletion Blocked')

        # POST should refuse deletion and redirect back
        post_response = self.client.post(delete_url)
        self.assertEqual(post_response.status_code, 302)
        # Student must still exist
        self.assertTrue(Student.objects.filter(pk=self.student_10a.pk).exists())

    def test_admin_can_safely_delete_student_without_attendance(self):
        self.client.force_login(self.admin_user)
        # student_10b has no attendance
        delete_url = reverse('students:student_delete', kwargs={'pk': self.student_10b.pk})

        response = self.client.get(delete_url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['has_attendance_history'])
        self.assertContains(response, 'Confirm Permanent Deletion')

        # POST deletes record
        post_response = self.client.post(delete_url)
        self.assertEqual(post_response.status_code, 302)
        self.assertFalse(Student.objects.filter(pk=self.student_10b.pk).exists())

    def test_admin_can_deactivate_and_reactivate_student(self):
        self.client.force_login(self.admin_user)
        toggle_url = reverse('students:student_toggle_status', kwargs={'pk': self.student_10a.pk})

        # Initially active -> Deactivate
        self.assertTrue(self.student_10a.is_active)
        response = self.client.post(toggle_url)
        self.assertEqual(response.status_code, 302)
        self.student_10a.refresh_from_db()
        self.assertFalse(self.student_10a.is_active)

        # Deactivated -> Activate
        response = self.client.post(toggle_url)
        self.assertEqual(response.status_code, 302)
        self.student_10a.refresh_from_db()
        self.assertTrue(self.student_10a.is_active)

    def test_teacher_cannot_delete_or_deactivate_student_forbidden(self):
        self.client.force_login(self.teacher_user)
        delete_url = reverse('students:student_delete', kwargs={'pk': self.student_10a.pk})
        toggle_url = reverse('students:student_toggle_status', kwargs={'pk': self.student_10a.pk})

        self.assertEqual(self.client.get(delete_url).status_code, 403)
        self.assertEqual(self.client.post(delete_url).status_code, 403)
        self.assertEqual(self.client.post(toggle_url).status_code, 403)
