from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Authentication routes
    path('login/', views.UserLoginView.as_view(), name='login'),
    path('logout/', views.UserLogoutView.as_view(), name='logout'),
    path('profile/', views.profile_view, name='profile'),

    # Administrator teacher management routes
    path('teachers/', views.TeacherListView.as_view(), name='teacher_list'),
    path('teachers/new/', views.TeacherCreateView.as_view(), name='teacher_create'),
    path('teachers/<int:pk>/', views.TeacherDetailView.as_view(), name='teacher_detail'),
    path('teachers/<int:pk>/edit/', views.TeacherUpdateView.as_view(), name='teacher_edit'),
    path('teachers/<int:pk>/toggle-status/', views.TeacherToggleStatusView.as_view(), name='teacher_toggle_status'),
    path('teachers/<int:pk>/assign/', views.TeacherAssignClassSubjectView.as_view(), name='teacher_assign'),
    path('teachers/<int:pk>/assignments/<int:assignment_id>/remove/', views.TeacherRemoveAssignmentView.as_view(), name='teacher_remove_assignment'),
]
