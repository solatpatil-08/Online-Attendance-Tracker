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
    import logging
    logger = logging.getLogger('django')
    try:
        from django.db import connection
        from django.core.management import call_command
        from django.contrib.auth import get_user_model

        # Ensure schema tables exist on active database (SQLite or remote PostgreSQL)
        existing_tables = connection.introspection.table_names()
        if 'accounts_user' not in existing_tables:
            logger.info("Initializing database schema via migrate...")
            call_command('migrate', interactive=False, verbosity=0)

        # Secure administrator provisioning via environment variables
        admin_password = os.getenv('DJANGO_SUPERUSER_PASSWORD') or os.getenv('ADMIN_PASSWORD')
        admin_username = os.getenv('DJANGO_SUPERUSER_USERNAME') or os.getenv('ADMIN_USERNAME') or ('admin' if admin_password else None)
        admin_email = os.getenv('DJANGO_SUPERUSER_EMAIL') or os.getenv('ADMIN_EMAIL', 'admin@attendance.local')

        User = get_user_model()
        if admin_username and admin_password:
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
                logger.info(f"Provisioned superuser: {admin_username}")

        # Optional: Seed complete Indian school demo dataset on initial deploy if requested
        if os.getenv('SEED_DEMO_DATA', 'False').lower() in ('true', '1', 't'):
            if not User.objects.filter(role=User.Role.ADMIN).exists():
                logger.info("Initializing Indian school demo dataset...")
                call_command('seed_demo_data', confirm_production=True, verbosity=0)
    except Exception as e:
        logger.error(f"Vercel startup init notice: {e}", exc_info=True)
    finally:
        try:
            connection.close()
        except Exception:
            pass


