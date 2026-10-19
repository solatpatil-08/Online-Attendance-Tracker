from io import StringIO
import datetime
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.core.management import call_command, CommandError
from django.contrib.auth import get_user_model
from academics.models import AcademicYear, Classroom, Subject, ClassSubjectAssignment
from students.models import Student
from attendance.models import Attendance, AttendanceSession
from accounts.models import User, TeacherProfile
from accounts.signals import assign_role_permissions


class UserModelTests(TestCase):
    def setUp(self):
        assign_role_permissions()
        self.admin_user = User.objects.create_superuser(
            username='admin_test',
            email='admin@example.com',
            password='TestPassword123!',
        )
        self.teacher_user = User.objects.create_user(
            username='teacher_test',
            email='teacher@example.com',
            password='TestPassword123!',
            role=User.Role.TEACHER,
        )

    def test_admin_role_properties(self):
        self.assertTrue(self.admin_user.is_administrator)
        self.assertFalse(self.admin_user.is_teacher_user)
        self.assertEqual(self.admin_user.role, User.Role.ADMIN)

    def test_teacher_role_properties(self):
        self.assertFalse(self.teacher_user.is_administrator)
        self.assertTrue(self.teacher_user.is_teacher_user)
        self.assertEqual(self.teacher_user.role, User.Role.TEACHER)

    def test_teacher_profile_creation(self):
        profile = TeacherProfile.objects.create(
            user=self.teacher_user,
            employee_id='EMP-001',
            department='Mathematics',
            qualification='M.Sc. Mathematics'
        )
        self.assertEqual(str(profile), 'teacher_test (EMP-001)')

    def test_role_group_sync(self):
        self.admin_user.sync_role_group()
        self.teacher_user.sync_role_group()
        self.assertTrue(self.admin_user.groups.filter(name='Administrator').exists())
        self.assertTrue(self.teacher_user.groups.filter(name='Teacher').exists())


