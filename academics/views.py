from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView, CreateView, UpdateView, View
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.db.models import Q, Count

from .models import Classroom, Subject, ClassSubjectAssignment, AcademicYear
from .forms import ClassroomForm, SubjectForm, ClassSubjectAssignmentForm
from accounts.models import User
from accounts.permissions import AdminRequiredMixin, teacher_class_access_required


# ==============================================================================
# Classroom Management Views
# ==============================================================================

@method_decorator(login_required, name='dispatch')
class ClassroomListView(ListView):
    """
    Lists classrooms based on user authorization:
    - Administrators: All institutional classrooms with search, academic year filters, and status filters.
    - Teachers: Only classrooms to which they are actively allocated.
    """
    model = Classroom
    template_name = 'academics/classroom_list.html'
    context_object_name = 'classrooms'
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user
        if user.is_administrator:
            qs = Classroom.objects.all().select_related('academic_year', 'class_teacher')

            # 1. Search Query (name, section, class teacher)
            q = self.request.GET.get('q', '').strip()
            if q:
                qs = qs.filter(
                    Q(name__icontains=q) |
                    Q(section__icontains=q) |
                    Q(class_teacher__first_name__icontains=q) |
                    Q(class_teacher__last_name__icontains=q) |
                    Q(class_teacher__username__icontains=q)
                )

            # 2. Academic Year filter
            year_id = self.request.GET.get('academic_year', '').strip()
            if year_id:
                qs = qs.filter(academic_year_id=year_id)

            # 3. Status filter ('active', 'inactive', 'all')
            status = self.request.GET.get('status', 'all').strip()
            if status == 'active':
                qs = qs.filter(is_active=True)
            elif status == 'inactive':
                qs = qs.filter(is_active=False)

            return qs.order_by('academic_year', 'name', 'section')
        else:
            return Classroom.objects.filter(
                Q(subject_assignments__teacher=user, subject_assignments__is_active=True) |
                Q(class_teacher=user),
                is_active=True
            ).distinct().select_related('academic_year', 'class_teacher').order_by('name', 'section')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        params = self.request.GET.copy()
        params.pop('page', None)
        context['query_string'] = params.urlencode()

        if user.is_administrator:
            all_classes = Classroom.objects.all()
            context.update({
                'academic_years': AcademicYear.objects.all().order_by('-is_current', '-start_date'),
                'search_query': self.request.GET.get('q', '').strip(),
                'selected_year': self.request.GET.get('academic_year', '').strip(),
                'selected_status': self.request.GET.get('status', 'all').strip(),
                'total_count': all_classes.count(),
                'active_count': all_classes.filter(is_active=True).count(),
                'inactive_count': all_classes.filter(is_active=False).count(),
            })
        return context


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
        context['students'] = classroom.students.all().order_by('roll_number', 'last_name', 'first_name')
        context['assignments'] = classroom.subject_assignments.all().select_related('subject', 'teacher')
        if self.request.user.is_administrator:
            context['assign_form'] = ClassSubjectAssignmentForm(classroom_fixed=classroom)
        return context


class ClassroomCreateView(AdminRequiredMixin, CreateView):
    """
    Administrator-only view for creating new classrooms.
    Validates duplicate class name and section within the same academic year.
    """
    model = Classroom
    form_class = ClassroomForm
    template_name = 'academics/classroom_form.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"Classroom '{self.object.display_name}' ({self.object.academic_year.name}) created successfully."
        )
        return response

    def get_success_url(self):
        return reverse('academics:classroom_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_edit'] = False
        return context


class ClassroomUpdateView(AdminRequiredMixin, UpdateView):
    """
    Administrator-only view for updating classroom details, division, academic year, and supervisor.
    """
    model = Classroom
    form_class = ClassroomForm
    template_name = 'academics/classroom_form.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"Classroom '{self.object.display_name}' details updated successfully."
        )
        return response

    def get_success_url(self):
        return reverse('academics:classroom_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_edit'] = True
        context['classroom'] = self.object
        return context


