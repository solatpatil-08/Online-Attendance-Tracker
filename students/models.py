from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError


class Student(models.Model):
    """
    Represents an enrolled student in the Online Attendance Tracking System.
    Tracks academic identity, enrollment, assigned classroom, and personal contact info.
    """
    class Gender(models.TextChoices):
        MALE = 'MALE', 'Male'
        FEMALE = 'FEMALE', 'Female'
        OTHER = 'OTHER', 'Other'

    student_id = models.CharField(
        max_length=30,
        unique=True,
        db_index=True,
        help_text="Unique student registration or enrollment number (e.g. 'STU-2026-001')."
    )
    first_name = models.CharField(max_length=50, help_text="Student's first name.")
    last_name = models.CharField(max_length=50, help_text="Student's surname or last name.")
    email = models.EmailField(
        blank=True,
        null=True,
        help_text="Optional student contact email address."
    )
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        help_text="Contact telephone number for the student or guardian."
    )
    gender = models.CharField(
        max_length=10,
        choices=Gender.choices,
        blank=True,
        help_text="Student's biological or declared gender."
    )
    date_of_birth = models.DateField(
        blank=True,
        null=True,
        help_text="Student date of birth."
    )
    classroom = models.ForeignKey(
        'academics.Classroom',
        on_delete=models.PROTECT,
        related_name='students',
        help_text="Currently assigned class and section."
    )
    roll_number = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Sequential roll number within the assigned classroom."
    )
    enrollment_date = models.DateField(
        default=timezone.now,
        help_text="Date on which the student was officially enrolled."
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Designates whether the student is currently enrolled and active."
    )
    guardian_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Name of parent or guardian."
    )
    guardian_phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="Primary emergency/guardian phone number."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['classroom', 'roll_number', 'last_name', 'first_name']
        verbose_name = 'Student'
        verbose_name_plural = 'Students'
        constraints = [
            models.UniqueConstraint(
                fields=['classroom', 'roll_number'],
                condition=models.Q(roll_number__isnull=False),
                name='unique_classroom_roll_number'
            )
        ]
        indexes = [
            models.Index(fields=['student_id']),
            models.Index(fields=['classroom', 'is_active']),
            models.Index(fields=['last_name', 'first_name']),
        ]

    def clean(self):
        super().clean()
        today = timezone.localdate()

        if self.date_of_birth and self.date_of_birth >= today:
            raise ValidationError({
                'date_of_birth': "Date of birth must be in the past."
            })

        if self.date_of_birth and self.enrollment_date:
            if self.enrollment_date <= self.date_of_birth:
                raise ValidationError({
                    'enrollment_date': "Enrollment date must be after the student's date of birth."
                })

        if self.classroom_id:
            try:
                classroom = self.classroom
            except Exception:
                classroom = None
            if classroom and not classroom.is_active and self.is_active:
                raise ValidationError({
                    'classroom': "Cannot assign an active student to an inactive classroom."
                })

    def delete(self, *args, **kwargs):
        if self.attendance_records.exists():
            raise ValidationError(
                f"Cannot delete student '{self.full_name}' because attendance records exist for this student. Deactivate the student instead."
            )
        return super().delete(*args, **kwargs)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def get_full_name(self):
        return self.full_name

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('students:student_detail', kwargs={'pk': self.pk})

    def __str__(self):
        roll_str = f" [Roll #{self.roll_number}]" if self.roll_number else ""
        return f"{self.full_name} ({self.student_id}){roll_str} - {self.classroom.display_name}"
