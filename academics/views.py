from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView, CreateView
from django.urls import reverse_lazy

from .models import Classroom, Subject
from accounts.permissions import AdminRequiredMixin, teacher_class_access_required


@method_decorator(login_required, name='dispatch')
class ClassroomListView(ListView):
    """
    Lists classrooms based on user authorization:
    - Administrators: All institutional classrooms.
    - Teachers: Only classrooms to which they are actively allocated.
    """
    model = Classroom
    template_name = 'academics/classroom_list.html'
    context_object_name = 'classrooms'

    def get_queryset(self):
        user = self.request.user
        if user.is_administrator:
            return Classroom.objects.filter(is_active=True).select_related('academic_year', 'class_teacher')
        return Classroom.objects.filter(
            subject_assignments__teacher=user,
            subject_assignments__is_active=True,
            is_active=True
        ).distinct().select_related('academic_year', 'class_teacher')


@method_decorator(teacher_class_access_required(class_param='pk'), name='dispatch')
class ClassroomDetailView(DetailView):
    """
    Displays roster and subject allocations for a specific classroom.
    Strictly enforced: Teachers can ONLY access classes assigned to them.
    Unassigned teachers receive HTTP 403 PermissionDenied.
    """
    model = Classroom
    template_name = 'academics/classroom_detail.html'
    context_object_name = 'classroom'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        classroom = self.object
        context['students'] = classroom.students.filter(is_active=True).order_by('roll_number', 'last_name')
        context['assignments'] = classroom.subject_assignments.filter(is_active=True).select_related('subject', 'teacher')
        return context


class ClassroomCreateView(AdminRequiredMixin, CreateView):
    """
    Administrator-only view for creating new classrooms.
    Teachers are strictly forbidden (HTTP 403).
    """
    model = Classroom
    fields = ['name', 'section', 'academic_year', 'class_teacher', 'is_active']
    template_name = 'academics/classroom_form.html'
    success_url = reverse_lazy('academics:classroom_list')


@method_decorator(login_required, name='dispatch')
class SubjectListView(ListView):
    """
    Catalog of institutional academic subjects.
    """
    model = Subject
    template_name = 'academics/subject_list.html'
    context_object_name = 'subjects'

    def get_queryset(self):
        return Subject.objects.filter(is_active=True).order_by('name')


class SubjectCreateView(AdminRequiredMixin, CreateView):
    """
    Administrator-only view for defining new academic subjects.
    """
    model = Subject
    fields = ['name', 'code', 'description', 'is_active']
    template_name = 'academics/subject_form.html'
    success_url = reverse_lazy('academics:subject_list')