class ClassroomToggleStatusView(AdminRequiredMixin, View):
    """
    Administrator view to activate or deactivate a classroom.
    """
    def post(self, request, pk):
        classroom = get_object_or_404(Classroom, pk=pk)
        classroom.is_active = not classroom.is_active
        classroom.save(update_fields=['is_active', 'updated_at'])
        status_label = "activated" if classroom.is_active else "deactivated"
        messages.info(request, f"Classroom '{classroom.display_name}' has been {status_label}.")

        next_url = request.POST.get('next')
        if next_url:
            return redirect(next_url)
        return redirect('academics:classroom_detail', pk=classroom.pk)


class ClassroomAssignSubjectView(AdminRequiredMixin, View):
    """
    Administrator action to assign a subject and teacher directly from the Classroom Detail page.
    """
    def post(self, request, pk):
        classroom = get_object_or_404(Classroom, pk=pk)
        if not classroom.is_active:
            messages.error(request, f"Cannot assign subjects to inactive classroom '{classroom.display_name}'.")
            return redirect('academics:classroom_detail', pk=classroom.pk)

        subject_id = request.POST.get('subject')
        teacher_id = request.POST.get('teacher')

        if not subject_id or not teacher_id:
            messages.error(request, "Please select both a subject and an instructor teacher.")
            return redirect('academics:classroom_detail', pk=classroom.pk)

        subject = get_object_or_404(Subject, pk=subject_id)
        teacher = get_object_or_404(User, pk=teacher_id, role=User.Role.TEACHER)

        if not subject.is_active:
            messages.error(request, f"Cannot assign inactive subject '{subject.name}'.")
            return redirect('academics:classroom_detail', pk=classroom.pk)

        if not teacher.is_active:
            messages.error(request, f"Cannot assign inactive teacher '{teacher.get_full_name() or teacher.username}'.")
            return redirect('academics:classroom_detail', pk=classroom.pk)

        # Check existing assignment
        existing = ClassSubjectAssignment.objects.filter(classroom=classroom, subject=subject).first()
        if existing:
            existing_teacher = existing.teacher.get_full_name() or existing.teacher.username
            messages.error(
                request,
                f"Subject '{subject.name}' is already assigned to this classroom (assigned to {existing_teacher}). "
                "Unassign or update the existing assignment."
            )
            return redirect('academics:classroom_detail', pk=classroom.pk)

        ClassSubjectAssignment.objects.create(
            classroom=classroom,
            subject=subject,
            teacher=teacher,
            is_active=True
        )
        messages.success(
            request,
            f"Successfully assigned {subject.name} to {teacher.get_full_name() or teacher.username} for {classroom.display_name}."
        )
        return redirect('academics:classroom_detail', pk=classroom.pk)


class ClassroomRemoveSubjectView(AdminRequiredMixin, View):
    """
    Administrator action to remove an allocated subject and teacher from a classroom.
    """
    def post(self, request, pk, assignment_id):
        classroom = get_object_or_404(Classroom, pk=pk)
        assignment = get_object_or_404(ClassSubjectAssignment, pk=assignment_id, classroom=classroom)
        subj_name = assignment.subject.name
        teacher_name = assignment.teacher.get_full_name() or assignment.teacher.username
        assignment.delete()
        messages.success(
            request,
            f"Removed subject '{subj_name}' (Instructor: {teacher_name}) from {classroom.display_name}."
        )
        return redirect('academics:classroom_detail', pk=classroom.pk)


# ==============================================================================
# Subject Management Views
# ==============================================================================

@method_decorator(login_required, name='dispatch')
class SubjectListView(ListView):
    """
    Catalog of institutional academic subjects with search, status filters, and pagination.
    """
    model = Subject
    template_name = 'academics/subject_list.html'
    context_object_name = 'subjects'
    paginate_by = 10

    def get_queryset(self):
        qs = Subject.objects.all().annotate(assignment_count=Count('class_assignments'))

        # 1. Search Query (name, code)
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))

        # 2. Status filter ('active', 'inactive', 'all')
        status = self.request.GET.get('status', 'all').strip()
        if status == 'active':
            qs = qs.filter(is_active=True)
        elif status == 'inactive':
            qs = qs.filter(is_active=False)

        return qs.order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_subjects = Subject.objects.all()

        params = self.request.GET.copy()
        params.pop('page', None)
        context['query_string'] = params.urlencode()

        context.update({
            'search_query': self.request.GET.get('q', '').strip(),
            'selected_status': self.request.GET.get('status', 'all').strip(),
            'total_count': all_subjects.count(),
            'active_count': all_subjects.filter(is_active=True).count(),
            'inactive_count': all_subjects.filter(is_active=False).count(),
        })
        return context


