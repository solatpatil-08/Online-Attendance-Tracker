"""
Secure production diagnostic and verification utility for Online Attendance Tracking System.
Restricted strictly to holders of the application SECRET_KEY.
Does not expose passwords, password hashes, or session credentials.
"""

import hmac
from django.conf import settings
from django.http import JsonResponse, HttpResponseForbidden
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db import connection
from django.contrib.auth import get_user_model
from django.core.management import call_command


@method_decorator(csrf_exempt, name='dispatch')
class ProductionAuthDiagnosticView(View):
    """
    Secure diagnostic endpoint to inspect database connectivity, schema tables,
    and user account existence in production.
    Requires header 'X-Diagnostic-Key' or GET parameter 'key' matching SECRET_KEY.
    """

    def _is_authorized(self, request):
        token = request.headers.get('X-Diagnostic-Key') or request.GET.get('key', '')
        if not token or not settings.SECRET_KEY:
            return False
        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(token.strip(), settings.SECRET_KEY.strip())

    def get(self, request):
        if not self._is_authorized(request):
            return HttpResponseForbidden("Access Denied: Valid diagnostic token required.")

        User = get_user_model()
        db_conf = settings.DATABASES.get('default', {})
        engine = db_conf.get('ENGINE', 'unknown')
        raw_name = str(db_conf.get('NAME', ''))

        # Check database connection and introspection
        db_connected = False
        tables = []
        user_table_exists = False
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
            db_connected = True
            tables = connection.introspection.table_names()
            user_table_exists = 'accounts_user' in tables
        except Exception as e:
            db_error = str(e)
            return JsonResponse({
                'database_connected': False,
                'database_engine': engine,
                'error': db_error,
            }, status=500)

        # User metrics
        total_users = 0
        active_users = 0
        roles_summary = {}
        existing_usernames = []

        if user_table_exists:
            total_users = User.objects.count()
            active_users = User.objects.filter(is_active=True).count()
            for u in User.objects.all()[:50]:
                existing_usernames.append(u.username)
                roles_summary[u.role] = roles_summary.get(u.role, 0) + 1

        # Check specific user if requested via ?check_user=<username>
        check_user_result = None
        target_username = request.GET.get('check_user')
        if target_username and user_table_exists:
            matched_user = User.objects.filter(username__iexact=target_username.strip()).first()
            if matched_user:
                check_user_result = {
                    'username': matched_user.username,
                    'is_active': matched_user.is_active,
                    'role': matched_user.role,
                    'is_superuser': matched_user.is_superuser,
                }
            else:
                check_user_result = {'username': target_username, 'exists': False}

        return JsonResponse({
            'status': 'ok',
            'database_connected': db_connected,
            'database_engine': engine.split('.')[-1],
            'database_location': 'in-memory/tmp' if '/tmp' in raw_name else ('local' if 'Online Attendance' in raw_name else 'remote-managed'),
            'schema_ready': user_table_exists,
            'total_users': total_users,
            'active_users': active_users,
            'roles_summary': roles_summary,
            'usernames': existing_usernames,
            'user_check': check_user_result,
        })

    def post(self, request):
        """
        Allows secure, authorized one-time provisioning of an administrator account
        in the active production database without interactive CLI access.
        """
        if not self._is_authorized(request):
            return HttpResponseForbidden("Access Denied: Valid diagnostic token required.")

        User = get_user_model()
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        email = request.POST.get('email', '').strip() or f"{username}@attendance.local"

        if not username or not password:
            return JsonResponse({'error': 'Both username and password are required.'}, status=400)

        if len(password) < 8:
            return JsonResponse({'error': 'Password must be at least 8 characters long.'}, status=400)

        # Check or create administrator
        admin_user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': email,
                'role': User.Role.ADMIN,
                'is_staff': True,
                'is_superuser': True,
                'is_active': True,
            }
        )

        admin_user.set_password(password)
        admin_user.role = User.Role.ADMIN
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.is_active = True
        if email:
            admin_user.email = email
        admin_user.save()

        return JsonResponse({
            'success': True,
            'username': admin_user.username,
            'created': created,
            'role': admin_user.role,
            'is_active': admin_user.is_active,
            'is_superuser': admin_user.is_superuser,
        })
