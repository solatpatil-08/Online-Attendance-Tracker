import csv
import datetime
import json
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView, TemplateView
from django.views import View
from django.utils import timezone
from django.db.models import Count, Q
from django.http import HttpResponse
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.contrib import messages

from .models import AttendanceSession, Attendance
from academics.models import Classroom, Subject, ClassSubjectAssignment
from accounts.models import User
from accounts.permissions import check_teacher_class_authorization
from students.models import Student


def sanitize_csv_cell(value):
    """
    Guards against CSV Formula Injection (DDE injection).
    If a string starts with '=', '+', '-', '@', '\t', or '\r', prepends a single quote "'".
    """
    if value is None:
        return ""
    str_val = str(value)
    if str_val and str_val[0] in ('=', '+', '-', '@', '\t', '\r'):
        return f"'{str_val}"
    return str_val


def get_filtered_attendance_queryset(user, params):
    """
    Constructs and returns a validated, role-scoped Attendance queryset.
    - Administrators: View records across the entire institution.
    - Teachers: View only records for assigned classes, class-teacher classes, or recorded by self.
    """
    qs = Attendance.objects.select_related(
        'student', 'classroom', 'subject', 'recorded_by', 'classroom__academic_year'
    ).order_by('-date', 'classroom__name', 'classroom__section', 'student__roll_number', '-created_at')

    # Teacher role-based record scoping
    if not user.is_administrator:
        qs = qs.filter(
            Q(classroom__subject_assignments__teacher=user, classroom__subject_assignments__is_active=True) |
            Q(classroom__class_teacher=user) |
            Q(recorded_by=user)
        ).distinct()

    # 1. Exact date filter
    date_str = params.get('date', '').strip()
    if date_str:
        try:
            exact_date = datetime.date.fromisoformat(date_str)
            qs = qs.filter(date=exact_date)
        except ValueError:
            pass

    # 2. Date range filter
    start_date_str = params.get('start_date', '').strip()
    if start_date_str:
        try:
            start_date = datetime.date.fromisoformat(start_date_str)
            qs = qs.filter(date__gte=start_date)
        except ValueError:
            pass

    end_date_str = params.get('end_date', '').strip()
    if end_date_str:
        try:
            end_date = datetime.date.fromisoformat(end_date_str)
            qs = qs.filter(date__lte=end_date)
        except ValueError:
            pass

    # 3. Student search: text or roll number
    student_q = params.get('student', '').strip()
    if student_q:
        q_filter = (
            Q(student__first_name__icontains=student_q) |
            Q(student__last_name__icontains=student_q) |
            Q(student__student_id__icontains=student_q)
        )
        if student_q.isdigit():
            q_filter |= Q(student__roll_number=int(student_q))
        qs = qs.filter(q_filter)

    # 4. Class filter
    class_id = params.get('class_id', '').strip()
    if class_id:
        try:
            qs = qs.filter(classroom_id=int(class_id))
        except (ValueError, TypeError):
            pass

    # 5. Section filter
    section = params.get('section', '').strip()
    if section:
        qs = qs.filter(classroom__section__iexact=section)

    # 6. Subject filter
    subject_id = params.get('subject_id', '').strip()
    if subject_id:
        try:
            qs = qs.filter(subject_id=int(subject_id))
        except (ValueError, TypeError):
            pass

    # 7. Teacher filter (recorded_by)
    teacher_id = params.get('teacher_id', '').strip()
    if teacher_id:
        try:
            qs = qs.filter(recorded_by_id=int(teacher_id))
        except (ValueError, TypeError):
            pass

    # 8. Attendance status filter
    status = params.get('status', '').strip().upper()
    if status and status in Attendance.Status.values:
        qs = qs.filter(status=status)

    return qs


