import datetime
from django import forms
from django.utils import timezone
from academics.models import Classroom
from .models import Student


class StudentForm(forms.ModelForm):
    """
    Form for enrolling and updating student records.
    Provides rigorous validation for unique IDs, valid active classroom assignments,
    duplicate roll numbers, valid date sequences, and responsive Bootstrap styling.
    """

    class Meta:
        model = Student
        fields = [
            'student_id',
            'first_name',
            'last_name',
            'classroom',
            'roll_number',
            'gender',
            'date_of_birth',
            'enrollment_date',
            'email',
            'phone_number',
            'guardian_name',
            'guardian_phone',
            'is_active',
        ]
        widgets = {
            'student_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. STU-2026-001',
                'autocomplete': 'off',
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'First Name',
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Last / Family Name',
            }),
            'classroom': forms.Select(attrs={
                'class': 'form-select',
            }),
            'roll_number': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. 1, 2, 15',
                'min': '1',
            }),
            'gender': forms.Select(attrs={
                'class': 'form-select',
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'enrollment_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'student@school.edu',
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+1 (555) 000-0000',
            }),
            'guardian_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Full Name of Parent / Guardian',
            }),
            'guardian_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+1 (555) 000-0000',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'role': 'switch',
            }),
        }
        labels = {
            'student_id': 'Student ID / Enrollment Number',
            'first_name': 'First Name',
            'last_name': 'Last Name',
            'classroom': 'Class & Section',
            'roll_number': 'Roll Number',
            'gender': 'Gender',
            'date_of_birth': 'Date of Birth',
            'enrollment_date': 'Enrollment Date',
            'email': 'Email Address',
            'phone_number': 'Contact Phone Number',
            'guardian_name': 'Parent / Guardian Name',
            'guardian_phone': 'Parent / Guardian Phone',
            'is_active': 'Active Enrollment Status',
        }
        help_texts = {
            'student_id': 'Institutional unique identifier. Cannot be duplicated.',
            'classroom': 'Select target grade and section.',
            'roll_number': 'Sequential roll number unique within the classroom (optional).',
            'is_active': 'Uncheck to deactivate without deleting historical records.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Load classrooms with active status indicator in labels
        self.fields['classroom'].queryset = Classroom.objects.select_related('academic_year').order_by('-is_active', 'name', 'section')
        self.fields['classroom'].label_from_instance = lambda obj: f"{obj.display_name} ({obj.academic_year.name}){' [Inactive]' if not obj.is_active else ''}"

        # Default enrollment_date to today if not set
        if not self.initial.get('enrollment_date') and not (self.instance and self.instance.pk):
            self.initial['enrollment_date'] = timezone.localdate()

    def clean_student_id(self):
        student_id = self.cleaned_data.get('student_id', '').strip()
        if not student_id:
            raise forms.ValidationError("Student ID is required.")

        qs = Student.objects.filter(student_id__iexact=student_id)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise forms.ValidationError(
                f"A student with enrollment ID '{student_id}' already exists. Student IDs must be unique."
            )
        return student_id

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            email = email.strip()
            if not email:
                return None
        return email

    def clean(self):
        cleaned_data = super().clean()
        classroom = cleaned_data.get('classroom')
        is_active = cleaned_data.get('is_active', True)
        roll_number = cleaned_data.get('roll_number')
        date_of_birth = cleaned_data.get('date_of_birth')
        enrollment_date = cleaned_data.get('enrollment_date')
        today = timezone.localdate()

        # Inactive classroom validation
        if classroom and not classroom.is_active and is_active:
            self.add_error(
                'classroom',
                "Cannot assign an active student to an inactive classroom. Please activate the class first or assign an active classroom."
            )

        # Roll number uniqueness per classroom
        if classroom and roll_number is not None:
            roll_qs = Student.objects.filter(classroom=classroom, roll_number=roll_number)
            if self.instance and self.instance.pk:
                roll_qs = roll_qs.exclude(pk=self.instance.pk)
            if roll_qs.exists():
                existing = roll_qs.first()
                self.add_error(
                    'roll_number',
                    f"Roll number {roll_number} is already assigned to {existing.full_name} in {classroom.display_name}."
                )

        # Date of birth validation
        if date_of_birth:
            if date_of_birth >= today:
                self.add_error(
                    'date_of_birth',
                    "Date of birth must be in the past."
                )

        # Enrollment date validation
        if date_of_birth and enrollment_date:
            if enrollment_date <= date_of_birth:
                self.add_error(
                    'enrollment_date',
                    "Enrollment date must be after the student's date of birth."
                )

        return cleaned_data
