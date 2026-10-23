"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()

# Alias for Vercel Serverless WSGI detection
app = application

# Serverless database auto-migration & secure admin bootstrap:
if os.getenv('VERCEL'):
    try:
        from django.db import connection
        from django.core.management import call_command
        from django.contrib.auth import get_user_model

        # 1. If using fallback SQLite without managed DB, ensure schema exists
        if not (os.getenv('DATABASE_URL') or os.getenv('POSTGRES_URL')):
            existing_tables = connection.introspection.table_names()
            if 'accounts_user' not in existing_tables:
                call_command('migrate', interactive=False, verbosity=0)

        # 2. Secure administrator provisioning via environment variables
        admin_username = os.getenv('DJANGO_SUPERUSER_USERNAME') or os.getenv('ADMIN_USERNAME')
        admin_password = os.getenv('DJANGO_SUPERUSER_PASSWORD') or os.getenv('ADMIN_PASSWORD')
        admin_email = os.getenv('DJANGO_SUPERUSER_EMAIL') or os.getenv('ADMIN_EMAIL', 'admin@attendance.local')

        if admin_username and admin_password:
            User = get_user_model()
            admin_user, created = User.objects.get_or_create(
                username=admin_username.strip(),
                defaults={
                    'email': admin_email.strip(),
                    'role': User.Role.ADMIN,
                    'is_staff': True,
                    'is_superuser': True,
                    'is_active': True,
                }
            )
            # Ensure correct role, flags, and password
            if created or not admin_user.check_password(admin_password):
                admin_user.set_password(admin_password)
                admin_user.role = User.Role.ADMIN
                admin_user.is_staff = True
                admin_user.is_superuser = True
                admin_user.is_active = True
                admin_user.save()
    except Exception as e:
        import logging
        logging.getLogger('django').warning(f"Vercel startup init notice: {e}")

