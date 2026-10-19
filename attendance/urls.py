from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    path('', views.AttendanceRecordListView.as_view(), name='attendance_list'),
    path('export/csv/', views.AttendanceCSVExportView.as_view(), name='export_csv'),
    path('take/', views.AttendanceTakeView.as_view(), name='take_attendance'),
    path('reports/', views.AttendanceReportView.as_view(), name='reports'),
    path('reports/students/', views.StudentAttendanceReportListView.as_view(), name='student_report_list'),
    path('reports/students/<int:pk>/', views.StudentAttendanceDetailReportView.as_view(), name='student_report_detail'),
    path('reports/students/<int:pk>/export/csv/', views.StudentAttendanceDetailCSVExportView.as_view(), name='student_report_export_csv'),
]
