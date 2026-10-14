import json
import datetime
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from accounts.models import User
from academics.models import Classroom, Subject
from students.models import Student
from attendance.models import Attendance, AttendanceSession


@login_required
def index(request):
    """
    Main dashboard router and landing page.
    Dynamically renders statistics, trends, and Chart.js datasets for Administrators and Teachers.
    """
    user = request.user
    today = timezone.localdate()

    # Determine requested date filter, defaulting to today
    date_str = request.GET.get('date')
    if date_str:
        try:
            selected_date = datetime.date.fromisoformat(date_str)
        except ValueError:
            selected_date = today
    else:
        selected_date = today

    if user.is_administrator:
        # 1. High-level institutional metrics
        total_active_students = Student.objects.filter(is_active=True).count()
        total_active_teachers = User.objects.filter(role=User.Role.TEACHER, is_active=True).count()
        total_classes = Classroom.objects.filter(is_active=True).count()
        total_subjects = Subject.objects.filter(is_active=True).count()

        # 2. Daily attendance counts for selected date
        date_records = Attendance.objects.filter(date=selected_date)
        records_count = date_records.count()
        present_count = date_records.filter(status=Attendance.Status.PRESENT).count()
        late_count = date_records.filter(status=Attendance.Status.LATE).count()
        absent_count = date_records.filter(status=Attendance.Status.ABSENT).count()
        excused_count = date_records.filter(status=Attendance.Status.EXCUSED).count()

        # Distinct student counts
        distinct_students_count = date_records.values('student').distinct().count()
        distinct_present_count = date_records.filter(status=Attendance.Status.PRESENT).values('student').distinct().count()
        distinct_absent_count = date_records.filter(status=Attendance.Status.ABSENT).values('student').distinct().count()

        # Attendance percentage calculation: (Present + Late) / Total Recorded Students
        # Note: Unrecorded students are not treated as absent; only recorded students form the denominator.
        effective_attended = present_count + late_count
        overall_attendance_pct = round(
            (effective_attended / records_count) * 100, 1
        ) if records_count > 0 else 0.0

        unrecorded_count = max(0, total_active_students - records_count)

        # 3. Chart 1: 7-Day Attendance Trend
        trend_labels = []
        trend_percentages = []
        trend_presents = []
        trend_absents = []
        trend_totals = []

        for i in range(6, -1, -1):
            day = selected_date - datetime.timedelta(days=i)
            day_records = Attendance.objects.filter(date=day)
            day_total = day_records.count()
            day_pres = day_records.filter(status__in=[Attendance.Status.PRESENT, Attendance.Status.LATE]).count()
            day_abs = day_records.filter(status=Attendance.Status.ABSENT).count()
            day_pct = round((day_pres / day_total) * 100, 1) if day_total > 0 else 0.0

            trend_labels.append(day.strftime('%b %d'))
            trend_percentages.append(day_pct)
            trend_presents.append(day_pres)
            trend_absents.append(day_abs)
            trend_totals.append(day_total)

        # 4. Chart 2: Status Distribution (Doughnut)
        status_labels = ['Present', 'Late', 'Absent', 'Excused']
        status_data = [present_count, late_count, absent_count, excused_count]

        # 5. Chart 3 & Table: Class-wise Attendance Performance
        class_bar_labels = []
        class_bar_percentages = []
        class_summaries = []

        active_classes = Classroom.objects.filter(is_active=True).order_by('name', 'section')
        for c in active_classes:
            c_records = date_records.filter(classroom=c)
            c_total = c_records.count()
            c_pres = c_records.filter(status=Attendance.Status.PRESENT).count()
            c_late = c_records.filter(status=Attendance.Status.LATE).count()
            c_abs = c_records.filter(status=Attendance.Status.ABSENT).count()
            c_exc = c_records.filter(status=Attendance.Status.EXCUSED).count()
            c_attended = c_pres + c_late
            c_rate = round((c_attended / c_total) * 100, 1) if c_total > 0 else 0.0

            class_bar_labels.append(c.display_name)
            class_bar_percentages.append(c_rate)

            class_summaries.append({
                'classroom': c,
                'enrolled_count': c.students.filter(is_active=True).count(),
                'recorded_count': c_total,
                'present_count': c_pres,
                'late_count': c_late,
                'absent_count': c_abs,
                'excused_count': c_exc,
                'percentage': c_rate if c_total > 0 else None,
            })

        # 6. Sessions recorded on selected date
        date_sessions = AttendanceSession.objects.filter(
            date=selected_date
        ).select_related('classroom', 'subject', 'recorded_by').order_by('-created_at')

        # Fallback recent sessions across all dates for activity stream
        all_recent_sessions = AttendanceSession.objects.all().select_related(
            'classroom', 'subject', 'recorded_by'
        ).order_by('-date', '-created_at')[:6]

        context = {
            'user': user,
            'selected_date': selected_date,
            'selected_date_str': selected_date.isoformat(),
            'today': today,
            'yesterday': today - datetime.timedelta(days=1),
            'prev_day': (selected_date - datetime.timedelta(days=1)).isoformat(),
            'next_day': (selected_date + datetime.timedelta(days=1)).isoformat(),
            'is_today': selected_date == today,
            'has_records': records_count > 0,
            'stats': {
                'total_students': total_active_students,
                'total_teachers': total_active_teachers,
                'total_classes': total_classes,
                'total_subjects': total_subjects,
                'records_count': records_count,
                'present_count': present_count,
                'late_count': late_count,
                'absent_count': absent_count,
                'excused_count': excused_count,
                'effective_attended': effective_attended,
                'unrecorded_count': unrecorded_count,
                'distinct_students_count': distinct_students_count,
                'distinct_present_count': distinct_present_count,
                'distinct_absent_count': distinct_absent_count,
                'attendance_percentage': overall_attendance_pct,
            },
            'class_summaries': class_summaries,
            'date_sessions': date_sessions,
            'all_recent_sessions': all_recent_sessions,
            # Data for json_script serialization
            'trend_labels': trend_labels,
            'trend_percentages': trend_percentages,
            'trend_presents': trend_presents,
            'trend_absents': trend_absents,
            'trend_totals': trend_totals,
            'status_labels': status_labels,
            'status_data': status_data,
            'class_labels': class_bar_labels,
            'class_percentages': class_bar_percentages,
            # Serialized JSON for Chart.js
            'chart_trend_labels_json': json.dumps(trend_labels),
            'chart_trend_percentages_json': json.dumps(trend_percentages),
            'chart_trend_presents_json': json.dumps(trend_presents),
            'chart_trend_absents_json': json.dumps(trend_absents),
            'chart_trend_totals_json': json.dumps(trend_totals),
            'chart_status_labels_json': json.dumps(status_labels),
            'chart_status_data_json': json.dumps(status_data),
            'chart_class_labels_json': json.dumps(class_bar_labels),
            'chart_class_percentages_json': json.dumps(class_bar_percentages),
        }
        return render(request, 'dashboard/admin_dashboard.html', context)

    else:
        # Teacher Portal
        assigned_assignments = user.teaching_assignments.filter(
            is_active=True
        ).select_related('classroom', 'subject')

        assigned_classes_count = assigned_assignments.values('classroom').distinct().count()
        assigned_students_count = Student.objects.filter(
            classroom__subject_assignments__teacher=user,
            classroom__subject_assignments__is_active=True,
            is_active=True
        ).distinct().count()

        today_sessions_count = AttendanceSession.objects.filter(
            recorded_by=user,
            date=selected_date
        ).count()

        today_records_count = Attendance.objects.filter(
            recorded_by=user,
            date=selected_date
        ).count()

        context = {
            'user': user,
            'selected_date': selected_date,
            'today': today,
            'stats': {
                'assigned_classes': assigned_classes_count,
                'total_students': assigned_students_count,
                'today_sessions': today_sessions_count,
                'today_attendance_count': today_records_count,
            },
            'assignments': assigned_assignments,
        }
        return render(request, 'dashboard/teacher_dashboard.html', context)
