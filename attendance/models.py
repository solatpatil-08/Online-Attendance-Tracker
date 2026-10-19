from django.db import models, transaction
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone


class AttendanceSession(models.Model):
    """
    Represents an attendance taking event for a given Classroom, Subject, and Date.
    Serves as the parent session grouping individual student attendance records.
    """
    classroom = models.ForeignKey(
        'academics.Classroom',
        on_delete=models.CASCADE,
        related_name='attendance_sessions',
        help_text="Classroom for which attendance is being registered."
    )
    subject = models.ForeignKey(
        'academics.Subject',
        on_delete=models.CASCADE,
        related_name='attendance_sessions',
        help_text="Academic subject session being attended."
    )
    date = models.DateField(
        default=timezone.now,
        db_index=True,
        help_text="Calendar date of the attendance session."
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='recorded_attendance_sessions',
        help_text="Staff member or teacher who recorded this session."
    )
    notes = models.TextField(
        blank=True,
        help_text="Optional general notes regarding the class session."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', 'classroom', 'subject']
        verbose_name = 'Attendance Session'
        verbose_name_plural = 'Attendance Sessions'
        constraints = [
            models.UniqueConstraint(
                fields=['classroom', 'subject', 'date'],
                name='unique_class_subject_date_session'
            )
        ]
        indexes = [
            models.Index(fields=['classroom', 'subject', 'date']),
            models.Index(fields=['date']),
        ]

    def clean(self):
        super().clean()
        if self.classroom and not self.classroom.is_active:
            raise ValidationError({
                'classroom': "Attendance cannot be recorded for an inactive classroom."
            })
        if self.subject and not self.subject.is_active:
            raise ValidationError({
                'subject': "Attendance cannot be recorded for an inactive subject."
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @classmethod
    @transaction.atomic
    def record_bulk_attendance(cls, classroom, subject, date, recorded_by, student_records, notes=""):
        """
        Atomically creates or updates an attendance session and its corresponding student records.
        Ensures complete ACID transaction consistency and enforces server-side assignment validation.
        Rolls back the entire transaction if any student record or date validation fails.
        
        student_records: list of dicts [{'student': student_instance, 'status': 'PRESENT', 'remarks': '...'}]
        """
        if not recorded_by.is_active:
            raise ValidationError("Inactive users cannot record attendance.")

        if recorded_by.role == 'TEACHER' and not recorded_by.can_mark_attendance(classroom, subject):
            raise ValidationError(
                f"Teacher '{recorded_by.get_full_name() or recorded_by.username}' is not assigned to take attendance for {classroom.display_name} - {subject.name}."
            )

        if not classroom.is_active:
            raise ValidationError("Attendance cannot be recorded for an inactive classroom.")

        if not subject.is_active:
            raise ValidationError("Attendance cannot be recorded for an inactive subject.")

        today = timezone.localdate()
        if date > today:
            raise ValidationError("Attendance date cannot be in the future.")

        max_backdated_days = getattr(settings, 'MAX_BACKDATED_ATTENDANCE_DAYS', 7)
        if recorded_by.role == 'TEACHER' and (today - date).days > max_backdated_days:
            raise ValidationError(
                f"Attendance cannot be submitted or edited for dates older than {max_backdated_days} days ({date} exceeds limit)."
            )

        if not student_records:
            raise ValidationError("No student attendance records were provided.")

        session, _ = cls.objects.update_or_create(
            classroom=classroom,
            subject=subject,
            date=date,
            defaults={
                'recorded_by': recorded_by,
                'notes': notes,
            }
        )

        for record in student_records:
            student = record.get('student')
            if not student:
                raise ValidationError("Student instance is required for all attendance entries.")

            if student.classroom_id != classroom.id:
                raise ValidationError(
                    f"Student '{student.full_name}' is enrolled in '{student.classroom}', not '{classroom}'."
                )
            if not student.is_active:
                raise ValidationError(
                    f"Cannot mark attendance for inactive student '{student.full_name}'."
                )

            status = record.get('status')
            if not status or status not in Attendance.Status.values:
                raise ValidationError(
                    f"Invalid or missing attendance status '{status}' for student '{student.full_name}'. Every student must be explicitly marked."
                )

            remarks = record.get('remarks', '')

            Attendance.objects.update_or_create(
                student=student,
                classroom=classroom,
                subject=subject,
                date=date,
                defaults={
                    'session': session,
                    'status': status,
                    'recorded_by': recorded_by,
                    'remarks': remarks,
                }
            )

        return session

    def __str__(self):
        return f"{self.classroom.display_name} | {self.subject.name} ({self.date})"


class Attendance(models.Model):
    """
    Individual attendance log for a specific Student, Classroom, Subject, and Date.
    Enforces that the student belongs to the selected class and prevents duplicate logs.
    """
    class Status(models.TextChoices):
        PRESENT = 'PRESENT', 'Present'
        ABSENT = 'ABSENT', 'Absent'
        LATE = 'LATE', 'Late'
        EXCUSED = 'EXCUSED', 'Excused'

    session = models.ForeignKey(
        AttendanceSession,
        on_delete=models.CASCADE,
        related_name='records',
        help_text="Parent session group for this entry."
    )
    student = models.ForeignKey(
        'students.Student',
        on_delete=models.CASCADE,
        related_name='attendance_records',
        help_text="Student whose attendance status is recorded."
    )
    classroom = models.ForeignKey(
        'academics.Classroom',
        on_delete=models.CASCADE,
        related_name='attendance_records',
        help_text="Classroom of the attendance entry."
    )
    subject = models.ForeignKey(
        'academics.Subject',
        on_delete=models.CASCADE,
        related_name='attendance_records',
        help_text="Subject attended."
    )
    date = models.DateField(
        db_index=True,
        help_text="Date of attendance."
    )
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.PRESENT,
        help_text="Recorded presence status."
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='recorded_attendances',
        help_text="Staff or teacher who marked this record."
    )
    remarks = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional annotation (e.g. 'Left early', 'Medical leave certificate submitted')."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', 'classroom', 'student']
        verbose_name = 'Attendance Record'
        verbose_name_plural = 'Attendance Records'
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'classroom', 'subject', 'date'],
                name='unique_student_class_subject_date'
            )
        ]
        indexes = [
            models.Index(fields=['student', 'date']),
            models.Index(fields=['classroom', 'subject', 'date']),
            models.Index(fields=['status', 'date']),
        ]
        permissions = [
            ('can_mark_attendance', 'Can record or update student attendance'),
            ('can_view_reports', 'Can view attendance reports and analytics'),
            ('can_export_attendance', 'Can export attendance data as CSV'),
        ]

    def clean(self):
        super().clean()
        # Synchronize class, subject, and date with session if session exists
        if self.session_id:
            if not self.classroom_id:
                self.classroom = self.session.classroom
            if not self.subject_id:
                self.subject = self.session.subject
            if not self.date:
                self.date = self.session.date

        # Enforce that student belongs to the selected class
        if self.student_id and self.classroom_id:
            if self.student.classroom_id != self.classroom_id:
                raise ValidationError({
                    'student': f"Student '{self.student.full_name}' is enrolled in '{self.student.classroom}', not '{self.classroom}'."
                })

        # Ensure student is active
        if self.student_id and not self.student.is_active:
            raise ValidationError({
                'student': f"Cannot mark attendance for inactive student '{self.student.full_name}'."
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.full_name} - {self.get_status_display()} ({self.date})"
