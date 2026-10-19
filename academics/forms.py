from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from .models import Classroom, Subject, ClassSubjectAssignment, AcademicYear
from accounts.models import User


class ClassroomForm(forms.ModelForm):
    """
    Form for creating and editing academic classrooms (grades and sections).
    Prevents duplicate class name and section combinations within the same academic year.
    Limits teacher selection strictly to active users with the TEACHER role.
    """
    class Meta:
        model = Classroom
        fields = ['name', 'section', 'academic_year', 'class_teacher', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Grade 10, Class 5, Year 11',
            }),
            'section': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. A, B, Green, Morning',
            }),
            'academic_year': forms.Select(attrs={
                'class': 'form-select',
            }),
            'class_teacher': forms.Select(attrs={
                'class': 'form-select',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Order academic years by start_date descending
        self.fields['academic_year'].queryset = AcademicYear.objects.all().order_by('-is_current', '-start_date')
        
        # Restrict class_teacher choices to active faculty with TEACHER role
        teacher_qs = User.objects.filter(
            role=User.Role.TEACHER,
            is_active=True
        ).order_by('last_name', 'first_name')
        
        # If editing and current teacher was assigned (even if now inactive), include them
        if self.instance and self.instance.pk and self.instance.class_teacher:
            teacher_qs = User.objects.filter(
                Q(role=User.Role.TEACHER, is_active=True) | Q(pk=self.instance.class_teacher_id)
            ).order_by('last_name', 'first_name')
            
        self.fields['class_teacher'].queryset = teacher_qs
        self.fields['class_teacher'].empty_label = "--- Select Supervising Teacher (Optional) ---"

        # If creating new, default academic year to currently active year if available
        if not self.instance.pk and not self.initial.get('academic_year'):
            current_year = AcademicYear.objects.filter(is_current=True).first()
            if current_year:
                self.fields['academic_year'].initial = current_year.pk

    def clean_name(self):
        return self.cleaned_data.get('name', '').strip()

    def clean_section(self):
        return self.cleaned_data.get('section', '').strip().upper()

    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get('name')
        section = cleaned_data.get('section')
        academic_year = cleaned_data.get('academic_year')
        class_teacher = cleaned_data.get('class_teacher')

        if name and section and academic_year:
            # Check duplicate class name + section in same academic year
            dup_query = Classroom.objects.filter(
                name__iexact=name,
                section__iexact=section,
                academic_year=academic_year
            )
            if self.instance and self.instance.pk:
                dup_query = dup_query.exclude(pk=self.instance.pk)

            if dup_query.exists():
                raise ValidationError({
                    'section': f"A classroom '{name} - {section}' already exists for the academic year '{academic_year.name}'. Please choose a distinct section or grade."
                })

        if class_teacher:
            if class_teacher.role != User.Role.TEACHER:
                raise ValidationError({
                    'class_teacher': "Only faculty members with the 'TEACHER' role can be assigned as class supervisor."
                })
            if not class_teacher.is_active:
                raise ValidationError({
                    'class_teacher': "Cannot assign an inactive teacher as class teacher."
                })

        return cleaned_data


class SubjectForm(forms.ModelForm):
    """
    Form for defining and updating institutional academic subjects.
    Prevents duplicate subject codes.
    """
    class Meta:
        model = Subject
        fields = ['name', 'code', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Mathematics, Advanced Physics, English Literature',
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. MATH-101, PHY-201',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional course syllabus, curriculum overview, or department notes...',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }

    def clean_name(self):
        return self.cleaned_data.get('name', '').strip()

    def clean_code(self):
        code = self.cleaned_data.get('code', '').strip().upper()
        dup_query = Subject.objects.filter(code__iexact=code)
        if self.instance and self.instance.pk:
            dup_query = dup_query.exclude(pk=self.instance.pk)

        if dup_query.exists():
            raise ValidationError(f"A subject with code '{code}' already exists. Please provide a unique subject code.")
        return code


class ClassSubjectAssignmentForm(forms.ModelForm):
    """
    Form for allocating a Subject and Teacher to a specific Classroom.
    Validates that:
    - Classroom, Subject, and Teacher are active.
    - Teacher possesses the TEACHER role.
    - Prevents duplicate allocation of the same subject to the same classroom.
    """
    class Meta:
        model = ClassSubjectAssignment
        fields = ['classroom', 'subject', 'teacher', 'is_active']
        widgets = {
            'classroom': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'teacher': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        classroom_fixed = kwargs.pop('classroom_fixed', None)
        teacher_fixed = kwargs.pop('teacher_fixed', None)
        subject_fixed = kwargs.pop('subject_fixed', None)
        super().__init__(*args, **kwargs)

        # Active classrooms only
        cr_qs = Classroom.objects.filter(is_active=True).select_related('academic_year').order_by('name', 'section')
        if self.instance and self.instance.pk and self.instance.classroom:
            cr_qs = Classroom.objects.filter(
                Q(is_active=True) | Q(pk=self.instance.classroom_id)
            ).select_related('academic_year').order_by('name', 'section')
        self.fields['classroom'].queryset = cr_qs

        # Active subjects only
        subj_qs = Subject.objects.filter(is_active=True).order_by('name')
        if self.instance and self.instance.pk and self.instance.subject:
            subj_qs = Subject.objects.filter(
                Q(is_active=True) | Q(pk=self.instance.subject_id)
            ).order_by('name')
        self.fields['subject'].queryset = subj_qs

        # Active teachers only
        teacher_qs = User.objects.filter(role=User.Role.TEACHER, is_active=True).order_by('last_name', 'first_name')
        if self.instance and self.instance.pk and self.instance.teacher:
            teacher_qs = User.objects.filter(
                Q(role=User.Role.TEACHER, is_active=True) | Q(pk=self.instance.teacher_id)
            ).order_by('last_name', 'first_name')
        self.fields['teacher'].queryset = teacher_qs

        # Pre-set fixed fields if requested (e.g. assigning from class detail or teacher detail)
        if classroom_fixed:
            self.fields['classroom'].initial = classroom_fixed
        if teacher_fixed:
            self.fields['teacher'].initial = teacher_fixed
        if subject_fixed:
            self.fields['subject'].initial = subject_fixed

    def clean(self):
        cleaned_data = super().clean()
        classroom = cleaned_data.get('classroom')
        subject = cleaned_data.get('subject')
        teacher = cleaned_data.get('teacher')

        if classroom and not classroom.is_active:
            raise ValidationError({'classroom': "Cannot assign subjects to an inactive classroom."})

        if subject and not subject.is_active:
            raise ValidationError({'subject': "Cannot assign an inactive subject."})

        if teacher:
            if teacher.role != User.Role.TEACHER:
                raise ValidationError({'teacher': "Only users with the 'TEACHER' role can be assigned."})
            if not teacher.is_active:
                raise ValidationError({'teacher': "Cannot assign an inactive teacher."})

        if classroom and subject:
            dup_query = ClassSubjectAssignment.objects.filter(
                classroom=classroom,
                subject=subject
            )
            if self.instance and self.instance.pk:
                dup_query = dup_query.exclude(pk=self.instance.pk)

            if dup_query.exists():
                existing = dup_query.first()
                existing_teacher = existing.teacher.get_full_name() or existing.teacher.username
                raise ValidationError({
                    'subject': f"'{subject.name}' is already assigned to '{classroom.display_name}' (Assigned to {existing_teacher}). Update the existing assignment or select another subject."
                })

        return cleaned_data
