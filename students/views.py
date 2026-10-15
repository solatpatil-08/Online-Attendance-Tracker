from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.core.exceptions import PermissionDenied
from django.views.generic import ListView, DetailView, CreateView, UpdateView, View
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.db.models import Q

from .models import Student
from .forms import StudentForm
from academics.models import Classroom
from attendance.models import Attendance
from accounts.permissions import AdminRequiredMixin, check_teacher_class_authorization


@method_decorator(login_required, name='dispatch')
class StudentListView(ListView):
    """
    Responsive student directory with pagination, search, and multidimensional filters:
    - Administrators: Full institutional enrollment roster across all classrooms.
    - Teachers: Only students enrolled in classrooms assigned to this teacher.
    - Search: Student ID or full name.
    - Filters: Classroom, Section, and Active Status.
    - Preserves query parameters across pagination links.
    """
    model = Student
    template_name = 'students/student_list.html'
    context_object_name = 'students'
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user
        if user.is_administrator:
            qs = Student.objects.all().select_related('classroom', 'classroom__academic_year')
        else:
            # Restrict strictly to classrooms where teacher has active assignments or direct supervision
            qs = Student.objects.filter(
                Q(classroom__subject_assignments__teacher=user, classroom__subject_assignments__is_active=True) |
                Q(classroom__class_teacher=user)
            ).distinct().select_related('classroom', 'classroom__academic_year')

        # 1. Search Query (Student ID, First Name, Last Name)
        search_query = self.request.GET.get('q', '').strip()
        if search_query:
            qs = qs.filter(
                Q(student_id__icontains=search_query) |
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query)
            )

        # 2. Classroom Filter
        classroom_id = self.request.GET.get('classroom', '').strip()
        if classroom_id:
            qs = qs.filter(classroom_id=classroom_id)

        # 3. Section Filter
        section = self.request.GET.get('section', '').strip()
        if section:
            qs = qs.filter(classroom__section__iexact=section)

        # 4. Status Filter ('active', 'inactive', 'all')
        status = self.request.GET.get('status', 'active').strip()
        if status == 'active':
            qs = qs.filter(is_active=True)
        elif status == 'inactive':
            qs = qs.filter(is_active=False)
        # if 'all', do not filter by is_active

        return qs.order_by('classroom__name', 'classroom__section', 'roll_number', 'last_name', 'first_name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Get permitted classrooms for filter dropdown
        if user.is_administrator:
            classrooms = Classroom.objects.filter(is_active=True).select_related('academic_year').order_by('name', 'section')
            sections = Classroom.objects.filter(is_active=True).values_list('section', flat=True).distinct().order_by('section')
        else:
            classrooms = Classroom.objects.filter(
                Q(subject_assignments__teacher=user, subject_assignments__is_active=True) |
                Q(class_teacher=user),
                is_active=True
            ).distinct().select_related('academic_year').order_by('name', 'section')
            sections = classrooms.values_list('section', flat=True).distinct().order_by('section')

        # Preserve query parameters across pagination
        params = self.request.GET.copy()
        params.pop('page', None)
        context['query_string'] = params.urlencode()

        context.update({
            'classrooms': classrooms,
            'sections': sections,
            'search_query': self.request.GET.get('q', '').strip(),
            'selected_classroom': self.request.GET.get('classroom', '').strip(),
            'selected_section': self.request.GET.get('section', '').strip(),
            'selected_status': self.request.GET.get('status', 'active').strip(),
            'total_count': self.get_queryset().count(),
        })
        return context


@method_decorator(login_required, name='dispatch')
class StudentDetailView(DetailView):
    """
    Detailed profile view of a student.
    Enforces authorization:
    - Administrators: Full access.
    - Teachers: Only students belonging to their permitted classes (HTTP 403 on unauthorized).
    Calculates exact attendance statistics and history from actual database records.
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.object

        # Retrieve actual attendance records
        records = student.attendance_records.select_related(
            'session', 'classroom', 'subject', 'recorded_by'
        ).order_by('-date', '-created_at')

        total_sessions = records.count()
        present_count = records.filter(status=Attendance.Status.PRESENT).count()
        late_count = records.filter(status=Attendance.Status.LATE).count()
        absent_count = records.filter(status=Attendance.Status.ABSENT).count()
        excused_count = records.filter(status=Attendance.Status.EXCUSED).count()

        attended_count = present_count + late_count
        attendance_percentage = round((attended_count / total_sessions) * 100, 1) if total_sessions > 0 else None

        context.update({
            'attendance_summary': {
                'total_sessions': total_sessions,
                'present_count': present_count,
                'late_count': late_count,
                'absent_count': absent_count,
                'excused_count': excused_count,
                'attended_count': attended_count,
                'percentage': attendance_percentage,
            },
            'recent_records': records[:25],
            'has_attendance_history': total_sessions > 0,
        })
        return context


class StudentCreateView(AdminRequiredMixin, CreateView):
    """
    Administrator-only view for enrolling new students.
    Validates form data and prevents duplicate student IDs or invalid classroom assignments.
    """
    model = Student
    form_class = StudentForm
    template_name = 'students/student_form.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"Student '{self.object.full_name}' (ID: {self.object.student_id}) has been successfully enrolled."
        )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_edit'] = False
        return context


class StudentUpdateView(AdminRequiredMixin, UpdateView):
    """
    Administrator-only view for updating existing student details.
    Displays field-specific validation errors and preserves academic integrity.
    """
    model = Student
    form_class = StudentForm
    template_name = 'students/student_form.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"Student '{self.object.full_name}' details have been updated successfully."
        )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_edit'] = True
        context['student'] = self.object
        return context


class StudentDeleteView(AdminRequiredMixin, View):
    """
    Administrator-only safe student deletion view.
    Enforces safe behavior for historical records:
    - If student has attendance history, permanent deletion is BLOCKED to prevent data loss.
      The administrator is prompted to deactivate the student instead.
    - If student has no attendance history, explicit confirmation is required before deletion.
    """
    template_name = 'students/student_confirm_delete.html'

    def get(self, request, pk):
        student = get_object_or_404(Student, pk=pk)
        records_count = student.attendance_records.count()
        context = {
            'student': student,
            'records_count': records_count,
            'has_attendance_history': records_count > 0,
        }
        return render(request, self.template_name, context)

    def post(self, request, pk):
        student = get_object_or_404(Student, pk=pk)
        records_count = student.attendance_records.count()

        if records_count > 0:
            messages.error(
                request,
                f"Cannot delete '{student.full_name}' because {records_count} attendance records exist. "
                "Deleting would destroy historical attendance audit data. Please deactivate the student instead."
            )
            return redirect('students:student_detail', pk=student.pk)

        student_name = student.full_name
        student_id = student.student_id
        student.delete()
        messages.success(
            request,
            f"Student record for '{student_name}' ({student_id}) has been permanently deleted."
        )
        return redirect('students:student_list')


class StudentToggleStatusView(AdminRequiredMixin, View):
    """
    Administrator-only view to activate or deactivate a student record.
    Preserves all historical records while removing deactivated students from active rosters.
    """
    def post(self, request, pk):
        student = get_object_or_404(Student, pk=pk)
        if student.is_active:
            student.is_active = False
            student.save(update_fields=['is_active', 'updated_at'])
            messages.warning(
                request,
                f"Student '{student.full_name}' has been deactivated. Historical records remain intact, but the student will no longer appear on active rosters."
            )
        else:
            if not student.classroom.is_active:
                messages.error(
                    request,
                    f"Cannot activate student '{student.full_name}' because their assigned classroom ({student.classroom.display_name}) is inactive. Please edit student and assign an active classroom first."
                )
                return redirect('students:student_detail', pk=student.pk)

            student.is_active = True
            student.save(update_fields=['is_active', 'updated_at'])
            messages.success(
                request,
                f"Student '{student.full_name}' has been successfully reactivated."
            )

        # Redirect to next or detail
        next_url = request.POST.get('next')
        if next_url:
            return redirect(next_url)
        return redirect('students:student_detail', pk=student.pk)
