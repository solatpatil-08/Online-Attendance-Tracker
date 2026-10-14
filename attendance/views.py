import datetime
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView, TemplateView
from django.utils import timezone
from django.db.models import Count, Q

from .models import AttendanceSession, Attendance
from academics.models import Classroom, Subject
from accounts.permissions import check_teacher_class_authorization


@method_decorator(login_required, name='dispatch')
class AttendanceRecordListView(ListView):
    """
    Lists recent attendance sessions and logs.
    - Administrators: All institutional attendance sessions.
    - Teachers: Only attendance sessions for assigned classes.
    """
    model = AttendanceSession
    template_name = 'attendance/attendance_list.html'
    context_object_name = 'sessions'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        qs = AttendanceSession.objects.select_related('classroom', 'subject', 'recorded_by').order_by('-date', '-created_at')

        if not user.is_administrator:
            qs = qs.filter(
                classroom__subject_assignments__teacher=user,
                classroom__subject_assignments__is_active=True
            ).distinct()

        # Optional date filter
        date_str = self.request.GET.get('date')
        if date_str:
            try:
                selected_date = datetime.date.fromisoformat(date_str)
                qs = qs.filter(date=selected_date)
            except ValueError:
                pass

        class_id = self.request.GET.get('class_id')
        if class_id:
            qs = qs.filter(classroom_id=class_id)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        if user.is_administrator:
            context['classrooms'] = Classroom.objects.filter(is_active=True)
        else:
            context['classrooms'] = Classroom.objects.filter(
                subject_assignments__teacher=user,
                is_active=True
            ).distinct()
        context['selected_date'] = self.request.GET.get('date', '')
        context['selected_class_id'] = self.request.GET.get('class_id', '')
        return context


@method_decorator(login_required, name='dispatch')
class AttendanceReportView(TemplateView):
    """
    Attendance reports and analytics overview.
    Calculates exact percentage based on recorded students for the chosen date.
    """
    template_name = 'reports/attendance_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        date_str = self.request.GET.get('date')
        if date_str:
            try:
                report_date = datetime.date.fromisoformat(date_str)
            except ValueError:
                report_date = timezone.localdate()
        else:
            report_date = timezone.localdate()

        context['report_date'] = report_date

        # Query records
        records = Attendance.objects.filter(date=report_date).select_related('student', 'classroom', 'subject')
        if not user.is_administrator:
            records = records.filter(
                classroom__subject_assignments__teacher=user,
                classroom__subject_assignments__is_active=True
            ).distinct()

        total_recorded = records.count()
        present_count = records.filter(status=Attendance.Status.PRESENT).count()
        late_count = records.filter(status=Attendance.Status.LATE).count()
        absent_count = records.filter(status=Attendance.Status.ABSENT).count()
        excused_count = records.filter(status=Attendance.Status.EXCUSED).count()

        overall_percentage = round((present_count / total_recorded) * 100, 1) if total_recorded > 0 else 0

        # Class breakdown
        classrooms_qs = Classroom.objects.filter(is_active=True)
        if not user.is_administrator:
            classrooms_qs = classrooms_qs.filter(
                subject_assignments__teacher=user,
                is_active=True
            ).distinct()

        class_summaries = []
        for cr in classrooms_qs:
            cr_records = records.filter(classroom=cr)
            cr_total = cr_records.count()
            cr_present = cr_records.filter(status=Attendance.Status.PRESENT).count()
            cr_absent = cr_records.filter(status=Attendance.Status.ABSENT).count()
            cr_late = cr_records.filter(status=Attendance.Status.LATE).count()
            cr_rate = round((cr_present / cr_total) * 100, 1) if cr_total > 0 else None

            class_summaries.append({
                'classroom': cr,
                'total_enrolled': cr.students.filter(is_active=True).count(),
                'total_recorded': cr_total,
                'present': cr_present,
                'absent': cr_absent,
                'late': cr_late,
                'percentage': cr_rate,
            })

        context.update({
            'total_recorded': total_recorded,
            'present_count': present_count,
            'late_count': late_count,
            'absent_count': absent_count,
            'excused_count': excused_count,
            'overall_percentage': overall_percentage,
            'class_summaries': class_summaries,
            'recent_records': records.order_by('-updated_at')[:50],
        })
        return context
