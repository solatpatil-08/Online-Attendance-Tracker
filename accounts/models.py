from django.contrib.auth.models import AbstractUser, Group
from django.db import models


class User(AbstractUser):
    """
    Custom User model for Online Attendance Tracking System.
    Provides role-based access control integrated with Django's Group & Permission system.
    """
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Administrator'
        TEACHER = 'TEACHER', 'Teacher'

    ROLE_GROUP_MAPPING = {
        Role.ADMIN: 'Administrator',
        Role.TEACHER: 'Teacher',
    }

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.ADMIN,
        help_text='Designates the role of this user within the attendance tracking system.'
    )
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)

    @property
    def is_administrator(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def is_teacher_user(self):
        return self.role == self.Role.TEACHER

    def save(self, *args, **kwargs):
        # Automatically ensure superusers and staff flags reflect role
        if self.is_superuser:
            self.role = self.Role.ADMIN
            self.is_staff = True
        elif self.role == self.Role.ADMIN:
            self.is_staff = True

        super().save(*args, **kwargs)

    def sync_role_group(self):
        """
        Synchronizes this user's Django Group and permission membership
        strictly with their assigned role.
        """
        target_group_name = self.ROLE_GROUP_MAPPING.get(self.role)
        if not target_group_name:
            return

        target_group, _ = Group.objects.get_or_create(name=target_group_name)

        # Clear other role-managed groups to prevent privilege contamination
        all_role_group_names = list(self.ROLE_GROUP_MAPPING.values())
        for group_name in all_role_group_names:
            if group_name != target_group_name:
                try:
                    g = Group.objects.get(name=group_name)
                    self.groups.remove(g)
                except Group.DoesNotExist:
                    pass

        self.groups.add(target_group)

    def can_manage_academics(self):
        """Check if user has permission to manage academic years, classes, and subjects."""
        return self.is_administrator or self.has_perm('academics.change_classroom')

    def can_manage_students(self):
        """Check if user has permission to add, edit, or remove students."""
        return self.is_administrator or self.has_perm('students.change_student')

    def can_mark_attendance(self, classroom=None, subject=None):
        """
        Check if user can record or update attendance.
        If classroom and subject are provided, teachers must be assigned to that class-subject.
        Inactive users cannot mark attendance.
        """
        if not self.is_active:
            return False

        if self.is_administrator:
            return True

        if not self.is_teacher_user:
            return False

        if classroom is not None and subject is not None:
            # Check teacher's specific class-subject assignment
            return self.teaching_assignments.filter(
                classroom=classroom,
                subject=subject,
                is_active=True
            ).exists()

        return True

    def can_view_reports(self):
        """Check if user has permission to view attendance analytics and summaries."""
        return self.is_administrator or self.is_teacher_user or self.has_perm('attendance.can_view_reports')

    def can_export_attendance(self):
        """Check if user has permission to export attendance datasets to CSV."""
        return self.is_administrator or self.has_perm('attendance.can_export_attendance')

    def __str__(self):
        full_name = self.get_full_name()
        display_name = full_name if full_name else self.username
        return f"{display_name} ({self.get_role_display()})"


class TeacherProfile(models.Model):
    """
    Additional profile information for teacher users.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='teacher_profile'
    )
    employee_id = models.CharField(max_length=50, unique=True, db_index=True)
    qualification = models.CharField(max_length=120, blank=True)
    department = models.CharField(max_length=100, blank=True)
    date_of_joining = models.DateField(blank=True, null=True)

    class Meta:
        verbose_name = 'Teacher Profile'
        verbose_name_plural = 'Teacher Profiles'

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.employee_id})"