@method_decorator(login_required, name='dispatch')
class AttendanceRecordListView(ListView):
    """
    Displays saved individual attendance records with pagination, comprehensive search and filters,
    summary cards, and role-based security scoping.
    """
    model = Attendance
    template_name = 'attendance/attendance_list.html'
    context_object_name = 'records'
    paginate_by = 25

    def get_queryset(self):
        return get_filtered_attendance_queryset(self.request.user, self.request.GET)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Dropdowns data scoped to user permissions
        if user.is_administrator:
            classrooms = Classroom.objects.filter(is_active=True).order_by('name', 'section')
            subjects = Subject.objects.filter(is_active=True).order_by('name')
            teachers = User.objects.filter(role=User.Role.TEACHER, is_active=True).order_by('first_name', 'last_name')
        else:
            classrooms = Classroom.objects.filter(
                is_active=True
            ).filter(
                Q(subject_assignments__teacher=user, subject_assignments__is_active=True) |
                Q(class_teacher=user)
            ).distinct().order_by('name', 'section')

            subjects = Subject.objects.filter(
                is_active=True,
                class_assignments__teacher=user,
                class_assignments__is_active=True
            ).distinct().order_by('name')

            teachers = User.objects.filter(id=user.id)

        # Unique active sections
        sections = classrooms.values_list('section', flat=True).distinct().order_by('section')

        # Filtered queryset for summary counts
        filtered_qs = self.get_queryset()
        total_records = filtered_qs.count()
        present_count = filtered_qs.filter(status=Attendance.Status.PRESENT).count()
        late_count = filtered_qs.filter(status=Attendance.Status.LATE).count()
        absent_count = filtered_qs.filter(status=Attendance.Status.ABSENT).count()
        excused_count = filtered_qs.filter(status=Attendance.Status.EXCUSED).count()
        attended_count = present_count + late_count
        attendance_percentage = round((attended_count / total_records) * 100, 1) if total_records > 0 else 0

        # Preserve query params for pagination links
        get_params = self.request.GET.copy()
        if 'page' in get_params:
            del get_params['page']
        query_string = get_params.urlencode()

        context.update({
            'classrooms': classrooms,
            'subjects': subjects,
            'teachers': teachers,
            'sections': sections,
            'statuses': Attendance.Status.choices,
            'selected_date': self.request.GET.get('date', '').strip(),
            'start_date': self.request.GET.get('start_date', '').strip(),
            'end_date': self.request.GET.get('end_date', '').strip(),
            'student_query': self.request.GET.get('student', '').strip(),
            'selected_class_id': self.request.GET.get('class_id', '').strip(),
            'selected_section': self.request.GET.get('section', '').strip(),
            'selected_subject_id': self.request.GET.get('subject_id', '').strip(),
            'selected_teacher_id': self.request.GET.get('teacher_id', '').strip(),
            'selected_status': self.request.GET.get('status', '').strip().upper(),
            'total_records': total_records,
            'present_count': present_count,
            'late_count': late_count,
            'absent_count': absent_count,
            'excused_count': excused_count,
            'attendance_percentage': attendance_percentage,
            'query_string': query_string,
        })
        return context


@method_decorator(login_required, name='dispatch')
class AttendanceCSVExportView(View):
    """
    Exports filtered attendance records to CSV.
    - Validates user permissions (can_export_attendance)
    - Applies server-side filters and role-based record scoping
    - Protects against CSV formula injection
    - Outputs UTF-8 with BOM (utf-8-sig) for seamless Excel compatibility
    """
    def get(self, request, *args, **kwargs):
        user = request.user
        if not user.can_export_attendance():
            raise PermissionDenied("You do not have permission to export attendance data.")

        qs = get_filtered_attendance_queryset(user, request.GET)

        # Build CSV response with BOM for Excel
        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        response['Content-Disposition'] = f'attachment; filename="attendance_records_{timestamp}.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Attendance Date',
            'Student ID',
            'Roll Number',
            'Student Name',
            'Class',
            'Section',
            'Subject Code',
            'Subject Name',
            'Attendance Status',
            'Recorded By',
            'Remarks',
            'Created Timestamp',
        ])

        for record in qs:
            writer.writerow([
                sanitize_csv_cell(record.date.isoformat()),
                sanitize_csv_cell(record.student.student_id),
                sanitize_csv_cell(record.student.roll_number or ''),
                sanitize_csv_cell(record.student.full_name),
                sanitize_csv_cell(record.classroom.name),
                sanitize_csv_cell(record.classroom.section),
                sanitize_csv_cell(record.subject.code),
                sanitize_csv_cell(record.subject.name),
                sanitize_csv_cell(record.get_status_display()),
                sanitize_csv_cell(record.recorded_by.get_full_name() or record.recorded_by.username),
                sanitize_csv_cell(record.remarks),
                sanitize_csv_cell(record.created_at.strftime('%Y-%m-%d %H:%M:%S')),
            ])

        return response


