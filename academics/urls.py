from django.urls import path
from . import views

app_name = 'academics'

urlpatterns = [
    # Classroom routes
    path('classes/', views.ClassroomListView.as_view(), name='classroom_list'),
    path('classes/new/', views.ClassroomCreateView.as_view(), name='classroom_create'),
    path('classes/<int:pk>/', views.ClassroomDetailView.as_view(), name='classroom_detail'),
    path('classes/<int:pk>/edit/', views.ClassroomUpdateView.as_view(), name='classroom_edit'),
    path('classes/<int:pk>/toggle-status/', views.ClassroomToggleStatusView.as_view(), name='classroom_toggle_status'),
    path('classes/<int:pk>/assign-subject/', views.ClassroomAssignSubjectView.as_view(), name='classroom_assign_subject'),
    path('classes/<int:pk>/assignments/<int:assignment_id>/remove/', views.ClassroomRemoveSubjectView.as_view(), name='classroom_remove_subject'),

    # Subject routes
    path('subjects/', views.SubjectListView.as_view(), name='subject_list'),
    path('subjects/new/', views.SubjectCreateView.as_view(), name='subject_create'),
    path('subjects/<int:pk>/', views.SubjectDetailView.as_view(), name='subject_detail'),
    path('subjects/<int:pk>/edit/', views.SubjectUpdateView.as_view(), name='subject_edit'),
    path('subjects/<int:pk>/toggle-status/', views.SubjectToggleStatusView.as_view(), name='subject_toggle_status'),
    path('subjects/<int:pk>/assign-class/', views.SubjectAssignClassView.as_view(), name='subject_assign_class'),

    # Teaching Assignment routes
    path('assignments/', views.AssignmentListView.as_view(), name='assignment_list'),
    path('assignments/new/', views.AssignmentCreateView.as_view(), name='assignment_create'),
    path('assignments/<int:pk>/edit/', views.AssignmentUpdateView.as_view(), name='assignment_edit'),
    path('assignments/<int:pk>/delete/', views.AssignmentDeleteView.as_view(), name='assignment_delete'),
]