class AuthenticationAndSecurityTests(TestCase):
    def setUp(self):
        assign_role_permissions()
        self.client = Client()

        self.admin_user = User.objects.create_superuser(
            username='admin_user',
            email='admin@attendance.local',
            password='AdminPassword123!',
            first_name='Admin',
            last_name='User',
        )

        self.teacher_user = User.objects.create_user(
            username='teacher_user',
            email='teacher@attendance.local',
            password='TeacherPassword123!',
            role=User.Role.TEACHER,
            first_name='Jane',
            last_name='Teacher',
        )
        TeacherProfile.objects.create(
            user=self.teacher_user,
            employee_id='EMP-TEST-01',
            department='Science'
        )

        self.unassigned_teacher = User.objects.create_user(
            username='teacher_unassigned',
            email='unassigned@attendance.local',
            password='TeacherPassword123!',
            role=User.Role.TEACHER,
            first_name='Bob',
            last_name='Unassigned',
        )

        # Setup an academic year and classrooms
        self.academic_year = AcademicYear.objects.create(
            name='2026-2027',
            start_date=datetime.date(2026, 6, 1),
            end_date=datetime.date(2027, 4, 30),
            is_current=True
        )

        self.assigned_class = Classroom.objects.create(
            name='Grade 10',
            section='A',
            academic_year=self.academic_year,
            class_teacher=self.teacher_user
        )

        self.unassigned_class = Classroom.objects.create(
            name='Grade 12',
            section='B',
            academic_year=self.academic_year
        )

        self.subject = Subject.objects.create(
            name='Physics',
            code='PHY-201'
        )

        ClassSubjectAssignment.objects.create(
            classroom=self.assigned_class,
            subject=self.subject,
            teacher=self.teacher_user
        )

        self.student_assigned = Student.objects.create(
            student_id='STU-ASSIGNED',
            first_name='John',
            last_name='Assigned',
            classroom=self.assigned_class,
            roll_number=1
        )

        self.student_unassigned = Student.objects.create(
            student_id='STU-UNASSIGNED',
            first_name='Mary',
            last_name='Unassigned',
            classroom=self.unassigned_class,
            roll_number=1
        )

    # 1. Login Page Tests
    def test_login_page_renders_with_form(self):
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/login.html')
        self.assertContains(response, 'AttendanceHub')
        self.assertContains(response, 'loginPassword')

    def test_successful_login_with_username(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'admin_user',
            'password': 'AdminPassword123!',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['user'].is_authenticated)
        self.assertEqual(response.context['user'].username, 'admin_user')

    def test_successful_login_with_email(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'teacher@attendance.local',
            'password': 'TeacherPassword123!',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['user'].is_authenticated)
        self.assertEqual(response.context['user'].username, 'teacher_user')

    def test_remember_me_session_expiry(self):
        # When remember_me is True, session does NOT expire on browser close and is set to 2 weeks
        client_remember = Client()
        client_remember.post(reverse('accounts:login'), {
            'username': 'admin_user',
            'password': 'AdminPassword123!',
            'remember_me': 'on',
        })
        self.assertFalse(client_remember.session.get_expire_at_browser_close())
        self.assertEqual(client_remember.session.get_expiry_age(), 1209600)

        # When remember_me is False, session DOES expire on browser close
        client_regular = Client()
        client_regular.post(reverse('accounts:login'), {
            'username': 'teacher_user',
            'password': 'TeacherPassword123!',
        })
        self.assertTrue(client_regular.session.get_expire_at_browser_close())

    def test_invalid_login_credentials(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'admin_user',
            'password': 'WrongPassword!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse('_auth_user_id' in self.client.session)
        # Verify generic security message without exposing username
        self.assertContains(response, 'Invalid credentials')

    def test_nonexistent_user_login(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'nonexistent_account@school.edu',
            'password': 'SomePassword123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse('_auth_user_id' in self.client.session)
        self.assertContains(response, 'Invalid credentials')

    # 2. Logout Tests
    def test_secure_post_logout(self):
        self.client.login(username='admin_user', password='AdminPassword123!')
        self.assertTrue('_auth_user_id' in self.client.session)

        response = self.client.post(reverse('accounts:logout'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse('_auth_user_id' in self.client.session)
        self.assertTemplateUsed(response, 'accounts/login.html')

    # 3. Unauthenticated Access Protection
    def test_unauthenticated_protected_pages_redirect_to_login(self):
        protected_urls = [
            reverse('dashboard:index'),
            reverse('accounts:profile'),
            reverse('accounts:teacher_list'),
            reverse('academics:classroom_list'),
            reverse('students:student_list'),
        ]
        for url in protected_urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, f"Failed for {url}")
            self.assertTrue(response.url.startswith(reverse('accounts:login')))

    # 4. Administrator Permissions & Authorization
    def test_administrator_has_full_management_access(self):
        self.client.login(username='admin_user', password='AdminPassword123!')
        
        # Admin can view teacher management
        res_teachers = self.client.get(reverse('accounts:teacher_list'))
        self.assertEqual(res_teachers.status_code, 200)

        # Admin can view classrooms and students
        res_classes = self.client.get(reverse('academics:classroom_list'))
        self.assertEqual(res_classes.status_code, 200)

        res_students = self.client.get(reverse('students:student_list'))
        self.assertEqual(res_students.status_code, 200)

    # 5. Teacher Access to Administrator-Only Pages Forbidden (HTTP 403)
    def test_teacher_forbidden_from_admin_management_pages(self):
        self.client.login(username='teacher_user', password='TeacherPassword123!')

        admin_only_urls = [
            reverse('accounts:teacher_list'),
            reverse('accounts:teacher_create'),
            reverse('academics:classroom_create'),
            reverse('students:student_create'),
        ]
        for url in admin_only_urls:
            response = self.client.get(url)
            self.assertEqual(
                response.status_code, 403,
                f"Teacher was not denied (expected 403) for admin-only url {url}"
            )

    # 6. Teacher Classroom Access Control
    def test_teacher_can_access_assigned_classroom(self):
        self.client.login(username='teacher_user', password='TeacherPassword123!')
        response = self.client.get(reverse('academics:classroom_detail', kwargs={'pk': self.assigned_class.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Grade 10 - A')

    def test_teacher_forbidden_from_unassigned_classroom(self):
        self.client.login(username='teacher_user', password='TeacherPassword123!')
        response = self.client.get(reverse('academics:classroom_detail', kwargs={'pk': self.unassigned_class.pk}))
        # Strict server-side permission check: must return HTTP 403 Forbidden
        self.assertEqual(response.status_code, 403)

    # 7. Teacher Student Record Access Control
    def test_teacher_can_view_assigned_student_profile(self):
        self.client.login(username='teacher_user', password='TeacherPassword123!')
        response = self.client.get(reverse('students:student_detail', kwargs={'pk': self.student_assigned.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'John Assigned')

    def test_teacher_forbidden_from_unassigned_student_profile(self):
        self.client.login(username='teacher_user', password='TeacherPassword123!')
        response = self.client.get(reverse('students:student_detail', kwargs={'pk': self.student_unassigned.pk}))
        self.assertEqual(response.status_code, 403)

    # 8. Unauthorized Modification Attempts
    def test_teacher_cannot_toggle_teacher_status(self):
        self.client.login(username='teacher_user', password='TeacherPassword123!')
        response = self.client.post(reverse('accounts:teacher_toggle_status', kwargs={'pk': self.unassigned_teacher.pk}))
        self.assertEqual(response.status_code, 403)
        self.unassigned_teacher.refresh_from_db()
        self.assertTrue(self.unassigned_teacher.is_active)

    def test_teacher_cannot_create_new_classroom(self):
        self.client.login(username='teacher_user', password='TeacherPassword123!')
        response = self.client.post(reverse('academics:classroom_create'), {
            'name': 'Grade 11',
            'section': 'C',
            'academic_year': self.academic_year.pk,
            'is_active': True,
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Classroom.objects.filter(name='Grade 11', section='C').exists())

    # 9. Comprehensive Teacher Management Tests
    def test_teacher_creation_hashes_password_and_assigns_role(self):
        """Admin creates a teacher; password must be securely hashed and role assigned."""
        self.client.login(username='admin_user', password='AdminPassword123!')
        response = self.client.post(reverse('accounts:teacher_create'), {
            'username': 'new_teacher_dr',
            'email': 'dr_new@school.edu',
            'first_name': 'Doctor',
            'last_name': 'Who',
            'employee_id': 'EMP-DOC-01',
            'department': 'Physics',
            'qualification': 'Ph.D. Quantum Physics',
            'password': 'SecurePassword123!',
            'confirm_password': 'SecurePassword123!',
        })
        new_teacher = User.objects.get(username='new_teacher_dr')
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('accounts:teacher_detail', kwargs={'pk': new_teacher.pk}))
        self.assertEqual(new_teacher.role, User.Role.TEACHER)
        self.assertTrue(new_teacher.check_password('SecurePassword123!'))
        self.assertNotEqual(new_teacher.password, 'SecurePassword123!')  # Hashed
        self.assertEqual(new_teacher.teacher_profile.employee_id, 'EMP-DOC-01')
        self.assertEqual(new_teacher.teacher_profile.department, 'Physics')

    def test_teacher_creation_prevents_duplicate_employee_id_or_username(self):
        """Teacher creation rejects duplicate employee IDs or usernames."""
        self.client.login(username='admin_user', password='AdminPassword123!')
        response = self.client.post(reverse('accounts:teacher_create'), {
            'username': 'teacher_duplicate',
            'email': 'dup@school.edu',
            'first_name': 'Dup',
            'last_name': 'Licat',
            'employee_id': 'EMP-TEST-01',  # Already taken by self.teacher_user
            'password': 'Password123!',
            'confirm_password': 'Password123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'employee_id', 'A teacher with this employee ID already exists.')

    def test_teacher_admin_edit_profile(self):
        """Admin can edit teacher profile details, department, and active status."""
        self.client.login(username='admin_user', password='AdminPassword123!')
        response = self.client.post(reverse('accounts:teacher_edit', kwargs={'pk': self.teacher_user.pk}), {
            'first_name': 'Janet',
            'last_name': 'Teacher-Smith',
            'email': 'janet.updated@attendance.local',
            'phone_number': '+1 555-9876',
            'employee_id': 'EMP-TEST-01-UPD',
            'department': 'Advanced Science',
            'qualification': 'M.Sc., B.Ed.',
            'is_active': True,
        })
        self.assertEqual(response.status_code, 302)
        self.teacher_user.refresh_from_db()
        self.assertEqual(self.teacher_user.first_name, 'Janet')
        self.assertEqual(self.teacher_user.last_name, 'Teacher-Smith')
        self.assertEqual(self.teacher_user.email, 'janet.updated@attendance.local')
        self.assertEqual(self.teacher_user.teacher_profile.employee_id, 'EMP-TEST-01-UPD')
        self.assertEqual(self.teacher_user.teacher_profile.department, 'Advanced Science')

    def test_teacher_admin_edit_can_reset_password(self):
        """Admin can optionally reset a teacher's password."""
        self.client.login(username='admin_user', password='AdminPassword123!')
        response = self.client.post(reverse('accounts:teacher_edit', kwargs={'pk': self.teacher_user.pk}), {
            'first_name': self.teacher_user.first_name,
            'last_name': self.teacher_user.last_name,
            'email': self.teacher_user.email,
            'employee_id': self.teacher_user.teacher_profile.employee_id,
            'is_active': True,
            'new_password': 'BrandNewPassword999!',
            'confirm_new_password': 'BrandNewPassword999!',
        })
        self.assertEqual(response.status_code, 302)
        self.teacher_user.refresh_from_db()
        self.assertTrue(self.teacher_user.check_password('BrandNewPassword999!'))

    def test_teacher_search_and_filter(self):
        """Admin can search and filter teachers in list view."""
        self.client.login(username='admin_user', password='AdminPassword123!')
        # Search by employee id
        resp = self.client.get(reverse('accounts:teacher_list') + '?q=EMP-TEST-01')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'EMP-TEST-01')
        self.assertNotContains(resp, 'Bob Unassigned')

        # Filter by department
        resp = self.client.get(reverse('accounts:teacher_list') + '?department=Science')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Jane')

    def test_teacher_toggle_status_cannot_deactivate_self(self):
        """Admin cannot deactivate their own administrative account."""
        self.client.login(username='admin_user', password='AdminPassword123!')
        response = self.client.post(reverse('accounts:teacher_toggle_status', kwargs={'pk': self.admin_user.pk}))
        # Admin is not role=TEACHER, returns 404
        self.assertEqual(response.status_code, 404)

    def test_admin_assign_and_remove_class_subject_to_teacher(self):
        """Admin can assign and remove a class-subject from a teacher."""
        self.client.login(username='admin_user', password='AdminPassword123!')
        subject = Subject.objects.create(name='Biochemistry', code='BIO-301')

        # Assign BIO-301 in assigned_class to teacher_user
        response = self.client.post(reverse('accounts:teacher_assign', kwargs={'pk': self.teacher_user.pk}), {
            'classroom': self.assigned_class.pk,
            'subject': subject.pk,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ClassSubjectAssignment.objects.filter(
            classroom=self.assigned_class,
            subject=subject,
            teacher=self.teacher_user
        ).exists())

        # Duplicate assignment should be prevented
        dup_resp = self.client.post(reverse('accounts:teacher_assign', kwargs={'pk': self.teacher_user.pk}), {
            'classroom': self.assigned_class.pk,
            'subject': subject.pk,
        })
        self.assertEqual(dup_resp.status_code, 302)
        self.assertEqual(ClassSubjectAssignment.objects.filter(
            classroom=self.assigned_class,
            subject=subject
        ).count(), 1)

        # Remove assignment
        assignment = ClassSubjectAssignment.objects.get(classroom=self.assigned_class, subject=subject)
        del_resp = self.client.post(reverse('accounts:teacher_remove_assignment', kwargs={
            'pk': self.teacher_user.pk,
            'assignment_id': assignment.pk
        }))
        self.assertEqual(del_resp.status_code, 302)
        self.assertFalse(ClassSubjectAssignment.objects.filter(pk=assignment.pk).exists())

    def test_assign_to_inactive_teacher_fails(self):
        """Assigning class/subject to an inactive teacher fails."""
        self.client.login(username='admin_user', password='AdminPassword123!')
        self.teacher_user.is_active = False
        self.teacher_user.save()
        subject = Subject.objects.create(name='Geology', code='GEO-101')

        response = self.client.post(reverse('accounts:teacher_assign', kwargs={'pk': self.teacher_user.pk}), {
            'classroom': self.assigned_class.pk,
            'subject': subject.pk,
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ClassSubjectAssignment.objects.filter(classroom=self.assigned_class, subject=subject).exists())

    def test_unauthorized_teacher_forbidden_from_teacher_management(self):
        """Non-admin user cannot access teacher editing, detail, or assignments."""
        self.client.login(username='teacher_user', password='TeacherPassword123!')
        forbidden_urls = [
            reverse('accounts:teacher_edit', kwargs={'pk': self.teacher_user.pk}),
            reverse('accounts:teacher_detail', kwargs={'pk': self.teacher_user.pk}),
            reverse('accounts:teacher_assign', kwargs={'pk': self.teacher_user.pk}),
        ]
        for url in forbidden_urls:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 403)


@override_settings(DEBUG=True)
class SeedDemoDataCommandTests(TestCase):
    def setUp(self):
        assign_role_permissions()

    def test_seed_demo_data_command_execution(self):
        """seed_demo_data successfully creates accounts, classes, subjects, students, and attendance."""
        out = StringIO()
        call_command('seed_demo_data', days=3, stdout=out)

        # 3 Admins
        self.assertEqual(User.objects.filter(username__startswith='admin_').count(), 3)
        admin_rajesh = User.objects.get(username='admin_rajesh')
        self.assertTrue(admin_rajesh.is_administrator)
        self.assertTrue(admin_rajesh.is_superuser)
        self.assertTrue(admin_rajesh.check_password('DemoPass@123'))

        # 10 Teachers
        self.assertEqual(User.objects.filter(username__startswith='teacher_').count(), 10)
        self.assertEqual(TeacherProfile.objects.filter(employee_id__startswith='EMP-T').count(), 10)
        teacher_sneha = User.objects.get(username='teacher_sneha')
        self.assertTrue(teacher_sneha.is_teacher_user)
        self.assertEqual(teacher_sneha.teacher_profile.department, 'Mathematics')
        self.assertTrue(teacher_sneha.check_password('DemoPass@123'))

        # 8 Classrooms
        self.assertEqual(Classroom.objects.filter(academic_year__name='2026-2027').count(), 8)

        # 10 Subjects
        self.assertEqual(Subject.objects.filter(code__in=[
            'MATH-01', 'PHY-01', 'CHEM-01', 'BIO-01', 'ENG-01',
            'HIN-01', 'SOC-01', 'CS-01', 'EVS-01', 'ECON-01'
        ]).count(), 10)

        # 200 Students
        self.assertEqual(Student.objects.filter(student_id__startswith='IND-2026-').count(), 200)
        first_student = Student.objects.get(student_id='IND-2026-0001')
        self.assertEqual(first_student.roll_number, 1)
        self.assertEqual(first_student.classroom.name, 'Class 8')
        self.assertEqual(first_student.classroom.section, 'A')

        # Attendance records
        self.assertTrue(AttendanceSession.objects.filter(classroom__name='Class 8').exists())
        self.assertTrue(Attendance.objects.filter(student__student_id__startswith='IND-2026-').exists())

    def test_seed_demo_data_idempotency(self):
        """Calling seed_demo_data multiple times is safe and maintains identical record counts."""
        out = StringIO()
        call_command('seed_demo_data', days=2, stdout=out)
        first_student_count = Student.objects.filter(student_id__startswith='IND-2026-').count()
        first_session_count = AttendanceSession.objects.count()
        first_att_count = Attendance.objects.count()

        # Run second time
        call_command('seed_demo_data', days=2, stdout=out)
        self.assertEqual(Student.objects.filter(student_id__startswith='IND-2026-').count(), first_student_count)
        self.assertEqual(AttendanceSession.objects.count(), first_session_count)
        self.assertEqual(Attendance.objects.count(), first_att_count)

    def test_seed_demo_data_reset(self):
        """--reset cleanly purges all demo-tagged data while preserving non-demo records."""
        keep_user = User.objects.create_user(username='custom_user', email='custom@domain.local', password='pwd')
        out = StringIO()
        call_command('seed_demo_data', days=2, stdout=out)
        self.assertTrue(Student.objects.filter(student_id__startswith='IND-2026-').exists())

        # Reset demo data
        call_command('seed_demo_data', reset=True, stdout=out)
        self.assertFalse(Student.objects.filter(student_id__startswith='IND-2026-').exists())
        self.assertFalse(User.objects.filter(username__startswith='teacher_').exists())
        self.assertFalse(User.objects.filter(username__startswith='admin_').exists())
        self.assertTrue(User.objects.filter(pk=keep_user.pk).exists())

    @override_settings(DEBUG=False)
    def test_seed_demo_data_production_guard(self):
        """When DEBUG is False, seed_demo_data requires explicit --confirm-production."""
        out = StringIO()
        with self.assertRaises(CommandError):
            call_command('seed_demo_data', days=1, stdout=out)

        # Providing confirm_production succeeds
        call_command('seed_demo_data', days=1, confirm_production=True, stdout=out)
        self.assertTrue(User.objects.filter(username='admin_rajesh').exists())