@method_decorator(login_required, name='dispatch')
class SubjectDetailView(DetailView):
    """
    Displays subject information and all related class-teacher teaching assignments.
    """
    model = Subject
    template_name = 'academics/subject_detail.html'
    context_object_name = 'subject'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subject = self.object
        context['assignments'] = subject.class_assignments.select_related(
            'classroom', 'classroom__academic_year', 'teacher'
        ).order_by('classroom__name', 'classroom__section')
        if self.request.user.is_administrator:
            context['assign_form'] = ClassSubjectAssignmentForm(subject_fixed=subject)
        return context


class SubjectCreateView(AdminRequiredMixin, CreateView):
    """
    Administrator-only view for defining new academic subjects.
    Validates unique subject codes.
    """
    model = Subject
    form_class = SubjectForm
    template_name = 'academics/subject_form.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"Subject '{self.object.name}' ({self.object.code}) created successfully."
        )
        return response

    def get_success_url(self):
        return reverse('academics:subject_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_edit'] = False
        return context


class SubjectUpdateView(AdminRequiredMixin, UpdateView):
    """
    Administrator-only view for updating subject details and course codes.
    """
    model = Subject
    form_class = SubjectForm
    template_name = 'academics/subject_form.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"Subject '{self.object.name}' ({self.object.code}) updated successfully."
        )
        return response

    def get_success_url(self):
        return reverse('academics:subject_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_edit'] = True
        context['subject'] = self.object
        return context


class SubjectToggleStatusView(AdminRequiredMixin, View):
    """
    Administrator view to activate or deactivate an academic subject.
    """
    def post(self, request, pk):
        subject = get_object_or_404(Subject, pk=pk)
        subject.is_active = not subject.is_active
        subject.save(update_fields=['is_active', 'updated_at'])
        status_label = "activated" if subject.is_active else "deactivated"
        messages.info(request, f"Subject '{subject.name}' ({subject.code}) has been {status_label}.")

        next_url = request.POST.get('next')
        if next_url:
            return redirect(next_url)
        return redirect('academics:subject_detail', pk=subject.pk)


class SubjectAssignClassView(AdminRequiredMixin, View):
    """
    Administrator action to assign this subject to a classroom & teacher from the Subject Detail view.
    """
    def post(self, request, pk):
        subject = get_object_or_404(Subject, pk=pk)
        if not subject.is_active:
            messages.error(request, f"Cannot assign inactive subject '{subject.name}'.")
            return redirect('academics:subject_detail', pk=subject.pk)

        classroom_id = request.POST.get('classroom')
        teacher_id = request.POST.get('teacher')

        if not classroom_id or not teacher_id:
            messages.error(request, "Please select both a classroom and an instructor teacher.")
            return redirect('academics:subject_detail', pk=subject.pk)

        classroom = get_object_or_404(Classroom, pk=classroom_id)
        teacher = get_object_or_404(User, pk=teacher_id, role=User.Role.TEACHER)

        if not classroom.is_active:
            messages.error(request, f"Cannot assign to inactive classroom '{classroom.display_name}'.")
            return redirect('academics:subject_detail', pk=subject.pk)

        if not teacher.is_active:
            messages.error(request, f"Cannot assign inactive teacher '{teacher.get_full_name() or teacher.username}'.")
            return redirect('academics:subject_detail', pk=subject.pk)

        existing = ClassSubjectAssignment.objects.filter(classroom=classroom, subject=subject).first()
        if existing:
            existing_teacher = existing.teacher.get_full_name() or existing.teacher.username
            messages.error(
                request,
                f"This subject is already assigned to {classroom.display_name} (assigned to {existing_teacher})."
            )
            return redirect('academics:subject_detail', pk=subject.pk)

        ClassSubjectAssignment.objects.create(
            classroom=classroom,
            subject=subject,
            teacher=teacher,
            is_active=True
        )
        messages.success(
            request,
            f"Successfully assigned {subject.name} to {teacher.get_full_name() or teacher.username} for {classroom.display_name}."
        )
        return redirect('academics:subject_detail', pk=subject.pk)


