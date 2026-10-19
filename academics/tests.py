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

    def test_inactive_teacher_cannot_be_class_teacher(self):
        """Inactive teacher cannot be assigned as class_teacher."""
        inactive_teacher = User.objects.create_user(
            username='inactive_prof',
            email='inactive@example.com',
            password='Password123!',
            role=User.Role.TEACHER,
            is_active=False
        )
        classroom = Classroom(
            name='Grade 12',
            section='A',
            academic_year=self.year_2026,
            class_teacher=inactive_teacher
        )
        with self.assertRaises(ValidationError):
            classroom.clean()

    def test_inactive_teacher_cannot_be_subject_instructor(self):
        """Inactive teacher cannot be assigned to ClassSubjectAssignment."""
        inactive_teacher = User.objects.create_user(
            username='inactive_prof2',
            email='inactive2@example.com',
            password='Password123!',
            role=User.Role.TEACHER,
            is_active=False
        )
        classroom = Classroom.objects.create(
            name='Grade 8',
            section='A',
            academic_year=self.year_2026,
            class_teacher=self.teacher_user
        )
        subject = Subject.objects.create(name='Biology', code='BIO-101')
        assignment = ClassSubjectAssignment(
            classroom=classroom,
            subject=subject,
            teacher=inactive_teacher
        )
        with self.assertRaises(ValidationError):
            assignment.clean()

    def test_inactive_classroom_or_subject_cannot_be_assigned(self):
        """Inactive classroom or subject cannot be assigned in ClassSubjectAssignment."""
        inactive_classroom = Classroom.objects.create(
            name='Grade 7',
            section='A',
            academic_year=self.year_2026,
            is_active=False
        )
        active_subject = Subject.objects.create(name='History', code='HIST-101')
        inactive_subject = Subject.objects.create(name='Music', code='MUS-101', is_active=False)
        active_classroom = Classroom.objects.create(
            name='Grade 7',
            section='B',
            academic_year=self.year_2026,
            is_active=True
        )

        with self.assertRaises(ValidationError):
            assign1 = ClassSubjectAssignment(classroom=inactive_classroom, subject=active_subject, teacher=self.teacher_user)
            assign1.clean()

        with self.assertRaises(ValidationError):
            assign2 = ClassSubjectAssignment(classroom=active_classroom, subject=inactive_subject, teacher=self.teacher_user)
            assign2.clean()


from django.test import Client
from django.urls import reverse
from accounts.signals import assign_role_permissions
from .forms import ClassroomForm, SubjectForm, ClassSubjectAssignmentForm


