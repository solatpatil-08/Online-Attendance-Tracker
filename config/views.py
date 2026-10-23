"""
Custom error handlers for Online Attendance Tracking System.
"""

import sys
import hmac
from django.conf import settings
from django.http import JsonResponse
from django.views.defaults import server_error


def custom_server_error(request, template_name='500.html'):
    """
    Secure production 500 error handler.
    Returns standard generic 500 page for normal users.
    If authenticated via X-Diagnostic-Key matching SECRET_KEY,
    returns the exact exception name and message for immediate diagnosis.
    """
    token = request.headers.get('X-Diagnostic-Key') or request.GET.get('diagnostic_key', '')
    is_valid_token = False
    if token:
        token_clean = token.strip()
        sk = getattr(settings, 'SECRET_KEY', '') or ''
        if sk and hmac.compare_digest(token_clean, sk.strip()):
            is_valid_token = True

    if is_valid_token:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        import traceback
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback) if exc_type else []
        return JsonResponse({
            'error_type': str(exc_type.__name__ if exc_type else 'Unknown'),
            'error_message': str(exc_value) if exc_value else 'No exception info',
            'traceback': tb_lines[-4:],
        }, status=500)

    try:
        return server_error(request, template_name=template_name)
    except Exception:
        from django.http import HttpResponseServerError
        return HttpResponseServerError("<h1>Server Error (500)</h1>", content_type="text/html")
