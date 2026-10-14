from django.contrib import admin
from .models import AttendanceSession, Attendance


class AttendanceInline(admin.TabularInline):
    model = Attendance
    extra = 0
    fields = ('student', 'status', 'remarks')
    autocomplete_fields = ('student',)
    show_change_link = True


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = (
        'classroom',
        'subject',
        'date',
        'recorded_by',
        'total_logged',
        'created_at'
    )
    list_filter = (
        'date',
        'classroom__academic_year',
        'classroom',
        'subject'
    )
    search_fields = (
        'classroom__name',
        'classroom__section',
        'subject__name',
        'recorded_by__username',
        'notes'
    )
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-date', 'classroom', 'subject')
    inlines = [AttendanceInline]

    @admin.display(description='Logged Records')
    def total_logged(self, obj):
        return obj.records.count()


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = (
        'student',
        'classroom',
        'subject',
        'date',
        'status',
        'recorded_by',
        'updated_at'
    )
    list_filter = (
        'status',
        'date',
        'classroom',
        'subject'
    )
    search_fields = (
        'student__student_id',
        'student__first_name',
        'student__last_name',
        'remarks'
    )
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-date', 'classroom', 'student')
    list_editable = ('status',)
    autocomplete_fields = ('student', 'session', 'classroom', 'subject')
