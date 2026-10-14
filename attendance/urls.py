from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    path('', views.AttendanceRecordListView.as_view(), name='attendance_list'),
    path('reports/', views.AttendanceReportView.as_view(), name='reports'),
]
