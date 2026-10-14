import json
import datetime
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from accounts.signals import assign_role_permissions
from academics.models import AcademicYear, Classroom, Subject
from students.models import Student
from attendance.models import Attendance, AttendanceSession


class DashboardViewTests(TestCase):
    def setUp(self):
        assign_role_permissions()
        self.client = Client()

        self.admin = User.objects.create_superuser(
            username='admin_boss',
            email='admin@school.org',
            password='Password123!',
            role=User.Role.ADMIN,
        )

        self.teacher = User.objects.create_user(
            username='teacher_jane',
            email='jane@school.org',
            password='Password123!',
            role=User.Role.TEACHER,
        )

    def test_anonymous_user_redirected_to_login(self):
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response.url)

    def test_admin_dashboard_empty_database(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/admin_dashboard.html')

        stats = response.context['stats']
        self.assertEqual(stats['total_students'], 0)
        self.assertEqual(stats['total_teachers'], 1)  # self.teacher exists
        self.assertEqual(stats['total_classes'], 0)
        self.assertEqual(stats['total_subjects'], 0)
        self.assertEqual(stats['records_count'], 0)
        self.assertEqual(stats['present_count'], 0)
        self.assertEqual(stats['late_count'], 0)
        self.assertEqual(stats['absent_count'], 0)
        self.assertEqual(stats['excused_count'], 0)
        self.assertEqual(stats['attendance_percentage'], 0.0)

        # Verify Chart.js JSON context variables parse without error
        trend_labels = json.loads(response.context['chart_trend_labels_json'])
        self.assertEqual(len(trend_labels), 7)
        status_data = json.loads(response.context['chart_status_data_json'])
        self.assertEqual(status_data, [0, 0, 0, 0])

    def test_admin_dashboard_populated_database_and_attendance_rate(self):
        today = timezone.localdate()
        year = AcademicYear.objects.create(
            name='2026-2027',
            start_date=datetime.date(2026, 6, 1),
            end_date=datetime.date(2027, 5, 31),
            is_current=True,
        )
        class_a = Classroom.objects.create(name='Grade 10', section='A', academic_year=year)
        class_b = Classroom.objects.create(name='Grade 10', section='B', academic_year=year)
        subject_math = Subject.objects.create(name='Calculus', code='MTH-101')
        subject_eng = Subject.objects.create(name='English', code='ENG-101')

        # 4 enrolled students: 2 in Class A, 2 in Class B
        s1 = Student.objects.create(student_id='STU-001', first_name='Alice', last_name='Smith', classroom=class_a)
        s2 = Student.objects.create(student_id='STU-002', first_name='Bob', last_name='Jones', classroom=class_a)
        s3 = Student.objects.create(student_id='STU-003', first_name='Charlie', last_name='Brown', classroom=class_b)
        s4 = Student.objects.create(student_id='STU-004', first_name='Diana', last_name='Prince', classroom=class_b)

        # Attendance Session ONLY for Class A today:
        # s1 is PRESENT, s2 is LATE. Total recorded = 2.
        # Students in Class B (s3, s4) are NOT recorded today and MUST NOT be assumed absent.
        session = AttendanceSession.objects.create(
            classroom=class_a,
            subject=subject_math,
            recorded_by=self.teacher,
            date=today,
        )
        Attendance.objects.create(
            session=session,
            student=s1,
            classroom=class_a,
            subject=subject_math,
            date=today,
            status=Attendance.Status.PRESENT,
            recorded_by=self.teacher,
        )
        Attendance.objects.create(
            session=session,
            student=s2,
            classroom=class_a,
            subject=subject_math,
            date=today,
            status=Attendance.Status.LATE,
            recorded_by=self.teacher,
        )

        self.client.force_login(self.admin)
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 200)

        stats = response.context['stats']
        self.assertEqual(stats['total_students'], 4)
        self.assertEqual(stats['total_teachers'], 1)
        self.assertEqual(stats['total_classes'], 2)
        self.assertEqual(stats['total_subjects'], 2)

        # Rate: (1 Present + 1 Late) / 2 recorded = 100%
        self.assertEqual(stats['records_count'], 2)
        self.assertEqual(stats['present_count'], 1)
        self.assertEqual(stats['late_count'], 1)
        self.assertEqual(stats['absent_count'], 0)
        self.assertEqual(stats['attendance_percentage'], 100.0)
        self.assertEqual(stats['unrecorded_count'], 2)

        # Check chart datasets
        class_labels = json.loads(response.context['chart_class_labels_json'])
        self.assertIn('Grade 10 - A', class_labels)
        self.assertIn('Grade 10 - B', class_labels)

        # Assert visual page elements
        content = response.content.decode()
        self.assertIn('Institutional Dashboard', content)
        self.assertIn('Attendance Records', content)
        self.assertIn('Grade 10 - A', content)

    def test_admin_dashboard_date_filtering(self):
        today = timezone.localdate()
        past_date = today - datetime.timedelta(days=2)
        past_date_str = past_date.isoformat()

        year = AcademicYear.objects.create(
            name='2026-2027',
            start_date=datetime.date(2026, 6, 1),
            end_date=datetime.date(2027, 5, 31),
            is_current=True,
        )
        classroom = Classroom.objects.create(name='Grade 11', section='A', academic_year=year)
        subject = Subject.objects.create(name='Physics', code='PHY-101')
        student1 = Student.objects.create(student_id='STU-101', first_name='Tom', last_name='Sawyer', classroom=classroom)
        student2 = Student.objects.create(student_id='STU-102', first_name='Huck', last_name='Finn', classroom=classroom)

        past_session = AttendanceSession.objects.create(
            classroom=classroom,
            subject=subject,
            recorded_by=self.teacher,
            date=past_date,
        )
        Attendance.objects.create(
            session=past_session,
            student=student1,
            classroom=classroom,
            subject=subject,
            date=past_date,
            status=Attendance.Status.PRESENT,
            recorded_by=self.teacher,
        )
        Attendance.objects.create(
            session=past_session,
            student=student2,
            classroom=classroom,
            subject=subject,
            date=past_date,
            status=Attendance.Status.ABSENT,
            recorded_by=self.teacher,
        )

        self.client.force_login(self.admin)

        # Query past date
        response = self.client.get(f"{reverse('dashboard:index')}?date={past_date_str}")
        self.assertEqual(response.status_code, 200)

        stats = response.context['stats']
        self.assertEqual(stats['records_count'], 2)
        self.assertEqual(stats['present_count'], 1)
        self.assertEqual(stats['absent_count'], 1)
        # Attendance % = (1 Present / 2 recorded) = 50.0%
        self.assertEqual(stats['attendance_percentage'], 50.0)

    def test_invalid_date_query_param_falls_back_to_today(self):
        self.client.force_login(self.admin)
        response = self.client.get(f"{reverse('dashboard:index')}?date=not-a-valid-date")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_date'], timezone.localdate())

    def test_teacher_user_renders_teacher_dashboard(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/teacher_dashboard.html')

    def test_navigation_links_role_authorization(self):
        # 1. Admin login sees Faculty & Teachers
        self.client.force_login(self.admin)
        response_admin = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response_admin.status_code, 200)
        content_admin = response_admin.content.decode()
        self.assertIn('Faculty & Teachers', content_admin)
        self.assertIn(reverse('accounts:teacher_list'), content_admin)
        self.assertIn('Administrator Profile', content_admin)

        # 2. Teacher login does NOT see Faculty & Teachers management link
        self.client.force_login(self.teacher)
        response_teacher = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response_teacher.status_code, 200)
        content_teacher = response_teacher.content.decode()
        self.assertNotIn('Faculty & Teachers', content_teacher)
        self.assertNotIn(reverse('accounts:teacher_list'), content_teacher)

    def test_admin_dashboard_distinct_students_and_unrecorded_accuracy(self):
        today = timezone.localdate()
        year = AcademicYear.objects.create(
            name='2026-2027',
            start_date=datetime.date(2026, 6, 1),
            end_date=datetime.date(2027, 5, 31),
            is_current=True,
        )
        classroom = Classroom.objects.create(name='Grade 12', section='A', academic_year=year)
        sub1 = Subject.objects.create(name='History', code='HIS-101')
        sub2 = Subject.objects.create(name='Geography', code='GEO-101')

        # 3 students enrolled
        stu1 = Student.objects.create(student_id='STU-201', first_name='Elena', last_name='Gilbert', classroom=classroom)
        stu2 = Student.objects.create(student_id='STU-202', first_name='Stefan', last_name='Salvatore', classroom=classroom)
        stu3 = Student.objects.create(student_id='STU-203', first_name='Damon', last_name='Salvatore', classroom=classroom)

        # Session 1: History (stu1 Present, stu2 Absent)
        sess1 = AttendanceSession.objects.create(
            classroom=classroom, subject=sub1, recorded_by=self.teacher, date=today
        )
        Attendance.objects.create(
            session=sess1, student=stu1, classroom=classroom, subject=sub1,
            date=today, status=Attendance.Status.PRESENT, recorded_by=self.teacher
        )
        Attendance.objects.create(
            session=sess1, student=stu2, classroom=classroom, subject=sub1,
            date=today, status=Attendance.Status.ABSENT, recorded_by=self.teacher
        )

        # Session 2: Geography (stu1 Present, stu3 Late)
        sess2 = AttendanceSession.objects.create(
            classroom=classroom, subject=sub2, recorded_by=self.teacher, date=today
        )
        Attendance.objects.create(
            session=sess2, student=stu1, classroom=classroom, subject=sub2,
            date=today, status=Attendance.Status.PRESENT, recorded_by=self.teacher
        )
        Attendance.objects.create(
            session=sess2, student=stu3, classroom=classroom, subject=sub2,
            date=today, status=Attendance.Status.LATE, recorded_by=self.teacher
        )

        self.client.force_login(self.admin)
        response = self.client.get(reverse('dashboard:index'))
        stats = response.context['stats']

        # Total records = 4 across both sessions
        self.assertEqual(stats['records_count'], 4)
        # All 3 distinct students were recorded at least once
        self.assertEqual(stats['distinct_students_count'], 3)
        self.assertEqual(stats['present_count'], 2)  # 2 present records
        self.assertEqual(stats['late_count'], 1)     # 1 late record
        self.assertEqual(stats['absent_count'], 1)   # 1 absent record
        # Effective attended: 2 present + 1 late = 3 out of 4 records => 75.0%
        self.assertEqual(stats['attendance_percentage'], 75.0)

        # Check Chart.js json_script tags are in rendered HTML
        content = response.content.decode()
        self.assertIn('id="trend-labels-data"', content)
        self.assertIn('id="trend-percentages-data"', content)
        self.assertIn('id="status-data"', content)
        self.assertIn('id="class-percentages-data"', content)
        self.assertIn('id="trend-totals-data"', content)
