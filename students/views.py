from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.core.exceptions import PermissionDenied
from django.views.generic import ListView, DetailView, CreateView
from django.urls import reverse_lazy

from .models import Student
from accounts.permissions import AdminRequiredMixin, check_teacher_class_authorization


@method_decorator(login_required, name='dispatch')
class StudentListView(ListView):
    """
    Roster view for students:
    - Administrators: Full institutional student directory.
    - Teachers: Only students enrolled in classrooms assigned to this teacher.
    """
    model = Student
    template_name = 'students/student_list.html'
    context_object_name = 'students'

    def get_queryset(self):
        user = self.request.user
        if user.is_administrator:
            return Student.objects.filter(is_active=True).select_related('classroom').order_by('classroom', 'roll_number', 'last_name')

        # Restrict to teacher's assigned classes
        return Student.objects.filter(
            classroom__subject_assignments__teacher=user,
            classroom__subject_assignments__is_active=True,
            is_active=True
        ).distinct().select_related('classroom').order_by('classroom', 'roll_number', 'last_name')


@method_decorator(login_required, name='dispatch')
class StudentDetailView(DetailView):
    """
    Detailed profile view of a student.
    Enforces that teachers can only view students belonging to their assigned classes.
    Unauthorized attempts raise HTTP 403 PermissionDenied.
    """
    model = Student
    template_name = 'students/student_detail.html'
    context_object_name = 'student'

    def get_object(self, queryset=None):
        student = super().get_object(queryset)
        user = self.request.user
        if not check_teacher_class_authorization(user, student.classroom):
            raise PermissionDenied(
                f"You are not authorized to view student records for {student.classroom.display_name}."
            )
        return student


class StudentCreateView(AdminRequiredMixin, CreateView):
    """
    Administrator-only view for enrolling new students.
    Teachers are strictly forbidden (HTTP 403).
    """
    model = Student
    fields = [
        'student_id', 'first_name', 'last_name', 'classroom',
        'roll_number', 'gender', 'date_of_birth', 'enrollment_date',
        'email', 'phone_number', 'guardian_name', 'guardian_phone', 'is_active'
    ]
    template_name = 'students/student_form.html'
    success_url = reverse_lazy('students:student_list')