@method_decorator(login_required, name='dispatch')
class AttendanceReportView(TemplateView):
    """
    Class-wise attendance reporting and daily institutional breakdown.
    - Accurately distinguishes between unrecorded attendance and explicitly marked absences.
    - Backed by real database metrics for Chart.js data visualizations.
    - Teacher access is scoped to their authorized classrooms.
    """
    template_name = 'reports/attendance_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        if not user.can_view_reports():
            raise PermissionDenied("You do not have permission to view attendance reports.")

        # Date filter
        date_str = self.request.GET.get('date', '').strip()
        if date_str:
            try:
                report_date = datetime.date.fromisoformat(date_str)
            except ValueError:
                report_date = timezone.localdate()
        else:
            report_date = timezone.localdate()

        context['report_date'] = report_date

        # Classrooms query
        if user.is_administrator:
            classrooms_qs = Classroom.objects.filter(is_active=True).select_related('academic_year').order_by('name', 'section')
        else:
            classrooms_qs = Classroom.objects.filter(
                is_active=True
            ).filter(
                Q(subject_assignments__teacher=user, subject_assignments__is_active=True) |
                Q(class_teacher=user)
            ).distinct().select_related('academic_year').order_by('name', 'section')

        selected_class_id = self.request.GET.get('class_id', '').strip()
        if selected_class_id:
            try:
                classrooms_qs = classrooms_qs.filter(id=int(selected_class_id))
            except (ValueError, TypeError):
                pass

        class_summaries = []
        for cr in classrooms_qs:
            total_enrolled = cr.students.filter(is_active=True).count()

            cr_records = Attendance.objects.filter(classroom=cr, date=report_date)
            if not user.is_administrator:
                cr_records = cr_records.filter(
                    Q(classroom__subject_assignments__teacher=user, classroom__subject_assignments__is_active=True) |
                    Q(classroom__class_teacher=user) |
                    Q(recorded_by=user)
                ).distinct()

            total_recorded = cr_records.count()
            present_count = cr_records.filter(status=Attendance.Status.PRESENT).count()
            late_count = cr_records.filter(status=Attendance.Status.LATE).count()
            absent_count = cr_records.filter(status=Attendance.Status.ABSENT).count()
            excused_count = cr_records.filter(status=Attendance.Status.EXCUSED).count()

            # Distinguish unmarked from absent:
            # If total_recorded < total_enrolled, unmarked students exist.
            unmarked_count = max(0, total_enrolled - total_recorded)

            if total_recorded == 0:
                recording_status = "Not Recorded"
                status_badge = "secondary"
                percentage = None
            elif unmarked_count > 0:
                recording_status = "Partially Recorded"
                status_badge = "warning"
                percentage = round(((present_count + late_count) / total_recorded) * 100, 1)
            else:
                recording_status = "Recorded"
                status_badge = "success"
                percentage = round(((present_count + late_count) / total_recorded) * 100, 1)

            class_summaries.append({
                'classroom': cr,
                'total_enrolled': total_enrolled,
                'total_recorded': total_recorded,
                'present': present_count,
                'late': late_count,
                'absent': absent_count,
                'excused': excused_count,
                'unmarked': unmarked_count,
                'status_label': recording_status,
                'status_badge': status_badge,
                'percentage': percentage,
            })

        # Institutional aggregates
        total_enrolled_all = sum(c['total_enrolled'] for c in class_summaries)
        total_recorded_all = sum(c['total_recorded'] for c in class_summaries)
        total_present_all = sum(c['present'] for c in class_summaries)
        total_late_all = sum(c['late'] for c in class_summaries)
        total_absent_all = sum(c['absent'] for c in class_summaries)
        total_excused_all = sum(c['excused'] for c in class_summaries)
        total_unmarked_all = sum(c['unmarked'] for c in class_summaries)
        attended_all = total_present_all + total_late_all

        overall_percentage = round((attended_all / total_recorded_all) * 100, 1) if total_recorded_all > 0 else 0

        # Chart Data
        status_chart_data = {
            'labels': ['Present', 'Late', 'Excused', 'Explicitly Absent', 'Unmarked'],
            'data': [total_present_all, total_late_all, total_excused_all, total_absent_all, total_unmarked_all],
        }

        class_chart_labels = []
        class_chart_data = []
        for c in class_summaries:
            if c['percentage'] is not None:
                class_chart_labels.append(c['classroom'].display_name)
                class_chart_data.append(c['percentage'])

        # 7-Day Trend
        trend_labels = []
        trend_percentages = []
        for i in range(6, -1, -1):
            day = report_date - datetime.timedelta(days=i)
            day_records = Attendance.objects.filter(date=day)
            if not user.is_administrator:
                day_records = day_records.filter(
                    Q(classroom__subject_assignments__teacher=user, classroom__subject_assignments__is_active=True) |
                    Q(classroom__class_teacher=user) |
                    Q(recorded_by=user)
                ).distinct()
            day_total = day_records.count()
            day_present = day_records.filter(status=Attendance.Status.PRESENT).count()
            day_late = day_records.filter(status=Attendance.Status.LATE).count()
            day_pct = round(((day_present + day_late) / day_total) * 100, 1) if day_total > 0 else 0
            trend_labels.append(day.strftime('%b %d'))
            trend_percentages.append(day_pct)

        # Classrooms dropdown for filter
        if user.is_administrator:
            all_filter_classrooms = Classroom.objects.filter(is_active=True).order_by('name', 'section')
        else:
            all_filter_classrooms = Classroom.objects.filter(
                is_active=True
            ).filter(
                Q(subject_assignments__teacher=user, subject_assignments__is_active=True) |
                Q(class_teacher=user)
            ).distinct().order_by('name', 'section')

        context.update({
            'class_summaries': class_summaries,
            'total_enrolled': total_enrolled_all,
            'total_recorded': total_recorded_all,
            'present_count': total_present_all,
            'late_count': total_late_all,
            'absent_count': total_absent_all,
            'excused_count': total_excused_all,
            'unmarked_count': total_unmarked_all,
            'overall_percentage': overall_percentage,
            'all_filter_classrooms': all_filter_classrooms,
            'selected_class_id': selected_class_id,
            'status_chart_data': status_chart_data,
            'class_chart_labels': class_chart_labels,
            'class_chart_data': class_chart_data,
            'trend_labels': trend_labels,
            'trend_percentages': trend_percentages,
        })
        return context


