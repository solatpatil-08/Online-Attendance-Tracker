from functools import wraps
from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import get_object_or_404
from academics.models import Classroom


class AdminRequiredMixin(UserPassesTestMixin):
    """
    CBV mixin that enforces that the user is authenticated and possesses the Administrator role.
    Redirects unauthenticated users to login; raises PermissionDenied (HTTP 403) for non-admins.
    """
    def test_func(self):
        user = self.request.user
        return user.is_authenticated and user.is_administrator

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        raise PermissionDenied("Access restricted to system administrators.")


class TeacherRequiredMixin(UserPassesTestMixin):
    """
    CBV mixin that permits access to authenticated Teachers (and Administrators as supervisors).
    Redirects unauthenticated users to login; raises PermissionDenied (HTTP 403) for others.
    """
    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (user.is_teacher_user or user.is_administrator)

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        raise PermissionDenied("Access restricted to faculty teachers and administrators.")


def admin_required(view_func):
    """
    View decorator that strictly restricts access to administrators.
    Redirects unauthenticated users to login; raises 403 PermissionDenied for non-admins.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        if not request.user.is_administrator:
            raise PermissionDenied("Access restricted to system administrators.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def teacher_required(view_func):
    """
    View decorator that permits access to teachers and administrators.
    Redirects unauthenticated users to login; raises 403 PermissionDenied for others.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        if not (request.user.is_teacher_user or request.user.is_administrator):
            raise PermissionDenied("Access restricted to faculty teachers and administrators.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def check_teacher_class_authorization(user, classroom):
    """
    Validates whether a user is authorized to access records or take attendance
    for a specific classroom. Administrators have unrestricted institutional access.
    Teachers must have an active ClassSubjectAssignment for the classroom.
    """
    if user.is_administrator:
        return True

    if user.is_teacher_user:
        # Check active class-subject assignments or direct class teacher supervision
        is_assigned_subject = user.teaching_assignments.filter(
            classroom=classroom,
            is_active=True
        ).exists()
        is_class_teacher = (classroom.class_teacher_id == user.id)
        return is_assigned_subject or is_class_teacher

    return False


def teacher_class_access_required(class_param='class_id'):
    """
    Decorator for views operating on a specific classroom.
    Enforces that teachers can only interact with classes assigned to them.
    Raises PermissionDenied (HTTP 403) if the teacher is not assigned to the class.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login
                return redirect_to_login(request.get_full_path())

            class_id = kwargs.get(class_param)
            if class_id:
                classroom = get_object_or_404(Classroom, pk=class_id)
                if not check_teacher_class_authorization(request.user, classroom):
                    raise PermissionDenied(
                        f"You are not assigned to instruct or access records for {classroom.display_name}."
                    )
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
