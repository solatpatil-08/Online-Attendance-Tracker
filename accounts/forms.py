from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from .models import User, TeacherProfile


class UserLoginForm(AuthenticationForm):
    """
    Secure login form supporting either username or email.
    Provides generic authentication error messages and optional remember-me functionality.
    """
    username = forms.CharField(
        label="Username or Email",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your username or email address',
            'autofocus': True,
            'id': 'loginUsername',
            'autocomplete': 'username',
        })
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password',
            'id': 'loginPassword',
            'autocomplete': 'current-password',
        })
    )
    remember_me = forms.BooleanField(
        required=False,
        initial=False,
        label="Remember this device for 2 weeks",
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'rememberMeCheck',
        })
    )

    error_messages = {
        'invalid_login': (
            "Invalid credentials. Please enter a correct username/email and password. "
            "Note that password is case-sensitive."
        ),
        'inactive': "This account is inactive. Please contact the system administrator.",
    }

    def clean(self):
        username_or_email = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username_or_email and password:
            # If input is an email, resolve to associated username
            if '@' in username_or_email:
                user_match = User.objects.filter(email__iexact=username_or_email.strip()).first()
                if user_match:
                    username_or_email = user_match.username

            self.user_cache = authenticate(
                self.request,
                username=username_or_email,
                password=password
            )

            if self.user_cache is None:
                raise self.get_invalid_login_error()
            else:
                self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data


class UserProfileForm(forms.ModelForm):
    """
    Form for updating basic user information.
    Prevents unauthorized modification of sensitive flags or roles.
    """
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'profile_picture']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-control'}),
        }


class TeacherProfileForm(forms.ModelForm):
    """
    Form for updating teacher-specific details.
    """
    class Meta:
        model = TeacherProfile
        fields = ['department', 'qualification']
        widgets = {
            'department': forms.TextInput(attrs={'class': 'form-control'}),
            'qualification': forms.TextInput(attrs={'class': 'form-control'}),
        }


class TeacherCreationForm(forms.Form):
    """
    Administrative form for provisioning new teacher accounts.
    Enforces security, password strength, and unique identifiers.
    """
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. jdoe'})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'teacher@school.edu'})
    )
    first_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    employee_id = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. EMP-2026-001'})
    )
    department = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Mathematics'})
    )
    qualification = forms.CharField(
        max_length=120,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. M.Sc, B.Ed'})
    )
    password = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    confirm_password = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("A user with this username already exists.")
        return username

    def clean_email(self):
        email = self.cleaned_data['email'].strip()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("A user with this email address already exists.")
        return email

    def clean_employee_id(self):
        emp_id = self.cleaned_data['employee_id'].strip()
        if TeacherProfile.objects.filter(employee_id__iexact=emp_id).exists():
            raise ValidationError("A teacher with this employee ID already exists.")
        return emp_id

    def clean(self):
        cleaned_data = super().clean()
        pwd = cleaned_data.get('password')
        cpwd = cleaned_data.get('confirm_password')

        if pwd and cpwd and pwd != cpwd:
            raise ValidationError({'confirm_password': "Passwords do not match."})
        return cleaned_data

    def save(self):
        cd = self.cleaned_data
        user = User.objects.create_user(
            username=cd['username'],
            email=cd['email'],
            password=cd['password'],
            first_name=cd['first_name'],
            last_name=cd['last_name'],
            role=User.Role.TEACHER,
            is_staff=True,
        )
        TeacherProfile.objects.create(
            user=user,
            employee_id=cd['employee_id'],
            department=cd.get('department', ''),
            qualification=cd.get('qualification', '')
        )
        user.sync_role_group()
        return user