# ==============================================================================
# Institutional Teaching Assignments Management
# ==============================================================================

class AssignmentListView(AdminRequiredMixin, ListView):
    """
    Institutional overview of all class-subject-teacher teaching allocations.
    Provides search, classroom, subject, and teacher filters, and pagination.
    """
    model = ClassSubjectAssignment
    template_name = 'academics/assignment_list.html'
    context_object_name = 'assignments'
    paginate_by = 15

    def get_queryset(self):
        qs = ClassSubjectAssignment.objects.select_related(
            'classroom', 'classroom__academic_year', 'subject', 'teacher'
        )

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(classroom__name__icontains=q) |
                Q(classroom__section__icontains=q) |
                Q(subject__name__icontains=q) |
                Q(subject__code__icontains=q) |
                Q(teacher__first_name__icontains=q) |
                Q(teacher__last_name__icontains=q) |
                Q(teacher__username__icontains=q)
            )

        cr_id = self.request.GET.get('classroom', '').strip()
        if cr_id:
            qs = qs.filter(classroom_id=cr_id)

        subj_id = self.request.GET.get('subject', '').strip()
        if subj_id:
            qs = qs.filter(subject_id=subj_id)

        teacher_id = self.request.GET.get('teacher', '').strip()
        if teacher_id:
            qs = qs.filter(teacher_id=teacher_id)

        status = self.request.GET.get('status', 'all').strip()
        if status == 'active':
            qs = qs.filter(is_active=True)
        elif status == 'inactive':
            qs = qs.filter(is_active=False)

        return qs.order_by('classroom__name', 'classroom__section', 'subject__name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_assignments = ClassSubjectAssignment.objects.all()

        params = self.request.GET.copy()
        params.pop('page', None)
        context['query_string'] = params.urlencode()

        context.update({
            'classrooms': Classroom.objects.filter(is_active=True).order_by('name', 'section'),
            'subjects': Subject.objects.filter(is_active=True).order_by('name'),
            'teachers': User.objects.filter(role=User.Role.TEACHER, is_active=True).order_by('last_name', 'first_name'),
            'search_query': self.request.GET.get('q', '').strip(),
            'selected_classroom': self.request.GET.get('classroom', '').strip(),
            'selected_subject': self.request.GET.get('subject', '').strip(),
            'selected_teacher': self.request.GET.get('teacher', '').strip(),
            'selected_status': self.request.GET.get('status', 'all').strip(),
            'total_count': all_assignments.count(),
            'active_count': all_assignments.filter(is_active=True).count(),
            'inactive_count': all_assignments.filter(is_active=False).count(),
        })
        return context


class AssignmentCreateView(AdminRequiredMixin, CreateView):
    """
    Administrator view to create a new class-subject-teacher allocation.
    """
    model = ClassSubjectAssignment
    form_class = ClassSubjectAssignmentForm
    template_name = 'academics/assignment_form.html'
    success_url = reverse_lazy('academics:assignment_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"Teaching assignment for '{self.object.subject.name}' in '{self.object.classroom.display_name}' to {self.object.teacher.get_full_name() or self.object.teacher.username} created successfully."
        )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_edit'] = False
        return context


class AssignmentUpdateView(AdminRequiredMixin, UpdateView):
    """
    Administrator view to edit an existing teaching assignment (e.g. reallocate teacher or update status).
    """
    model = ClassSubjectAssignment
    form_class = ClassSubjectAssignmentForm
    template_name = 'academics/assignment_form.html'
    success_url = reverse_lazy('academics:assignment_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"Teaching assignment for '{self.object.subject.name}' in '{self.object.classroom.display_name}' updated successfully."
        )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_edit'] = True
        context['assignment'] = self.object
        return context


class AssignmentDeleteView(AdminRequiredMixin, View):
    """
    Administrator view to delete/unassign a teaching allocation.
    """
    def post(self, request, pk):
        assignment = get_object_or_404(ClassSubjectAssignment, pk=pk)
        info = str(assignment)
        assignment.delete()
        messages.success(request, f"Successfully removed teaching assignment: {info}")
        next_url = request.POST.get('next')
        if next_url:
            return redirect(next_url)
        return redirect('academics:assignment_list')
