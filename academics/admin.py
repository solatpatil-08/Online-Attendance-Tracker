from django.contrib import admin
from .models import AcademicYear, Classroom, Subject, ClassSubjectAssignment


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'is_current', 'total_classes', 'created_at')
    list_filter = ('is_current',)
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-start_date',)

    @admin.display(description='Total Classes')
    def total_classes(self, obj):
        return obj.classrooms.count()


class ClassSubjectAssignmentInline(admin.TabularInline):
    model = ClassSubjectAssignment
    extra = 1
    autocomplete_fields = ('teacher', 'subject')


@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    list_display = ('name', 'section', 'academic_year', 'class_teacher', 'total_students', 'is_active')
    list_filter = ('academic_year', 'is_active')
    search_fields = (
        'name',
        'section',
        'class_teacher__username',
        'class_teacher__first_name',
        'class_teacher__last_name'
    )
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('academic_year', 'name', 'section')
    inlines = [ClassSubjectAssignmentInline]

    @admin.display(description='Enrolled Students')
    def total_students(self, obj):
        return obj.students.count()


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'code')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('name',)


@admin.register(ClassSubjectAssignment)
class ClassSubjectAssignmentAdmin(admin.ModelAdmin):
    list_display = ('classroom', 'subject', 'teacher', 'is_active', 'created_at')
    list_filter = ('classroom__academic_year', 'classroom', 'subject', 'teacher', 'is_active')
    search_fields = (
        'classroom__name',
        'classroom__section',
        'subject__name',
        'subject__code',
        'teacher__username',
        'teacher__first_name',
        'teacher__last_name'
    )
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('classroom', 'subject')
