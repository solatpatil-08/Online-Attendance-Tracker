import datetime
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from accounts.models import User, TeacherProfile
from academics.models import AcademicYear, Classroom, Subject, ClassSubjectAssignment
from students.models import Student
from attendance.models import AttendanceSession, Attendance


class Command(BaseCommand):
    help = 'Seeds sample academic structure, students, and attendance data for local testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm-production',
            action='store_true',
            help='Explicit override flag required if executing while settings.DEBUG is False.'
        )

    def handle(self, *args, **options):
        is_debug = getattr(settings, 'DEBUG', False)
        confirm_prod = options.get('confirm_production', False)
        if not is_debug and not confirm_prod:
            raise CommandError(
                "Execution aborted: Django settings.DEBUG is False. "
                "Seeding sample test data into a production database is prohibited. "
                "Provide the --confirm-production flag if this is an intentional staging drill."
            )

        self.stdout.write('Seeding initial academic dataset...')


        # 1. Teachers and Admins
        teacher, _ = User.objects.get_or_create(
            username='teacher',
            defaults={
                'email': 'teacher@attendance.local',
                'first_name': 'Jane',
                'last_name': 'Doe',
                'role': User.Role.TEACHER,
                'is_staff': True,
            }
        )
        TeacherProfile.objects.get_or_create(
            user=teacher,
            defaults={
                'employee_id': 'EMP-1001',
                'department': 'Science & Mathematics',
                'qualification': 'M.Sc. Mathematics'
            }
        )

        # 2. Academic Year
        academic_year, _ = AcademicYear.objects.get_or_create(
            name='2026-2027',
            defaults={
                'start_date': datetime.date(2026, 6, 1),
                'end_date': datetime.date(2027, 4, 30),
                'is_current': True,
            }
        )

        # 3. Classrooms
        class_10a, _ = Classroom.objects.get_or_create(
            name='Grade 10',
            section='A',
            academic_year=academic_year,
            defaults={'class_teacher': teacher}
        )
        class_10b, _ = Classroom.objects.get_or_create(
            name='Grade 10',
            section='B',
            academic_year=academic_year
        )
        class_9a, _ = Classroom.objects.get_or_create(
            name='Grade 9',
            section='A',
            academic_year=academic_year
        )

        # 4. Subjects
        math_subj, _ = Subject.objects.get_or_create(
            code='MATH-101',
            defaults={'name': 'Mathematics', 'description': 'Advanced Algebra & Trigonometry'}
        )
        science_subj, _ = Subject.objects.get_or_create(
            code='SCI-101',
            defaults={'name': 'Science', 'description': 'Physics and Chemistry fundamentals'}
        )
        english_subj, _ = Subject.objects.get_or_create(
            code='ENG-101',
            defaults={'name': 'English Literature', 'description': 'Grammar and Creative Writing'}
        )

        # 5. Teacher Allocations
        ClassSubjectAssignment.objects.get_or_create(
            classroom=class_10a,
            subject=math_subj,
            defaults={'teacher': teacher}
        )
        ClassSubjectAssignment.objects.get_or_create(
            classroom=class_10a,
            subject=science_subj,
            defaults={'teacher': teacher}
        )

        # 6. Students
        sample_students = [
            {'id': 'STU-10A-001', 'fn': 'Emma', 'ln': 'Watson', 'class': class_10a, 'roll': 1, 'gender': Student.Gender.FEMALE},
            {'id': 'STU-10A-002', 'fn': 'Daniel', 'ln': 'Radcliffe', 'class': class_10a, 'roll': 2, 'gender': Student.Gender.MALE},
            {'id': 'STU-10A-003', 'fn': 'Rupert', 'ln': 'Grint', 'class': class_10a, 'roll': 3, 'gender': Student.Gender.MALE},
            {'id': 'STU-10A-004', 'fn': 'Tom', 'ln': 'Felton', 'class': class_10a, 'roll': 4, 'gender': Student.Gender.MALE},
            {'id': 'STU-10A-005', 'fn': 'Bonnie', 'ln': 'Wright', 'class': class_10a, 'roll': 5, 'gender': Student.Gender.FEMALE},
            {'id': 'STU-10B-001', 'fn': 'Harry', 'ln': 'Styles', 'class': class_10b, 'roll': 1, 'gender': Student.Gender.MALE},
            {'id': 'STU-10B-002', 'fn': 'Taylor', 'ln': 'Swift', 'class': class_10b, 'roll': 2, 'gender': Student.Gender.FEMALE},
        ]

        created_students = []
        for s in sample_students:
            student_obj, _ = Student.objects.get_or_create(
                student_id=s['id'],
                defaults={
                    'first_name': s['fn'],
                    'last_name': s['ln'],
                    'classroom': s['class'],
                    'roll_number': s['roll'],
                    'gender': s['gender'],
                    'email': f"{s['fn'].lower()}@attendance.local",
                }
            )
            created_students.append(student_obj)

        # 7. Sample Attendance Session for Today
        today = timezone.localdate()
        students_10a = [st for st in created_students if st.classroom == class_10a]

        roster_data = [
            {'student': students_10a[0], 'status': Attendance.Status.PRESENT},
            {'student': students_10a[1], 'status': Attendance.Status.PRESENT},
            {'student': students_10a[2], 'status': Attendance.Status.LATE, 'remarks': 'Traffic delay 10 mins'},
            {'student': students_10a[3], 'status': Attendance.Status.ABSENT, 'remarks': 'Doctor visit - note submitted'},
            {'student': students_10a[4], 'status': Attendance.Status.PRESENT},
        ]

        AttendanceSession.record_bulk_attendance(
            classroom=class_10a,
            subject=math_subj,
            date=today,
            recorded_by=teacher,
            student_records=roster_data,
            notes='Chapter 4: Quadratic Equations review'
        )

        self.stdout.write(self.style.SUCCESS(
            'Successfully seeded: 1 Academic Year, 3 Classes, 3 Subjects, 2 Assignments, 7 Students, and today\'s Attendance Session.'
        ))
