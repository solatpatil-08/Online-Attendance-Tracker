from django.db.models.signals import post_save, post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import Group, Permission
from .models import User


def assign_role_permissions():
    """
    Ensures 'Administrator' and 'Teacher' groups exist and are equipped
    with their appropriate model and custom permissions.
    """
    admin_group, _ = Group.objects.get_or_create(name='Administrator')
    teacher_group, _ = Group.objects.get_or_create(name='Teacher')

    # Specific permission codenames for teachers
    teacher_permissions_codenames = [
        # Student viewing
        'view_student',
        # Academics viewing
        'view_classroom',
        'view_subject',
        'view_classsubjectassignment',
        # Attendance operations
        'view_attendancesession',
        'add_attendancesession',
        'change_attendancesession',
        'view_attendance',
        'add_attendance',
        'change_attendance',
        'can_mark_attendance',
        'can_view_reports',
    ]

    for codename in teacher_permissions_codenames:
        perm = Permission.objects.filter(codename=codename).first()
        if perm:
            teacher_group.permissions.add(perm)

    # Administrator group receives all permissions across core system apps
    for app_label in ['accounts', 'academics', 'students', 'attendance']:
        perms = Permission.objects.filter(content_type__app_label=app_label)
        admin_group.permissions.add(*perms)


@receiver(post_save, sender=User)
def user_role_group_sync_receiver(sender, instance, created, **kwargs):
    """
    Ensures every User instance is synchronized with their assigned role Group.
    """
    instance.sync_role_group()


@receiver(post_migrate)
def setup_roles_and_permissions_receiver(sender, **kwargs):
    """
    Triggered after migrations are applied to bootstrap/update group permissions.
    Runs when accounts or attendance finishes migrating.
    """
    if sender.name in ['accounts', 'attendance']:
        assign_role_permissions()
