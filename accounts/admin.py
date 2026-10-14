from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, TeacherProfile


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        ('System Role & Profile Info', {
            'fields': ('role', 'phone_number', 'profile_picture')
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('System Role & Profile Info', {
            'fields': ('role', 'phone_number', 'profile_picture')
        }),
    )


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'employee_id', 'department', 'qualification', 'date_of_joining')
    search_fields = ('employee_id', 'user__username', 'user__first_name', 'user__last_name', 'department')
    list_filter = ('department', 'date_of_joining')
