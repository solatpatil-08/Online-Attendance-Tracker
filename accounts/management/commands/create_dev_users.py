from django.core.management.base import BaseCommand
from accounts.models import User, TeacherProfile


class Command(BaseCommand):
    help = 'Creates default development users (Admin and Teacher) for quick local testing'

    def handle(self, *args, **options):
        # Admin User
        admin_user, created_admin = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@attendance.local',
                'first_name': 'System',
                'last_name': 'Administrator',
                'role': User.Role.ADMIN,
                'is_staff': True,
                'is_superuser': True,
            }
        )
        if created_admin:
            admin_user.set_password('admin123')
            admin_user.save()
            self.stdout.write(self.style.SUCCESS('Created default Administrator: username="admin", password="admin123"'))
        else:
            self.stdout.write(self.style.WARNING('Administrator user "admin" already exists.'))

        # Teacher User
        teacher_user, created_teacher = User.objects.get_or_create(
            username='teacher',
            defaults={
                'email': 'teacher@attendance.local',
                'first_name': 'Jane',
                'last_name': 'Doe',
                'role': User.Role.TEACHER,
                'is_staff': False,
                'is_superuser': False,
            }
        )
        if created_teacher:
            teacher_user.set_password('teacher123')
            teacher_user.save()
            TeacherProfile.objects.create(
                user=teacher_user,
                employee_id='EMP-1001',
                department='Computer Science',
                qualification='M.Tech Software Engineering'
            )
            self.stdout.write(self.style.SUCCESS('Created default Teacher: username="teacher", password="teacher123"'))
        else:
            self.stdout.write(self.style.WARNING('Teacher user "teacher" already exists.'))
