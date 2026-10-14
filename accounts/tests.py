import datetime
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from academics.models import AcademicYear, Classroom, Subject, ClassSubjectAssignment
from students.models import Student
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
