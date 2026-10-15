from django.urls import path
from . import views

app_name = 'students'

urlpatterns = [
    path('', views.StudentListView.as_view(), name='student_list'),
    path('new/', views.StudentCreateView.as_view(), name='student_create'),
    path('<int:pk>/', views.StudentDetailView.as_view(), name='student_detail'),
    path('<int:pk>/edit/', views.StudentUpdateView.as_view(), name='student_edit'),
    path('<int:pk>/delete/', views.StudentDeleteView.as_view(), name='student_delete'),
    path('<int:pk>/toggle-status/', views.StudentToggleStatusView.as_view(), name='student_toggle_status'),
]
