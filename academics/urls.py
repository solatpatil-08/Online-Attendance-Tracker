from django.urls import path
from . import views

app_name = 'academics'

urlpatterns = [
    # Classroom routes
    path('classes/', views.ClassroomListView.as_view(), name='classroom_list'),
    path('classes/new/', views.ClassroomCreateView.as_view(), name='classroom_create'),
    path('classes/<int:pk>/', views.ClassroomDetailView.as_view(), name='classroom_detail'),

    # Subject routes
    path('subjects/', views.SubjectListView.as_view(), name='subject_list'),
    path('subjects/new/', views.SubjectCreateView.as_view(), name='subject_create'),
]
