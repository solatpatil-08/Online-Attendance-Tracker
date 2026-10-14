from django.db import models, transaction
from django.conf import settings
from django.core.exceptions import ValidationError


class AcademicYear(models.Model):
    """
    Represents an institutional academic cycle (e.g., 2026-2027).
    Supports a single active/current year flag with automated deactivation of prior years.
    """
    name = models.CharField(
        max_length=50,
        unique=True,
        help_text="Descriptive academic calendar name, e.g. '2026-2027'."
    )
    start_date = models.DateField(help_text="Commencement date of the academic session.")
    end_date = models.DateField(help_text="Concluding date of the academic session.")
    is_current = models.BooleanField(
        default=False,
        help_text="Mark this academic year as the currently active session."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']
        verbose_name = 'Academic Year'
        verbose_name_plural = 'Academic Years'
        indexes = [
            models.Index(fields=['is_current']),
            models.Index(fields=['name']),
        ]

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.end_date <= self.start_date:
            raise ValidationError({
                'end_date': "The academic year end date must be after the start date."
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        with transaction.atomic():
            if self.is_current:
                # Set all other academic years as non-current
                AcademicYear.objects.exclude(pk=self.pk).filter(is_current=True).update(is_current=False)
            super().save(*args, **kwargs)

    def __str__(self):
        status = " (Current)" if self.is_current else ""
        return f"{self.name}{status}"


class Classroom(models.Model):
    """
    Represents an academic grade/division or section (e.g., Grade 10 - Section A).
    """
    name = models.CharField(
        max_length=50,
        help_text="Grade level or standard name (e.g. 'Grade 10', 'Class 5')."
    )
    section = models.CharField(
        max_length=10,
        help_text="Section or division identifier (e.g. 'A', 'B', 'Morning')."
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name='classrooms',
        help_text="The academic session for this class."
    )
    class_teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supervised_classes',
        limit_choices_to={'role': 'TEACHER'},
        help_text="Primary faculty in charge of this classroom."
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Designates whether this classroom is currently active."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['academic_year', 'name', 'section']
        verbose_name = 'Class / Section'
        verbose_name_plural = 'Classes & Sections'
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'section', 'academic_year'],
                name='unique_class_section_academic_year'
            )
        ]
        indexes = [
            models.Index(fields=['name', 'section']),
            models.Index(fields=['is_active']),
        ]

    def clean(self):
        super().clean()
        if self.class_teacher and self.class_teacher.role != 'TEACHER':
            raise ValidationError({
                'class_teacher': "Assigned class teacher must possess the 'TEACHER' role."
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def display_name(self):
        return f"{self.name} - {self.section}"

    def __str__(self):
        return f"{self.name} - {self.section} ({self.academic_year.name})"


class Subject(models.Model):
    """
    Represents an academic subject/course taught across classes.
    """
    name = models.CharField(
        max_length=100,
        help_text="Subject title (e.g. 'Mathematics', 'Physics')."
    )
    code = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        help_text="Unique course code identifier (e.g. 'MATH-101')."
    )
    description = models.TextField(
        blank=True,
        help_text="Optional syllabus summary or course overview."
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Designates whether this subject is actively taught."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Subject'
        verbose_name_plural = 'Subjects'
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


class ClassSubjectAssignment(models.Model):
    """
    Associates a specific Classroom and Subject with an assigned Teacher.
    Prevents duplicate teaching allocations for the same class-subject combination.
    """
    classroom = models.ForeignKey(
        Classroom,
        on_delete=models.CASCADE,
        related_name='subject_assignments',
        help_text="Target class receiving instruction."
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='class_assignments',
        help_text="Subject being taught."
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='teaching_assignments',
        limit_choices_to={'role': 'TEACHER'},
        help_text="Teacher responsible for instruction and attendance taking."
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Designates whether this teaching allocation is currently active."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['classroom', 'subject']
        verbose_name = 'Class Subject Assignment'
        verbose_name_plural = 'Class Subject Assignments'
        constraints = [
            models.UniqueConstraint(
                fields=['classroom', 'subject'],
                name='unique_class_subject_assignment'
            )
        ]
        indexes = [
            models.Index(fields=['classroom', 'subject']),
            models.Index(fields=['teacher', 'is_active']),
        ]

    def clean(self):
        super().clean()
        if self.teacher and self.teacher.role != 'TEACHER':
            raise ValidationError({
                'teacher': "Only users with the 'TEACHER' role can be assigned as subject instructors."
            })
        if self.classroom and not self.classroom.is_active:
            raise ValidationError({
                'classroom': "Cannot assign subjects to an inactive classroom."
            })
        if self.subject and not self.subject.is_active:
            raise ValidationError({
                'subject': "Cannot assign an inactive subject."
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.classroom.display_name} - {self.subject.name} (Teacher: {self.teacher.get_full_name() or self.teacher.username})"