@method_decorator(login_required, name='dispatch')
class StudentAttendanceReportListView(ListView):
    """
    Renders cumulative student attendance metrics and progress indicators.
    - Excludes sessions prior to student enrollment date.
    - Strictly enforces teacher classroom authorization.
    - Provides date-range and class filtering.
    """
    model = Student
    template_name = 'reports/student_report_list.html'
    context_object_name = 'students'
    paginate_by = 25

    def get_queryset(self):
        user = self.request.user
        qs = Student.objects.filter(is_active=True).select_related(
            'classroom', 'classroom__academic_year'
        ).order_by('classroom__name', 'classroom__section', 'roll_number', 'last_name')

        if not user.is_administrator:
            qs = qs.filter(
                Q(classroom__subject_assignments__teacher=user, classroom__subject_assignments__is_active=True) |
                Q(classroom__class_teacher=user)
            ).distinct()

        # Class filter
        class_id = self.request.GET.get('class_id', '').strip()
        if class_id:
            try:
                qs = qs.filter(classroom_id=int(class_id))
            except (ValueError, TypeError):
                pass

        # Section filter
        section = self.request.GET.get('section', '').strip()
        if section:
            qs = qs.filter(classroom__section__iexact=section)

        # Search query
        q = self.request.GET.get('q', '').strip()
        if q:
            q_filter = (
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(student_id__icontains=q)
            )
            if q.isdigit():
                q_filter |= Q(roll_number=int(q))
            qs = qs.filter(q_filter)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        start_date_str = self.request.GET.get('start_date', '').strip()
        end_date_str = self.request.GET.get('end_date', '').strip()
        start_date = None
        end_date = None
        if start_date_str:
            try:
                start_date = datetime.date.fromisoformat(start_date_str)
            except ValueError:
                pass
        if end_date_str:
            try:
                end_date = datetime.date.fromisoformat(end_date_str)
            except ValueError:
                pass

        # Calculate student stats for paginated objects
        page_students = context['students']
        student_summaries = []
        for student in page_students:
            # Rule: Do not count sessions in which the student was not enrolled.
            # Sessions must be on or after student.enrollment_date
            records = student.attendance_records.filter(date__gte=student.enrollment_date)
            if start_date:
                records = records.filter(date__gte=start_date)
            if end_date:
                records = records.filter(date__lte=end_date)

            total_applicable = records.count()
            present = records.filter(status=Attendance.Status.PRESENT).count()
            late = records.filter(status=Attendance.Status.LATE).count()
            absent = records.filter(status=Attendance.Status.ABSENT).count()
            excused = records.filter(status=Attendance.Status.EXCUSED).count()
            attended = present + late

            pct = round((attended / total_applicable) * 100, 1) if total_applicable > 0 else None

            if pct is None:
                health = 'secondary'
                health_label = 'No Data'
            elif pct >= 85:
                health = 'success'
                health_label = 'Good'
            elif pct >= 70:
                health = 'warning'
                health_label = 'Warning'
            else:
                health = 'danger'
                health_label = 'At Risk'

            student_summaries.append({
                'student': student,
                'total_applicable': total_applicable,
                'present': present,
                'late': late,
                'absent': absent,
                'excused': excused,
                'attended': attended,
                'percentage': pct,
                'health': health,
                'health_label': health_label,
            })

        # Dropdowns
        if user.is_administrator:
            classrooms = Classroom.objects.filter(is_active=True).order_by('name', 'section')
        else:
            classrooms = Classroom.objects.filter(
                is_active=True
            ).filter(
                Q(subject_assignments__teacher=user, subject_assignments__is_active=True) |
                Q(class_teacher=user)
            ).distinct().order_by('name', 'section')

        sections = classrooms.values_list('section', flat=True).distinct().order_by('section')

        get_params = self.request.GET.copy()
        if 'page' in get_params:
            del get_params['page']
        query_string = get_params.urlencode()

        context.update({
            'student_summaries': student_summaries,
            'classrooms': classrooms,
            'sections': sections,
            'selected_class_id': self.request.GET.get('class_id', '').strip(),
            'selected_section': self.request.GET.get('section', '').strip(),
            'search_query': self.request.GET.get('q', '').strip(),
            'start_date': start_date_str,
            'end_date': end_date_str,
            'query_string': query_string,
        })
        return context


