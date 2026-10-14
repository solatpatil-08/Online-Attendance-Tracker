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
    path('teachers/<int:pk>/toggle-status/', views.TeacherToggleStatusView.as_view(), name='teacher_toggle_status'),
]
