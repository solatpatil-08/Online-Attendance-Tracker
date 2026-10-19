from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView, FormView, View
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import UserLoginForm, UserProfileForm, TeacherProfileForm, TeacherCreationForm
from .models import User, TeacherProfile
from .permissions import AdminRequiredMixin, admin_required


class UserLoginView(LoginView):
    """
    Handles user authentication with username/email support and remember-me session management.
    """
    form_class = UserLoginForm
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True

    def form_valid(self, form):
        # Enforce secure remember-me session duration
        remember_me = form.cleaned_data.get('remember_me')
        if remember_me:
            # 14 days (1,209,600 seconds)
            self.request.session.set_expiry(1209600)
        else:
            # Expires when browser closes
            self.request.session.set_expiry(0)

        user = form.get_user()
        messages.success(self.request, f"Welcome back, {user.get_full_name() or user.username}!")
        return super().form_valid(form)

    def get_success_url(self):
        return self.get_redirect_url() or reverse_lazy('dashboard:index')



class UserLogoutView(LogoutView):
    """
    Secure POST-only logout handler following Django CSRF guidelines.
    """
    next_page = reverse_lazy('accounts:login')

    def post(self, request, *args, **kwargs):
        messages.info(request, "You have been securely signed out.")
        return super().post(request, *args, **kwargs)


@login_required
def profile_view(request):
    """
    Displays and allows editing of current user profile information.
    Prevents unauthorized privilege escalation.
    """
    user = request.user
    teacher_profile = None

    if user.is_teacher_user:
        teacher_profile, _ = TeacherProfile.objects.get_or_create(
            user=user,
            defaults={'employee_id': f"EMP-{user.id:04d}"}
        )

    if request.method == 'POST':
        user_form = UserProfileForm(request.POST, request.FILES, instance=user)
        teacher_form = TeacherProfileForm(request.POST, instance=teacher_profile) if teacher_profile else None

        if user_form.is_valid() and (teacher_form is None or teacher_form.is_valid()):
            user_form.save()
            if teacher_form:
                teacher_form.save()
            messages.success(request, "Your profile has been updated successfully.")
            return redirect('accounts:profile')
    else:
        user_form = UserProfileForm(instance=user)
        teacher_form = TeacherProfileForm(instance=teacher_profile) if teacher_profile else None

    context = {
        'user_form': user_form,
        'teacher_form': teacher_form,
        'teacher_profile': teacher_profile,
    }
    return render(request, 'accounts/profile.html', context)


from django.db.models import Q, Count
from academics.models import Classroom, Subject, ClassSubjectAssignment
from .forms import (
    UserLoginForm, UserProfileForm, TeacherProfileForm,
    TeacherCreationForm, TeacherAdminEditForm
)
from academics.forms import ClassSubjectAssignmentForm


# ==============================================================================
# Administrator-Only Management Views
# ==============================================================================

class TeacherListView(AdminRequiredMixin, ListView):
    """
    Administrator view for listing all registered faculty teachers.
    Supports real-time search, department filtering, status toggling, and pagination.
    """
    model = User
    template_name = 'accounts/teacher_list.html'
    context_object_name = 'teachers'
    paginate_by = 10

    def get_queryset(self):
        qs = User.objects.filter(role=User.Role.TEACHER).select_related('teacher_profile')

        # 1. Search query (first name, last name, username, email, employee ID)
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(username__icontains=q) |
                Q(email__icontains=q) |
                Q(teacher_profile__employee_id__icontains=q)
            )

        # 2. Department filter
        dept = self.request.GET.get('department', '').strip()
        if dept:
            qs = qs.filter(teacher_profile__department__iexact=dept)

        # 3. Status filter ('active', 'inactive', 'all')
        status = self.request.GET.get('status', 'all').strip()
        if status == 'active':
            qs = qs.filter(is_active=True)
        elif status == 'inactive':
            qs = qs.filter(is_active=False)

        return qs.order_by('last_name', 'first_name', 'username')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_teachers = User.objects.filter(role=User.Role.TEACHER)
        
        # Distinct departments for filter dropdown
        departments = TeacherProfile.objects.exclude(
            department=''
        ).values_list('department', flat=True).distinct().order_by('department')

        # Preserve query parameters across pagination
        params = self.request.GET.copy()
        params.pop('page', None)
        context['query_string'] = params.urlencode()

        context.update({
            'search_query': self.request.GET.get('q', '').strip(),
            'selected_department': self.request.GET.get('department', '').strip(),
            'selected_status': self.request.GET.get('status', 'all').strip(),
            'departments': departments,
            'total_count': all_teachers.count(),
            'active_count': all_teachers.filter(is_active=True).count(),
            'inactive_count': all_teachers.filter(is_active=False).count(),
        })
        return context