@method_decorator(login_required, name='dispatch')
class StudentAttendanceDetailReportView(TemplateView):
    """
    Comprehensive student attendance dossier.
    - Explicitly documents the attendance percentage formula.
    - Excludes sessions prior to student's enrollment date.
    - Breaks down attendance by subject and calendar history.
    - Role-based authorization: Teachers can only view assigned students.
    """
    template_name = 'reports/student_report_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        student_id = self.kwargs.get('pk')
        student = get_object_or_404(Student.objects.select_related('classroom', 'classroom__academic_year'), pk=student_id)

        # Enforce teacher authorization
        if not user.is_administrator:
            if not check_teacher_class_authorization(user, student.classroom):
                raise PermissionDenied(
                    f"You are not assigned to instruct or access records for student '{student.full_name}' ({student.classroom.display_name})."
                )

        # Date range filtering
        start_date_str = self.request.GET.get('start_date', '').strip()
        end_date_str = self.request.GET.get('end_date', '').strip()
        start_date = None
        end_date = None
        if start_date_str:
            try:
                start_date = datetime.date.fromisoformat(start_date_str)
            except ValueError:
                pass
        if end_date_str:
            try:
                end_date = datetime.date.fromisoformat(end_date_str)
            except ValueError:
                pass

        # Exclude records before enrollment_date
        records = student.attendance_records.filter(
            date__gte=student.enrollment_date
        ).select_related('classroom', 'subject', 'recorded_by').order_by('-date', '-created_at')

        if start_date:
            records = records.filter(date__gte=start_date)
        if end_date:
            records = records.filter(date__lte=end_date)

        total_applicable = records.count()
        present = records.filter(status=Attendance.Status.PRESENT).count()
        late = records.filter(status=Attendance.Status.LATE).count()
        absent = records.filter(status=Attendance.Status.ABSENT).count()
        excused = records.filter(status=Attendance.Status.EXCUSED).count()
        attended = present + late

        percentage = round((attended / total_applicable) * 100, 1) if total_applicable > 0 else None

        # Subject-wise summary
        subjects = Subject.objects.filter(attendance_records__in=records).distinct().order_by('name')
        subject_breakdown = []
        for subj in subjects:
            subj_records = records.filter(subject=subj)
            s_total = subj_records.count()
            s_present = subj_records.filter(status=Attendance.Status.PRESENT).count()
            s_late = subj_records.filter(status=Attendance.Status.LATE).count()
            s_absent = subj_records.filter(status=Attendance.Status.ABSENT).count()
            s_excused = subj_records.filter(status=Attendance.Status.EXCUSED).count()
            s_pct = round(((s_present + s_late) / s_total) * 100, 1) if s_total > 0 else None

            subject_breakdown.append({
                'subject': subj,
                'total': s_total,
                'present': s_present,
                'late': s_late,
                'absent': s_absent,
                'excused': s_excused,
                'percentage': s_pct,
            })

        # Chart Data
        status_chart_data = {
            'labels': ['Present', 'Late', 'Excused', 'Absent'],
            'data': [present, late, excused, absent],
        }

        context.update({
            'student': student,
            'total_applicable': total_applicable,
            'present_count': present,
            'late_count': late,
            'absent_count': absent,
            'excused_count': excused,
            'attended_count': attended,
            'attendance_percentage': percentage,
            'subject_breakdown': subject_breakdown,
            'history_records': records[:100],
            'total_history_count': total_applicable,
            'start_date': start_date_str,
            'end_date': end_date_str,
            'status_chart_data': status_chart_data,
        })
        return context


@method_decorator(login_required, name='dispatch')
class StudentAttendanceDetailCSVExportView(View):
    """
    Exports a single student's attendance history log to CSV.
    Validates permissions, scopes by enrollment date, and sanitizes untrusted cells.
    """
    def get(self, request, pk, *args, **kwargs):
        user = request.user
        if not user.can_export_attendance():
            raise PermissionDenied("You do not have permission to export attendance data.")

        student = get_object_or_404(Student, pk=pk)
        if not user.is_administrator and not check_teacher_class_authorization(user, student.classroom):
            raise PermissionDenied("You are not authorized to export data for this student.")

        start_date_str = request.GET.get('start_date', '').strip()
        end_date_str = request.GET.get('end_date', '').strip()

        records = student.attendance_records.filter(
            date__gte=student.enrollment_date
        ).select_related('classroom', 'subject', 'recorded_by').order_by('-date')

        if start_date_str:
            try:
                start_date = datetime.date.fromisoformat(start_date_str)
                records = records.filter(date__gte=start_date)
            except ValueError:
                pass
        if end_date_str:
            try:
                end_date = datetime.date.fromisoformat(end_date_str)
                records = records.filter(date__lte=end_date)
            except ValueError:
                pass

        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        safe_name = f"{student.first_name}_{student.last_name}".replace(" ", "_")
        response['Content-Disposition'] = f'attachment; filename="attendance_{safe_name}_{timestamp}.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Attendance Date',
            'Student ID',
            'Student Name',
            'Class',
            'Section',
            'Subject Code',
            'Subject Name',
            'Status',
            'Recorded By',
            'Remarks',
        ])

        for r in records:
            writer.writerow([
                sanitize_csv_cell(r.date.isoformat()),
                sanitize_csv_cell(student.student_id),
                sanitize_csv_cell(student.full_name),
                sanitize_csv_cell(r.classroom.name),
                sanitize_csv_cell(r.classroom.section),
                sanitize_csv_cell(r.subject.code),
                sanitize_csv_cell(r.subject.name),
                sanitize_csv_cell(r.get_status_display()),
                sanitize_csv_cell(r.recorded_by.get_full_name() or r.recorded_by.username),
                sanitize_csv_cell(r.remarks),
            ])

        return response



