import datetime
import random
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import User, TeacherProfile
from academics.models import AcademicYear, Classroom, Subject, ClassSubjectAssignment
from students.models import Student
from attendance.models import AttendanceSession, Attendance


class Command(BaseCommand):
    help = (
        "Safely populates the local development database with realistic fictional Indian "
        "school data: 3 admins, 10 teachers, 8 classes, 10 subjects, teaching assignments, "
        "200 students, and 30 days of attendance history."
    )

    DEMO_DOMAIN = "@school.demo"
    DEMO_STUDENT_PREFIX = "IND-2026-"
    DEMO_ACADEMIC_YEAR = "2026-2027"

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Safely purge previously seeded demo data without touching user or production data.'
        )
        parser.add_argument(
            '--password',
            type=str,
            default='DemoPass@123',
            help='Default password to set for all seeded administrator and teacher accounts.'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days of attendance history to generate (default: 30).'
        )
        parser.add_argument(
            '--confirm-production',
            action='store_true',
            help='Explicit override flag required if executing while settings.DEBUG is False.'
        )

    def handle(self, *args, **options):
        # 1. Environment Safety Guard
        is_debug = getattr(settings, 'DEBUG', False)
        confirm_prod = options.get('confirm_production', False)
        if not is_debug and not confirm_prod:
            raise CommandError(
                "Execution aborted: Django settings.DEBUG is False. "
                "To run this demo data seeder in a non-debug environment, "
                "you must provide the --confirm-production flag."
            )

        password = options.get('password', 'DemoPass@123')
        days = options.get('days', 30)
        should_reset = options.get('reset', False)

        if should_reset:
            self.stdout.write(self.style.WARNING("Purging existing demo data..."))
            self.purge_demo_data()
            self.stdout.write(self.style.SUCCESS("Demo data purge completed successfully."))
            return

        self.stdout.write(self.style.MIGRATE_HEADING("=== Seeding Indian School Demo Dataset ==="))

        with transaction.atomic():
            # 2. Seed Academic Year
            academic_year = self.seed_academic_year()

            # 3. Seed Administrators (3)
            admins = self.seed_administrators(password)

            # 4. Seed Teachers & Profiles (10)
            teachers = self.seed_teachers(password)

            # 5. Seed Classrooms (8)
            classrooms = self.seed_classrooms(academic_year, teachers)

            # 6. Seed Subjects (10)
            subjects = self.seed_subjects()

            # 7. Seed Teaching Allocations
            self.seed_teaching_assignments(classrooms, subjects, teachers)

            # 8. Seed Students (200)
            students = self.seed_students(classrooms)

            # 9. Seed 30 Days of Attendance
            total_sessions, total_records = self.seed_attendance(classrooms, days)

        self.print_summary(admins, teachers, classrooms, subjects, students, total_sessions, total_records, password)

    def purge_demo_data(self):
        """
        Safely purges strictly demo-tagged records in reverse dependency order.
        Never touches non-demo records.
        """
        with transaction.atomic():
            # 1. Purge attendance records for demo students
            demo_students = Student.objects.filter(student_id__startswith=self.DEMO_STUDENT_PREFIX)
            deleted_att, _ = Attendance.objects.filter(student__in=demo_students).delete()
            self.stdout.write(f"  - Deleted {deleted_att} demo attendance log records.")

            # 2. Purge attendance sessions for demo classrooms
            demo_classrooms = Classroom.objects.filter(
                academic_year__name=self.DEMO_ACADEMIC_YEAR,
                name__in=['Class 8', 'Class 9', 'Class 10', 'Class 11', 'Class 12']
            )
            deleted_sessions, _ = AttendanceSession.objects.filter(classroom__in=demo_classrooms).delete()
            self.stdout.write(f"  - Deleted {deleted_sessions} demo attendance sessions.")

            # 3. Purge demo students
            deleted_students, _ = demo_students.delete()
            self.stdout.write(f"  - Deleted {deleted_students} demo students.")

            # 4. Purge demo teaching assignments
            deleted_assignments, _ = ClassSubjectAssignment.objects.filter(classroom__in=demo_classrooms).delete()
            self.stdout.write(f"  - Deleted {deleted_assignments} demo teaching assignments.")

            # 5. Purge demo classrooms
            deleted_classrooms, _ = demo_classrooms.delete()
            self.stdout.write(f"  - Deleted {deleted_classrooms} demo classrooms.")

            # 6. Purge demo subjects
            demo_subject_codes = [
                'MATH-01', 'PHY-01', 'CHEM-01', 'BIO-01', 'ENG-01',
                'HIN-01', 'SOC-01', 'CS-01', 'EVS-01', 'ECON-01'
            ]
            deleted_subjects, _ = Subject.objects.filter(code__in=demo_subject_codes).delete()
            self.stdout.write(f"  - Deleted {deleted_subjects} demo subjects.")

            # 7. Purge demo teacher profiles & demo users
            demo_users = User.objects.filter(email__endswith=self.DEMO_DOMAIN)
            demo_user_count = demo_users.count()
            demo_profiles = TeacherProfile.objects.filter(user__in=demo_users)
            demo_profile_count = demo_profiles.count()
            demo_profiles.delete()
            demo_users.delete()
            self.stdout.write(f"  - Deleted {demo_profile_count} teacher profiles and {demo_user_count} demo user accounts.")

            # 8. Clean up demo academic year if no other classes attached
            demo_year = AcademicYear.objects.filter(name=self.DEMO_ACADEMIC_YEAR).first()
            if demo_year and not demo_year.classrooms.exists():
                demo_year.delete()
                self.stdout.write(f"  - Deleted unused demo academic year '{self.DEMO_ACADEMIC_YEAR}'.")

    def seed_academic_year(self):
        self.stdout.write("Seeding academic session...")
        academic_year, created = AcademicYear.objects.get_or_create(
            name=self.DEMO_ACADEMIC_YEAR,
            defaults={
                'start_date': datetime.date(2026, 6, 1),
                'end_date': datetime.date(2027, 4, 30),
                'is_current': True,
            }
        )
        if not created and not academic_year.is_current:
            academic_year.is_current = True
            academic_year.save()
        return academic_year

    def seed_administrators(self, password):
        self.stdout.write("Seeding 3 administrative test accounts...")
        admin_specs = [
            {
                'username': 'admin_rajesh',
                'first_name': 'Rajesh',
                'last_name': 'Sharma',
                'email': f'rajesh.sharma{self.DEMO_DOMAIN}',
                'phone_number': '+91 98200 11001',
                'is_superuser': True,
            },
            {
                'username': 'admin_sunita',
                'first_name': 'Sunita',
                'last_name': 'Patil',
                'email': f'sunita.patil{self.DEMO_DOMAIN}',
                'phone_number': '+91 98200 11002',
                'is_superuser': False,
            },
            {
                'username': 'admin_vikram',
                'first_name': 'Vikram',
                'last_name': 'Deshmukh',
                'email': f'vikram.deshmukh{self.DEMO_DOMAIN}',
                'phone_number': '+91 98200 11003',
                'is_superuser': False,
            },
        ]

        admin_objs = []
        for spec in admin_specs:
            user, created = User.objects.get_or_create(
                username=spec['username'],
                defaults={
                    'first_name': spec['first_name'],
                    'last_name': spec['last_name'],
                    'email': spec['email'],
                    'phone_number': spec['phone_number'],
                    'role': User.Role.ADMIN,
                    'is_staff': True,
                    'is_superuser': spec['is_superuser'],
                    'is_active': True,
                }
            )
            user.first_name = spec['first_name']
            user.last_name = spec['last_name']
            user.email = spec['email']
            user.phone_number = spec['phone_number']
            user.role = User.Role.ADMIN
            user.is_staff = True
            user.is_superuser = spec['is_superuser']
            user.is_active = True
            user.set_password(password)
            user.save()
            user.sync_role_group()
            admin_objs.append(user)

        return admin_objs

    def seed_teachers(self, password):
        self.stdout.write("Seeding 10 fictional faculty records...")
        teacher_specs = [
            ('teacher_sneha', 'Sneha', 'Kulkarni', 'EMP-T101', 'Mathematics', 'M.Sc. Mathematics, B.Ed', '+91 98200 22001'),
            ('teacher_aditya', 'Aditya', 'Joshi', 'EMP-T102', 'Physics & Science', 'M.Sc. Physics, B.Ed', '+91 98200 22002'),
            ('teacher_priya', 'Priya', 'Pawar', 'EMP-T103', 'Chemistry & Science', 'M.Sc. Chemistry', '+91 98200 22003'),
            ('teacher_rahul', 'Rahul', 'Jadhav', 'EMP-T104', 'Life Sciences & Biology', 'M.Sc. Botany, B.Ed', '+91 98200 22004'),
            ('teacher_neha', 'Neha', 'More', 'EMP-T105', 'Languages & Humanities', 'M.A. English Literature, B.Ed', '+91 98200 22005'),
            ('teacher_amit', 'Amit', 'Shinde', 'EMP-T106', 'Languages & Humanities', 'M.A. Hindi, B.Ed', '+91 98200 22006'),
            ('teacher_pooja', 'Pooja', 'Chavan', 'EMP-T107', 'Social Sciences', 'M.A. History & Political Science', '+91 98200 22007'),
            ('teacher_sachin', 'Sachin', 'Kadam', 'EMP-T108', 'Computer Science & IT', 'M.C.A., B.Tech Computer Science', '+91 98200 22008'),
            ('teacher_kavita', 'Kavita', 'Gaikwad', 'EMP-T109', 'Environmental Studies', 'M.Sc. Environmental Science', '+91 98200 22009'),
            ('teacher_manoj', 'Manoj', 'Thorat', 'EMP-T110', 'Economics & Commerce', 'M.A. Economics, B.Ed', '+91 98200 22010'),
        ]

        teacher_map = {}
        for username, fn, ln, emp_id, dept, qual, phone in teacher_specs:
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': fn,
                    'last_name': ln,
                    'email': f"{fn.lower()}.{ln.lower()}{self.DEMO_DOMAIN}",
                    'phone_number': phone,
                    'role': User.Role.TEACHER,
                    'is_staff': False,
                    'is_superuser': False,
                    'is_active': True,
                }
            )
            user.first_name = fn
            user.last_name = ln
            user.email = f"{fn.lower()}.{ln.lower()}{self.DEMO_DOMAIN}"
            user.phone_number = phone
            user.role = User.Role.TEACHER
            user.is_active = True
            user.set_password(password)
            user.save()
            user.sync_role_group()

            TeacherProfile.objects.update_or_create(
                user=user,
                defaults={
                    'employee_id': emp_id,
                    'department': dept,
                    'qualification': qual,
                    'date_of_joining': datetime.date(2023, 6, 1),
                }
            )
            teacher_map[username] = user

        return teacher_map

    def seed_classrooms(self, academic_year, teachers):
        self.stdout.write("Seeding 8 classes and sections...")
        classroom_specs = [
            ('Class 8', 'A', teachers['teacher_sneha']),
            ('Class 8', 'B', teachers['teacher_amit']),
            ('Class 9', 'A', teachers['teacher_aditya']),
            ('Class 9', 'B', teachers['teacher_pooja']),
            ('Class 10', 'A', teachers['teacher_priya']),
            ('Class 10', 'B', teachers['teacher_sachin']),
            ('Class 11', 'A', teachers['teacher_rahul']),
            ('Class 12', 'A', teachers['teacher_neha']),
        ]

        classrooms = []
        for name, sec, teacher in classroom_specs:
            cls_obj, _ = Classroom.objects.get_or_create(
                name=name,
                section=sec,
                academic_year=academic_year,
                defaults={
                    'class_teacher': teacher,
                    'is_active': True,
                }
            )
            if cls_obj.class_teacher != teacher or not cls_obj.is_active:
                cls_obj.class_teacher = teacher
                cls_obj.is_active = True
                cls_obj.save()
            classrooms.append(cls_obj)

        return classrooms

    def seed_subjects(self):
        self.stdout.write("Seeding 10 core academic subjects...")
        subject_specs = [
            ('MATH-01', 'Mathematics', 'Algebra, Trigonometry, Geometry, and Advanced Calculus'),
            ('PHY-01', 'Physics', 'Mechanics, Heat, Optics, Electricity, and Modern Physics'),
            ('CHEM-01', 'Chemistry', 'Physical, Organic, and Inorganic Chemistry Principles'),
            ('BIO-01', 'Biology', 'Botanical Sciences, Zoology, Genetics, and Physiology'),
            ('ENG-01', 'English', 'Language, Comprehension, Writing Skills, and Literature'),
            ('HIN-01', 'Hindi', 'Vyakaran, Rachna, Kavita evam Natak'),
            ('SOC-01', 'Social Science', 'History, Geography, Political Science, and Economics'),
            ('CS-01', 'Computer Science', 'Python Programming, Data Structures, and SQL'),
            ('EVS-01', 'Environmental Science', 'Ecosystems, Biodiversity, Conservation, and Sustainability'),
            ('ECON-01', 'Economics', 'Macroeconomics, Microeconomics, and Indian Economic Policies'),
        ]

        subject_map = {}
        for code, name, desc in subject_specs:
            subj_obj, _ = Subject.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'description': desc,
                    'is_active': True,
                }
            )
            if subj_obj.name != name or not subj_obj.is_active:
                subj_obj.name = name
                subj_obj.description = desc
                subj_obj.is_active = True
                subj_obj.save()
            subject_map[code] = subj_obj

        return subject_map

    def seed_teaching_assignments(self, classrooms, subjects, teachers):
        self.stdout.write("Configuring valid teacher-class-subject allocations...")
        allocations = {
            ('Class 8', 'A'): [
                ('MATH-01', 'teacher_sneha'),
                ('ENG-01', 'teacher_neha'),
                ('HIN-01', 'teacher_amit'),
                ('SOC-01', 'teacher_pooja'),
                ('EVS-01', 'teacher_kavita'),
            ],
            ('Class 8', 'B'): [
                ('MATH-01', 'teacher_sneha'),
                ('ENG-01', 'teacher_neha'),
                ('HIN-01', 'teacher_amit'),
                ('SOC-01', 'teacher_pooja'),
                ('CS-01', 'teacher_sachin'),
            ],
            ('Class 9', 'A'): [
                ('MATH-01', 'teacher_sneha'),
                ('PHY-01', 'teacher_aditya'),
                ('CHEM-01', 'teacher_priya'),
                ('ENG-01', 'teacher_neha'),
                ('CS-01', 'teacher_sachin'),
            ],
            ('Class 9', 'B'): [
                ('MATH-01', 'teacher_sneha'),
                ('BIO-01', 'teacher_rahul'),
                ('ENG-01', 'teacher_neha'),
                ('HIN-01', 'teacher_amit'),
                ('SOC-01', 'teacher_pooja'),
            ],
            ('Class 10', 'A'): [
                ('MATH-01', 'teacher_sneha'),
                ('PHY-01', 'teacher_aditya'),
                ('CHEM-01', 'teacher_priya'),
                ('BIO-01', 'teacher_rahul'),
                ('ENG-01', 'teacher_neha'),
            ],
            ('Class 10', 'B'): [
                ('MATH-01', 'teacher_sneha'),
                ('PHY-01', 'teacher_aditya'),
                ('CHEM-01', 'teacher_priya'),
                ('SOC-01', 'teacher_pooja'),
                ('HIN-01', 'teacher_amit'),
            ],
            ('Class 11', 'A'): [
                ('PHY-01', 'teacher_aditya'),
                ('CHEM-01', 'teacher_priya'),
                ('MATH-01', 'teacher_sneha'),
                ('BIO-01', 'teacher_rahul'),
                ('CS-01', 'teacher_sachin'),
            ],
            ('Class 12', 'A'): [
                ('PHY-01', 'teacher_aditya'),
                ('CHEM-01', 'teacher_priya'),
                ('MATH-01', 'teacher_sneha'),
                ('ECON-01', 'teacher_manoj'),
                ('ENG-01', 'teacher_neha'),
            ],
        }

        classroom_dict = {(c.name, c.section): c for c in classrooms}

        for (cls_name, sec), subj_teachers in allocations.items():
            cls_obj = classroom_dict[(cls_name, sec)]
            for code, t_username in subj_teachers:
                subj_obj = subjects[code]
                t_user = teachers[t_username]
                assignment, _ = ClassSubjectAssignment.objects.get_or_create(
                    classroom=cls_obj,
                    subject=subj_obj,
                    defaults={
                        'teacher': t_user,
                        'is_active': True,
                    }
                )
                if assignment.teacher != t_user or not assignment.is_active:
                    assignment.teacher = t_user
                    assignment.is_active = True
                    assignment.save()

    def seed_students(self, classrooms):
        self.stdout.write("Seeding 200 enrolled students with realistic Indian profiles...")

        male_first_names = [
            'Aarav', 'Rohan', 'Aditya', 'Rahul', 'Sai', 'Vihaan', 'Arjun', 'Reyansh',
            'Aryan', 'Kabir', 'Atharva', 'Dhruv', 'Vivaan', 'Shaurya', 'Samar', 'Harsh',
            'Dev', 'Tanmay', 'Om', 'Parth', 'Pranav', 'Yash', 'Tejas', 'Kunal', 'Jay',
            'Nishant', 'Ayush', 'Sarthak', 'Chinmay', 'Aniket', 'Siddharth', 'Varun',
            'Gaurav', 'Manish', 'Alok', 'Deepak', 'Mayur', 'Sameer', 'Pravin', 'Girish'
        ]

        female_first_names = [
            'Ananya', 'Sneha', 'Priya', 'Neha', 'Diya', 'Saanvi', 'Ishita', 'Riya',
            'Anika', 'Myra', 'Ira', 'Kiara', 'Pari', 'Avni', 'Tanvi', 'Aditi',
            'Shreya', 'Riddhi', 'Siddhi', 'Gauri', 'Janhavi', 'Swara', 'Meera',
            'Sanjana', 'Arya', 'Radhika', 'Mansi', 'Sakshi', 'Rutuja', 'Pooja',
            'Divya', 'Aishwarya', 'Komal', 'Prachi', 'Kalyani', 'Pallavi', 'Sonali',
            'Sheetal', 'Sayali', 'Vaishnavi'
        ]

        last_names = [
            'Sharma', 'Patil', 'Deshmukh', 'Kulkarni', 'Joshi', 'Pawar', 'Jadhav', 'More',
            'Shinde', 'Chavan', 'Kadam', 'Gaikwad', 'Thorat', 'Bhosale', 'Sawant', 'Salunkhe',
            'Mohite', 'Ghorpade', 'Jagtap', 'Kale', 'Mane', 'Sonawane', 'Kamble', 'Bhalerao',
            'Waghmare', 'Nikam', 'Surve', 'Darekar', 'Tambe', 'Sathe', 'Ghodke', 'Khare',
            'Date', 'Apte', 'Natu', 'Pendse', 'Bhave', 'Kelkar', 'Gadgil', 'Gokhale'
        ]

        guardian_first_names = [
            'Suresh', 'Ramesh', 'Mahesh', 'Sunil', 'Anil', 'Dinesh', 'Ashok', 'Vijay',
            'Prakash', 'Sanjay', 'Dilip', 'Santosh', 'Rajendra', 'Pradeep', 'Subhash'
        ]

        birth_year_map = {
            'Class 8': 2012,
            'Class 9': 2011,
            'Class 10': 2010,
            'Class 11': 2009,
            'Class 12': 2008,
        }

        enrollment_date = datetime.date(2026, 6, 1)
        created_students = []
        global_index = 1

        for cls_obj in classrooms:
            birth_year = birth_year_map.get(cls_obj.name, 2010)

            for roll in range(1, 26):
                student_id = f"{self.DEMO_STUDENT_PREFIX}{global_index:04d}"
                is_female = (roll % 2 == 0)

                if is_female:
                    first_name = female_first_names[(global_index + roll) % len(female_first_names)]
                    gender = Student.Gender.FEMALE
                else:
                    first_name = male_first_names[(global_index + roll) % len(male_first_names)]
                    gender = Student.Gender.MALE

                last_name = last_names[(global_index * 3 + roll) % len(last_names)]
                guardian_fn = guardian_first_names[(global_index + roll) % len(guardian_first_names)]
                guardian_name = f"{guardian_fn} {last_name}"

                b_month = ((roll * 7) % 12) + 1
                b_day = ((roll * 11) % 28) + 1
                dob = datetime.date(birth_year, b_month, b_day)

                phone = f"+91 98200 {global_index:05d}"
                guardian_phone = f"+91 98201 {global_index:05d}"
                email = f"student.{global_index:04d}{self.DEMO_DOMAIN}"

                student = Student.objects.filter(student_id=student_id).first()
                if student:
                    student.first_name = first_name
                    student.last_name = last_name
                    student.email = email
                    student.phone_number = phone
                    student.gender = gender
                    student.date_of_birth = dob
                    student.classroom = cls_obj
                    student.roll_number = roll
                    student.enrollment_date = enrollment_date
                    student.is_active = True
                    student.guardian_name = guardian_name
                    student.guardian_phone = guardian_phone
                    student.save()
                else:
                    student = Student.objects.create(
                        student_id=student_id,
                        first_name=first_name,
                        last_name=last_name,
                        email=email,
                        phone_number=phone,
                        gender=gender,
                        date_of_birth=dob,
                        classroom=cls_obj,
                        roll_number=roll,
                        enrollment_date=enrollment_date,
                        is_active=True,
                        guardian_name=guardian_name,
                        guardian_phone=guardian_phone,
                    )
                created_students.append(student)
                global_index += 1

        return created_students

    def seed_attendance(self, classrooms, days=30):
        self.stdout.write(f"Generating realistic attendance records spanning the previous {days} days...")

        today = timezone.localdate()
        date_list = [today - datetime.timedelta(days=d) for d in range(days - 1, -1, -1)]

        late_remarks = [
            "School bus delayed due to traffic",
            "Heavy rain in transit area",
            "Public transport delay",
            "Bicycle puncture on the way",
            "Morning vehicle breakdown",
            "Late arrival - 10 minutes",
            "Traffic congestion at railway crossing",
        ]

        absent_remarks = [
            "Uninformed absence",
            "Absent - message sent to guardian",
            "Not reported by morning roll call",
            "Absence noted",
        ]

        excused_remarks = [
            "Medical leave - doctor prescription submitted",
            "Viral fever - leave application submitted",
            "Participating in inter-school science exhibition",
            "Attending family wedding / function",
            "Dental appointment - prior permission granted",
            "District sports tournament representation",
        ]

        total_sessions = 0
        total_records = 0
        attendance_batch = []

        for cls_obj in classrooms:
            assignments = list(
                ClassSubjectAssignment.objects.filter(classroom=cls_obj, is_active=True).select_related('subject', 'teacher')
            )
            if not assignments:
                continue

            students = list(
                Student.objects.filter(classroom=cls_obj, is_active=True).order_by('roll_number')
            )
            if not students:
                continue

            for curr_date in date_list:
                # Exclude Sundays
                if curr_date.weekday() == 6:
                    continue

                day_offset = curr_date.weekday() % 2
                day_assignments = [
                    assignments[i] for i in range(len(assignments)) if i % 2 == day_offset
                ]
                if not day_assignments:
                    day_assignments = assignments[:2]

                for asgn in day_assignments:
                    subj_obj = asgn.subject
                    teacher_user = asgn.teacher

                    session, _ = AttendanceSession.objects.update_or_create(
                        classroom=cls_obj,
                        subject=subj_obj,
                        date=curr_date,
                        defaults={
                            'recorded_by': teacher_user,
                            'notes': f"Daily lecture session: {subj_obj.name}",
                        }
                    )
                    total_sessions += 1

                    for student in students:
                        seed_val = hash(f"{student.student_id}:{curr_date.isoformat()}:{subj_obj.code}")
                        rng = random.Random(seed_val)
                        roll_p = rng.random()

                        if roll_p < 0.84:
                            status = Attendance.Status.PRESENT
                            remarks = ""
                        elif roll_p < 0.91:
                            status = Attendance.Status.LATE
                            remarks = rng.choice(late_remarks)
                        elif roll_p < 0.96:
                            status = Attendance.Status.ABSENT
                            remarks = rng.choice(absent_remarks)
                        else:
                            status = Attendance.Status.EXCUSED
                            remarks = rng.choice(excused_remarks)

                        attendance_batch.append(
                            Attendance(
                                session=session,
                                student=student,
                                classroom=cls_obj,
                                subject=subj_obj,
                                date=curr_date,
                                status=status,
                                recorded_by=teacher_user,
                                remarks=remarks,
                            )
                        )

                        if len(attendance_batch) >= 1000:
                            Attendance.objects.bulk_create(
                                attendance_batch,
                                update_conflicts=True,
                                unique_fields=['student', 'classroom', 'subject', 'date'],
                                update_fields=['session', 'status', 'recorded_by', 'remarks']
                            )
                            total_records += len(attendance_batch)
                            attendance_batch.clear()

        if attendance_batch:
            Attendance.objects.bulk_create(
                attendance_batch,
                update_conflicts=True,
                unique_fields=['student', 'classroom', 'subject', 'date'],
                update_fields=['session', 'status', 'recorded_by', 'remarks']
            )
            total_records += len(attendance_batch)
            attendance_batch.clear()

        return total_sessions, total_records

    def print_summary(self, admins, teachers, classrooms, subjects, students, total_sessions, total_records, password):
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 70))
        self.stdout.write(self.style.SUCCESS("  DEMO DATA POPULATION COMPLETED SUCCESSFULLY"))
        self.stdout.write(self.style.SUCCESS("=" * 70))
        self.stdout.write(f"• Academic Year:        {self.DEMO_ACADEMIC_YEAR} (Active Session)")
        self.stdout.write(f"• Administrators:       {len(admins)} accounts created/verified")
        self.stdout.write(f"• Teachers:             {len(teachers)} faculty accounts + profiles")
        self.stdout.write(f"• Classrooms:           {len(classrooms)} classes/sections (Grades 8 - 12)")
        self.stdout.write(f"• Core Subjects:        {len(subjects)} subjects")
        self.stdout.write(f"• Enrolled Students:    {len(students)} students (25 per class, roll #1-25)")
        self.stdout.write(f"• Attendance Sessions:  {total_sessions} sessions across previous 30 days")
        self.stdout.write(f"• Attendance Records:   {total_records} student attendance records")
        self.stdout.write(f"• Default Demo Password: {password}")
        self.stdout.write("")
        self.stdout.write("Credential Cheat Sheet:")
        self.stdout.write("  - Super Admin:     admin_rajesh  /  " + password)
        self.stdout.write("  - Staff Admin:     admin_sunita  /  " + password)
        self.stdout.write("  - Math Teacher:    teacher_sneha /  " + password)
        self.stdout.write("  - Physics Teacher: teacher_aditya / " + password)
        self.stdout.write("=" * 70)