class TeacherCreateView(AdminRequiredMixin, FormView):
    """
    Administrator view for onboarding a new faculty teacher.
    Securely hashes passwords using Django's authentication system.
    """
    form_class = TeacherCreationForm
    template_name = 'accounts/teacher_form.html'
    success_url = reverse_lazy('accounts:teacher_list')

    def form_valid(self, form):
        teacher = form.save()
        messages.success(
            self.request,
            f"Teacher account for '{teacher.get_full_name() or teacher.username}' ({teacher.username}) created successfully."
        )
        return redirect('accounts:teacher_detail', pk=teacher.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_edit'] = False
        return context


class TeacherDetailView(AdminRequiredMixin, View):
    """
    Administrator view showing comprehensive details of a teacher:
    - Profile information (Employee ID, Department, Qualification, Contact).
    - Classes supervised as Class Teacher.
    - Assigned classes and subjects (ClassSubjectAssignment).
    - Quick action form to assign a new class and subject.
    """
    template_name = 'accounts/teacher_detail.html'

    def get(self, request, pk):
        teacher = get_object_or_404(User, pk=pk, role=User.Role.TEACHER)
        supervised_classes = Classroom.objects.filter(class_teacher=teacher).select_related('academic_year')
        assignments = ClassSubjectAssignment.objects.filter(teacher=teacher).select_related(
            'classroom', 'classroom__academic_year', 'subject'
        ).order_by('classroom__name', 'classroom__section', 'subject__name')

        assign_form = ClassSubjectAssignmentForm(teacher_fixed=teacher)

        context = {
            'teacher': teacher,
            'profile': getattr(teacher, 'teacher_profile', None),
            'supervised_classes': supervised_classes,
            'assignments': assignments,
            'assign_form': assign_form,
        }
        return render(request, self.template_name, context)


class TeacherUpdateView(AdminRequiredMixin, View):
    """
    Administrator view for editing an existing teacher's profile and credentials.
    """
    template_name = 'accounts/teacher_form.html'

    def get(self, request, pk):
        teacher = get_object_or_404(User, pk=pk, role=User.Role.TEACHER)
        form = TeacherAdminEditForm(teacher=teacher)
        context = {
            'form': form,
            'teacher': teacher,
            'is_edit': True,
        }
        return render(request, self.template_name, context)

    def post(self, request, pk):
        teacher = get_object_or_404(User, pk=pk, role=User.Role.TEACHER)
        form = TeacherAdminEditForm(request.POST, teacher=teacher)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f"Profile for teacher '{teacher.get_full_name() or teacher.username}' updated successfully."
            )
            return redirect('accounts:teacher_detail', pk=teacher.pk)

        context = {
            'form': form,
            'teacher': teacher,
            'is_edit': True,
        }
        return render(request, self.template_name, context)


class TeacherToggleStatusView(AdminRequiredMixin, View):
    """
    Administrator view to activate/deactivate a teacher user.
    """
    def post(self, request, pk, *args, **kwargs):
        teacher = get_object_or_404(User, pk=pk, role=User.Role.TEACHER)
        # Prevent disabling oneself if ever applicable
        if teacher == request.user:
            messages.error(request, "You cannot modify your own administrative account status.")
            return redirect('accounts:teacher_list')

        teacher.is_active = not teacher.is_active
        teacher.save(update_fields=['is_active'])
        status_label = "activated" if teacher.is_active else "deactivated"
        messages.info(request, f"Teacher account '{teacher.username}' has been {status_label}.")

        next_url = request.POST.get('next')
        if next_url and url_has_allowed_host_and_scheme(url=next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        return redirect('accounts:teacher_detail', pk=teacher.pk)


class TeacherAssignClassSubjectView(AdminRequiredMixin, View):
    """
    Administrator action to assign a classroom and subject directly to a teacher.
    Validates relationship and prevents duplicate assignments.
    """
    def post(self, request, pk):
        teacher = get_object_or_404(User, pk=pk, role=User.Role.TEACHER)
        if not teacher.is_active:
            messages.error(request, f"Cannot assign classes or subjects to inactive teacher '{teacher.get_full_name() or teacher.username}'.")
            return redirect('accounts:teacher_detail', pk=teacher.pk)

        classroom_id = request.POST.get('classroom')
        subject_id = request.POST.get('subject')

        if not classroom_id or not subject_id:
            messages.error(request, "Please select both a classroom and a subject to assign.")
            return redirect('accounts:teacher_detail', pk=teacher.pk)

        classroom = get_object_or_404(Classroom, pk=classroom_id)
        subject = get_object_or_404(Subject, pk=subject_id)

        if not classroom.is_active:
            messages.error(request, f"Cannot assign inactive classroom '{classroom.display_name}'.")
            return redirect('accounts:teacher_detail', pk=teacher.pk)

        if not subject.is_active:
            messages.error(request, f"Cannot assign inactive subject '{subject.name}'.")
            return redirect('accounts:teacher_detail', pk=teacher.pk)

        # Check existing assignment
        existing = ClassSubjectAssignment.objects.filter(classroom=classroom, subject=subject).first()
        if existing:
            if existing.teacher == teacher:
                messages.warning(
                    request,
                    f"'{subject.name}' in '{classroom.display_name}' is already assigned to {teacher.get_full_name() or teacher.username}."
                )
            else:
                existing_teacher = existing.teacher.get_full_name() or existing.teacher.username
                messages.error(
                    request,
                    f"'{subject.name}' in '{classroom.display_name}' is currently assigned to {existing_teacher}. Unassign them first or reallocate through class management."
                )
            return redirect('accounts:teacher_detail', pk=teacher.pk)

        ClassSubjectAssignment.objects.create(
            classroom=classroom,
            subject=subject,
            teacher=teacher,
            is_active=True
        )
        messages.success(
            request,
            f"Successfully assigned {subject.name} ({subject.code}) in {classroom.display_name} to {teacher.get_full_name() or teacher.username}."
        )
        return redirect('accounts:teacher_detail', pk=teacher.pk)


class TeacherRemoveAssignmentView(AdminRequiredMixin, View):
    """
    Administrator action to remove a class-subject allocation from a teacher.
    """
    def post(self, request, pk, assignment_id):
        teacher = get_object_or_404(User, pk=pk, role=User.Role.TEACHER)
        assignment = get_object_or_404(ClassSubjectAssignment, pk=assignment_id, teacher=teacher)
        class_name = assignment.classroom.display_name
        subj_name = assignment.subject.name
        assignment.delete()
        messages.success(
            request,
            f"Removed assignment of {subj_name} for {class_name} from {teacher.get_full_name() or teacher.username}."
        )
        return redirect('accounts:teacher_detail', pk=teacher.pk)