@method_decorator(login_required, name='dispatch')
class AttendanceTakeView(View):
    """
    View for recording and updating daily classroom attendance.
    Strictly enforces:
    - Only teachers assigned to the classroom and subject (or administrators) can take attendance.
    - Prevents taking or editing attendance for future dates.
    - Restricts backdated attendance submission/edits for teachers according to MAX_BACKDATED_ATTENDANCE_DAYS.
    - Controlled edit workflow: does not silently overwrite existing attendance; loads previous records and requires explicit confirmation.
    - All enrolled students must be explicitly marked (unmarked students are not silently treated as absent).
    - Preserves user selections if server validation encounters any error.
    - Uses database transactions with atomic rollback on any failure.
    """
    template_name = 'attendance/take_attendance.html'

    def get_session_parameters(self, request):
        user = request.user
        today = timezone.localdate()
        max_backdated_days = getattr(settings, 'MAX_BACKDATED_ATTENDANCE_DAYS', 7)
        min_date = today - datetime.timedelta(days=max_backdated_days) if not user.is_administrator else None

        date_str = request.GET.get('date', '').strip()
        selected_date = today
        if date_str:
            try:
                selected_date = datetime.date.fromisoformat(date_str)
            except ValueError:
                selected_date = today

        # Enforce date limits
        if not user.is_administrator:
            if selected_date > today:
                messages.warning(request, "Attendance date cannot be in the future. Reset to today's date.")
                selected_date = today
            elif min_date and selected_date < min_date:
                messages.warning(
                    request,
                    f"Attendance cannot be modified for dates older than {max_backdated_days} days ({selected_date}). Reset to today."
                )
                selected_date = today

        # Get permitted classrooms
        if user.is_administrator:
            classrooms = Classroom.objects.filter(is_active=True).select_related('academic_year').order_by('name', 'section')
        else:
            classrooms = Classroom.objects.filter(
                subject_assignments__teacher=user,
                subject_assignments__is_active=True,
                is_active=True
            ).distinct().select_related('academic_year').order_by('name', 'section')

        selected_class_id = request.GET.get('class_id', '').strip()
        selected_classroom = None
        if selected_class_id:
            selected_classroom = classrooms.filter(pk=selected_class_id).first()
            if not selected_classroom and not user.is_administrator:
                raise PermissionDenied("You are not assigned to instruct or take attendance for this classroom.")

        # Get permitted subjects for the selected classroom
        subjects = Subject.objects.none()
        if selected_classroom:
            if user.is_administrator:
                subjects = Subject.objects.filter(
                    class_assignments__classroom=selected_classroom,
                    is_active=True
                ).distinct().order_by('name')
                if not subjects.exists():
                    subjects = Subject.objects.filter(is_active=True).order_by('name')
            else:
                subjects = Subject.objects.filter(
                    class_assignments__classroom=selected_classroom,
                    class_assignments__teacher=user,
                    class_assignments__is_active=True,
                    is_active=True
                ).distinct().order_by('name')

        selected_subject_id = request.GET.get('subject_id', '').strip()
        selected_subject = None
        if selected_subject_id and selected_classroom:
            selected_subject = subjects.filter(pk=selected_subject_id).first()
            if not selected_subject and not user.is_administrator:
                raise PermissionDenied("You are not assigned to instruct or take attendance for this subject in this classroom.")

        return {
            'today': today,
            'selected_date': selected_date,
            'min_date': min_date,
            'max_date': today,
            'max_backdated_days': max_backdated_days,
            'classrooms': classrooms,
            'selected_classroom': selected_classroom,
            'subjects': subjects,
            'selected_subject': selected_subject,
        }

    def compute_summary_counts(self, students):
        total_enrolled = len(students)
        present_count = sum(1 for s in students if getattr(s, 'current_status', None) == Attendance.Status.PRESENT)
        absent_count = sum(1 for s in students if getattr(s, 'current_status', None) == Attendance.Status.ABSENT)
        late_count = sum(1 for s in students if getattr(s, 'current_status', None) == Attendance.Status.LATE)
        excused_count = sum(1 for s in students if getattr(s, 'current_status', None) == Attendance.Status.EXCUSED)
        unmarked_count = sum(1 for s in students if not getattr(s, 'current_status', None))

        effective_attended = present_count + late_count
        effective_total = present_count + late_count + absent_count
        if effective_total > 0:
            percentage = round((effective_attended / effective_total) * 100, 1)
        elif total_enrolled > 0 and excused_count == total_enrolled:
            percentage = 100.0
        else:
            percentage = 0.0

        return {
            'total_enrolled': total_enrolled,
            'present_count': present_count,
            'absent_count': absent_count,
            'late_count': late_count,
            'excused_count': excused_count,
            'unmarked_count': unmarked_count,
            'attendance_percentage': percentage,
        }

    def get(self, request):
        user = request.user
        if not user.is_active:
            raise PermissionDenied("Inactive accounts cannot record attendance.")

        params = self.get_session_parameters(request)
        selected_classroom = params['selected_classroom']
        selected_subject = params['selected_subject']
        selected_date = params['selected_date']

        students = []
        existing_session = None
        is_existing_session = False

        if selected_classroom and selected_subject:
            # Check server authorization explicitly
            if not user.can_mark_attendance(selected_classroom, selected_subject):
                raise PermissionDenied("You are not assigned to instruct or take attendance for this class and subject.")

            students = list(Student.objects.filter(
                classroom=selected_classroom,
                is_active=True
            ).order_by('roll_number', 'last_name', 'first_name'))

            existing_session = AttendanceSession.objects.filter(
                classroom=selected_classroom,
                subject=selected_subject,
                date=selected_date
            ).first()

            if existing_session:
                is_existing_session = True
                records_by_student = {rec.student_id: rec for rec in existing_session.records.all()}
                for student in students:
                    rec = records_by_student.get(student.id)
                    student.current_status = rec.status if rec else None
                    student.current_remarks = rec.remarks if rec else ''
            else:
                for student in students:
                    student.current_status = None  # Unmarked initially
                    student.current_remarks = ''

        counts = self.compute_summary_counts(students)

        context = {
            'classrooms': params['classrooms'],
            'subjects': params['subjects'],
            'selected_classroom': selected_classroom,
            'selected_subject': selected_subject,
            'selected_date': selected_date,
            'selected_date_str': selected_date.isoformat(),
            'min_date_str': params['min_date'].isoformat() if params['min_date'] else '',
            'max_date_str': params['max_date'].isoformat(),
            'max_backdated_days': params['max_backdated_days'],
            'students': students,
            'existing_session': existing_session,
            'is_existing_session': is_existing_session,
            'session_notes': existing_session.notes if existing_session else '',
            'status_choices': Attendance.Status.choices,
            **counts,
        }
        return render(request, self.template_name, context)

    def post(self, request):
        user = request.user
        if not user.is_active:
            raise PermissionDenied("Inactive accounts cannot record attendance.")

        class_id = request.POST.get('classroom_id')
        subject_id = request.POST.get('subject_id')
        date_str = request.POST.get('date')
        notes = request.POST.get('notes', '').strip()
        confirm_edit = request.POST.get('confirm_edit') == '1'

        if not class_id or not subject_id or not date_str:
            messages.error(request, "Please select classroom, subject, and date.")
            return redirect('attendance:take_attendance')

        try:
            date = datetime.date.fromisoformat(date_str)
        except ValueError:
            messages.error(request, "Invalid date format.")
            return redirect('attendance:take_attendance')

        classroom = get_object_or_404(Classroom, pk=class_id)
        subject = get_object_or_404(Subject, pk=subject_id)

        # SERVER-SIDE VALIDATION: Enforce teacher assignment
        if not user.can_mark_attendance(classroom, subject):
            raise PermissionDenied("You are not assigned to take attendance for this class and subject.")

        if not classroom.is_active:
            messages.error(request, f"Cannot record attendance for inactive classroom '{classroom.display_name}'.")
            return redirect('attendance:take_attendance')

        if not subject.is_active:
            messages.error(request, f"Cannot record attendance for inactive subject '{subject.name}'.")
            return redirect('attendance:take_attendance')

        # Check date rules
        today = timezone.localdate()
        max_backdated_days = getattr(settings, 'MAX_BACKDATED_ATTENDANCE_DAYS', 7)
        if not user.is_administrator:
            if date > today:
                messages.error(request, "Attendance date cannot be in the future.")
                return redirect(f"{reverse('attendance:take_attendance')}?class_id={classroom.id}&subject_id={subject.id}&date={today.isoformat()}")
            if (today - date).days > max_backdated_days:
                messages.error(
                    request,
                    f"Attendance cannot be submitted or edited for dates older than {max_backdated_days} days ({date} exceeds limit)."
                )
                return redirect(f"{reverse('attendance:take_attendance')}?class_id={classroom.id}&subject_id={subject.id}&date={today.isoformat()}")

        # Controlled Edit Workflow: Check if session already exists
        existing_session = AttendanceSession.objects.filter(
            classroom=classroom,
            subject=subject,
            date=date
        ).first()
        is_existing_session = existing_session is not None

        if is_existing_session and not confirm_edit:
            messages.warning(
                request,
                f"An attendance session for {classroom.display_name} - {subject.name} on {date.strftime('%b %d, %Y')} already exists. Please review the loaded records and confirm your changes before saving."
            )
            return redirect(f"{reverse('attendance:take_attendance')}?class_id={classroom.id}&subject_id={subject.id}&date={date.isoformat()}")

        # Fetch enrolled active students
        students = list(Student.objects.filter(classroom=classroom, is_active=True).order_by('roll_number', 'last_name', 'first_name'))
        student_records = []
        unmarked_students = []

        for student in students:
            status_val = request.POST.get(f'status_{student.id}', '').strip()
            remarks_val = request.POST.get(f'remarks_{student.id}', '').strip()
            student.current_status = status_val
            student.current_remarks = remarks_val

            if not status_val or status_val not in Attendance.Status.values:
                unmarked_students.append(student)
            else:
                student_records.append({
                    'student': student,
                    'status': status_val,
                    'remarks': remarks_val,
                })

        # Do not treat unmarked students as absent automatically: Reject submission if any student is unmarked
        if unmarked_students:
            names = ', '.join([s.full_name for s in unmarked_students[:3]])
            extra = f" and {len(unmarked_students)-3} others" if len(unmarked_students) > 3 else ""
            messages.error(
                request,
                f"Cannot save attendance: {len(unmarked_students)} student(s) remain unmarked ({names}{extra}). Every student must be marked Present, Absent, Late, or Excused."
            )
            # Preserve user's submitted values when re-rendering
            params = self.get_session_parameters(request)
            counts = self.compute_summary_counts(students)
            context = {
                'classrooms': params['classrooms'],
                'subjects': params['subjects'],
                'selected_classroom': classroom,
                'selected_subject': subject,
                'selected_date': date,
                'selected_date_str': date.isoformat(),
                'min_date_str': params['min_date'].isoformat() if params['min_date'] else '',
                'max_date_str': params['max_date'].isoformat(),
                'max_backdated_days': params['max_backdated_days'],
                'students': students,
                'existing_session': existing_session,
                'is_existing_session': is_existing_session,
                'status_choices': Attendance.Status.choices,
                'session_notes': notes,
                **counts,
            }
            return render(request, self.template_name, context)

        if not student_records:
            messages.warning(request, f"No active students found in {classroom.display_name} to record attendance.")
            return redirect(f"{reverse('attendance:take_attendance')}?class_id={classroom.id}&subject_id={subject.id}&date={date.isoformat()}")

        try:
            AttendanceSession.record_bulk_attendance(
                classroom=classroom,
                subject=subject,
                date=date,
                recorded_by=user,
                student_records=student_records,
                notes=notes
            )
            p_cnt = sum(1 for r in student_records if r['status'] == Attendance.Status.PRESENT)
            a_cnt = sum(1 for r in student_records if r['status'] == Attendance.Status.ABSENT)
            l_cnt = sum(1 for r in student_records if r['status'] == Attendance.Status.LATE)
            e_cnt = sum(1 for r in student_records if r['status'] == Attendance.Status.EXCUSED)

            action_verb = "updated" if is_existing_session else "recorded"
            messages.success(
                request,
                f"Attendance for {classroom.display_name} &bull; {subject.name} on {date.strftime('%b %d, %Y')} was successfully {action_verb} ({len(student_records)} students: {p_cnt} Present, {a_cnt} Absent, {l_cnt} Late, {e_cnt} Excused)."
            )
        except ValidationError as e:
            messages.error(request, f"Validation error while saving attendance: {e.message if hasattr(e, 'message') else e}")
            params = self.get_session_parameters(request)
            counts = self.compute_summary_counts(students)
            context = {
                'classrooms': params['classrooms'],
                'subjects': params['subjects'],
                'selected_classroom': classroom,
                'selected_subject': subject,
                'selected_date': date,
                'selected_date_str': date.isoformat(),
                'min_date_str': params['min_date'].isoformat() if params['min_date'] else '',
                'max_date_str': params['max_date'].isoformat(),
                'max_backdated_days': params['max_backdated_days'],
                'students': students,
                'existing_session': existing_session,
                'is_existing_session': is_existing_session,
                'status_choices': Attendance.Status.choices,
                'session_notes': notes,
                **counts,
            }
            return render(request, self.template_name, context)

        return redirect(f"{reverse('attendance:attendance_list')}?class_id={classroom.id}&date={date.isoformat()}")

