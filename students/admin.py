from django.contrib import admin
from .models import Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        'student_id',
        'first_name',
        'last_name',
        'classroom',
        'roll_number',
        'gender',
        'is_active',
        'enrollment_date'
    )
    list_filter = (
        'classroom__academic_year',
        'classroom',
        'gender',
        'is_active',
        'enrollment_date'
    )
    search_fields = (
        'student_id',
        'first_name',
        'last_name',
        'email',
        'phone_number',
        'guardian_name',
        'guardian_phone'
    )
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('classroom', 'roll_number', 'last_name', 'first_name')
    list_editable = ('is_active',)
    fieldsets = (
        ('Academic Enrollment', {
            'fields': ('student_id', 'classroom', 'roll_number', 'enrollment_date', 'is_active')
        }),
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'gender', 'date_of_birth')
        }),
        ('Contact Details', {
            'fields': ('email', 'phone_number', 'guardian_name', 'guardian_phone')
        }),
        ('System Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
