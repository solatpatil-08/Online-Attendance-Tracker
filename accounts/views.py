from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView, FormView, View
from django.urls import reverse_lazy

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
        return reverse_lazy('dashboard:index')


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


# ==============================================================================
# Administrator-Only Management Views
# ==============================================================================

class TeacherListView(AdminRequiredMixin, ListView):
    """
    Administrator view for listing all registered faculty teachers.
    """
    model = User
    template_name = 'accounts/teacher_list.html'
    context_object_name = 'teachers'

    def get_queryset(self):
        return User.objects.filter(role=User.Role.TEACHER).select_related('teacher_profile').order_by('last_name', 'first_name')


class TeacherCreateView(AdminRequiredMixin, FormView):
    """
    Administrator view for onboarding a new faculty teacher.
    """
    form_class = TeacherCreationForm
    template_name = 'accounts/teacher_form.html'
    success_url = reverse_lazy('accounts:teacher_list')

    def form_valid(self, form):
        teacher = form.save()
        messages.success(
            self.request,
            f"Teacher account for '{teacher.get_full_name()}' ({teacher.username}) created successfully."
        )
        return super().form_valid(form)


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
        return redirect('accounts:teacher_list')