class AcademicsManagementViewTests(TestCase):
    def setUp(self):
        assign_role_permissions()
        self.client = Client()

        self.admin = User.objects.create_superuser(
            username='admin_super',
            email='admin@school.local',
            password='Password123!',
            role=User.Role.ADMIN
        )
        self.teacher = User.objects.create_user(
            username='teacher_jane',
            email='jane@school.local',
            password='Password123!',
            role=User.Role.TEACHER,
            is_active=True
        )
        self.year = AcademicYear.objects.create(
            name='2026-2027',
            start_date=datetime.date(2026, 6, 1),
            end_date=datetime.date(2027, 4, 30),
            is_current=True
        )
        self.classroom = Classroom.objects.create(
            name='Grade 10',
            section='A',
            academic_year=self.year,
            class_teacher=self.teacher
        )
        self.subject = Subject.objects.create(
            name='Algebra',
            code='ALG-101'
        )

    # 1. Classroom Management
    def test_admin_can_create_classroom(self):
        self.client.login(username='admin_super', password='Password123!')
        response = self.client.post(reverse('academics:classroom_create'), {
            'name': 'Grade 10',
            'section': 'B',
            'academic_year': self.year.pk,
            'class_teacher': self.teacher.pk,
            'is_active': True,
        })
        new_class = Classroom.objects.get(name='Grade 10', section='B')
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('academics:classroom_detail', kwargs={'pk': new_class.pk}))
        self.assertEqual(new_class.class_teacher, self.teacher)

    def test_admin_create_duplicate_classroom_rejected(self):
        """Duplicate class and section in same academic year is prevented in form."""
        self.client.login(username='admin_super', password='Password123!')
        response = self.client.post(reverse('academics:classroom_create'), {
            'name': 'Grade 10',
            'section': 'A',  # Duplicate of self.classroom
            'academic_year': self.year.pk,
            'class_teacher': self.teacher.pk,
            'is_active': True,
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'section', f"A classroom 'Grade 10 - A' already exists for the academic year '{self.year.name}'. Please choose a distinct section or grade.")

    def test_admin_can_edit_classroom(self):
        self.client.login(username='admin_super', password='Password123!')
        response = self.client.post(reverse('academics:classroom_edit', kwargs={'pk': self.classroom.pk}), {
            'name': 'Grade 10',
            'section': 'A-Prime',
            'academic_year': self.year.pk,
            'class_teacher': self.teacher.pk,
            'is_active': True,
        })
        self.assertEqual(response.status_code, 302)
        self.classroom.refresh_from_db()
        self.assertEqual(self.classroom.section, 'A-PRIME')

    def test_admin_can_deactivate_and_activate_classroom(self):
        self.client.login(username='admin_super', password='Password123!')
        response = self.client.post(reverse('academics:classroom_toggle_status', kwargs={'pk': self.classroom.pk}))
        self.assertEqual(response.status_code, 302)
        self.classroom.refresh_from_db()
        self.assertFalse(self.classroom.is_active)

        # Reactivate
        self.client.post(reverse('academics:classroom_toggle_status', kwargs={'pk': self.classroom.pk}))
        self.classroom.refresh_from_db()
        self.assertTrue(self.classroom.is_active)

    def test_admin_assign_and_remove_subject_from_classroom_detail(self):
        self.client.login(username='admin_super', password='Password123!')
        # Assign
        resp = self.client.post(reverse('academics:classroom_assign_subject', kwargs={'pk': self.classroom.pk}), {
            'subject': self.subject.pk,
            'teacher': self.teacher.pk,
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(ClassSubjectAssignment.objects.filter(classroom=self.classroom, subject=self.subject).exists())

        # Duplicate assign rejected
        dup_resp = self.client.post(reverse('academics:classroom_assign_subject', kwargs={'pk': self.classroom.pk}), {
            'subject': self.subject.pk,
            'teacher': self.teacher.pk,
        })
        self.assertEqual(dup_resp.status_code, 302)
        self.assertEqual(ClassSubjectAssignment.objects.filter(classroom=self.classroom, subject=self.subject).count(), 1)

        # Remove
        assign = ClassSubjectAssignment.objects.get(classroom=self.classroom, subject=self.subject)
        rem_resp = self.client.post(reverse('academics:classroom_remove_subject', kwargs={
            'pk': self.classroom.pk,
            'assignment_id': assign.pk
        }))
        self.assertEqual(rem_resp.status_code, 302)
        self.assertFalse(ClassSubjectAssignment.objects.filter(pk=assign.pk).exists())

    # 2. Subject Management
    def test_admin_can_create_subject(self):
        self.client.login(username='admin_super', password='Password123!')
        response = self.client.post(reverse('academics:subject_create'), {
            'name': 'World History',
            'code': 'HIST-201',
            'description': 'Modern and Ancient civilizations',
            'is_active': True,
        })
        new_subj = Subject.objects.get(code='HIST-201')
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('academics:subject_detail', kwargs={'pk': new_subj.pk}))

    def test_admin_create_duplicate_subject_code_rejected(self):
        """Duplicate subject code is prevented in form."""
        self.client.login(username='admin_super', password='Password123!')
        response = self.client.post(reverse('academics:subject_create'), {
            'name': 'Linear Algebra',
            'code': 'alg-101',  # Same as ALG-101
            'is_active': True,
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'code', "A subject with code 'ALG-101' already exists. Please provide a unique subject code.")

    def test_admin_can_edit_subject(self):
        self.client.login(username='admin_super', password='Password123!')
        response = self.client.post(reverse('academics:subject_edit', kwargs={'pk': self.subject.pk}), {
            'name': 'Algebra & Geometry',
            'code': 'ALG-101',
            'description': 'Updated syllabus',
            'is_active': True,
        })
        self.assertEqual(response.status_code, 302)
        self.subject.refresh_from_db()
        self.assertEqual(self.subject.name, 'Algebra & Geometry')

    def test_admin_can_deactivate_subject(self):
        self.client.login(username='admin_super', password='Password123!')
        response = self.client.post(reverse('academics:subject_toggle_status', kwargs={'pk': self.subject.pk}))
        self.assertEqual(response.status_code, 302)
        self.subject.refresh_from_db()
        self.assertFalse(self.subject.is_active)

    # 3. Assignment Management Views
    def test_assignment_crud_views(self):
        self.client.login(username='admin_super', password='Password123!')
        # Create assignment
        response = self.client.post(reverse('academics:assignment_create'), {
            'classroom': self.classroom.pk,
            'subject': self.subject.pk,
            'teacher': self.teacher.pk,
            'is_active': True,
        })
        self.assertEqual(response.status_code, 302)
        assign = ClassSubjectAssignment.objects.get(classroom=self.classroom, subject=self.subject)
        self.assertEqual(assign.teacher, self.teacher)

        # Update assignment
        t2 = User.objects.create_user(username='teacher_bob', email='bob@school.local', password='Password123!', role=User.Role.TEACHER)
        up_resp = self.client.post(reverse('academics:assignment_edit', kwargs={'pk': assign.pk}), {
            'classroom': self.classroom.pk,
            'subject': self.subject.pk,
            'teacher': t2.pk,
            'is_active': True,
        })
        self.assertEqual(up_resp.status_code, 302)
        assign.refresh_from_db()
        self.assertEqual(assign.teacher, t2)

        # Delete assignment
        del_resp = self.client.post(reverse('academics:assignment_delete', kwargs={'pk': assign.pk}))
        self.assertEqual(del_resp.status_code, 302)
        self.assertFalse(ClassSubjectAssignment.objects.filter(pk=assign.pk).exists())

    # 4. Unauthorized operations
    def test_teacher_unauthorized_operations(self):
        self.client.login(username='teacher_jane', password='Password123!')
        # Teacher cannot edit classroom
        r1 = self.client.get(reverse('academics:classroom_edit', kwargs={'pk': self.classroom.pk}))
        self.assertEqual(r1.status_code, 403)

        # Teacher cannot toggle classroom status
        r2 = self.client.post(reverse('academics:classroom_toggle_status', kwargs={'pk': self.classroom.pk}))
        self.assertEqual(r2.status_code, 403)

        # Teacher cannot create subject
        r3 = self.client.get(reverse('academics:subject_create'))
        self.assertEqual(r3.status_code, 403)

        # Teacher cannot edit subject
        r4 = self.client.get(reverse('academics:subject_edit', kwargs={'pk': self.subject.pk}))
        self.assertEqual(r4.status_code, 403)

        # Teacher cannot access assignment management
        r5 = self.client.get(reverse('academics:assignment_list'))
        self.assertEqual(r5.status_code, 403)

