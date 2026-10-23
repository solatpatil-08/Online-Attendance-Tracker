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

# Serverless SQLite auto-initialization fallback:
# If deployed on Vercel without an external managed PostgreSQL database,
# initialize tables and default accounts in /tmp/db.sqlite3 on cold start
# so the live application does not crash with 500 when testing.
if os.getenv('VERCEL') and not (os.getenv('DATABASE_URL') or os.getenv('POSTGRES_URL')):
    try:
        from django.core.management import call_command
        from django.db import connection
        existing_tables = connection.introspection.table_names()
        if 'accounts_user' not in existing_tables:
            call_command('migrate', interactive=False, verbosity=0)
            call_command('create_dev_users', confirm_production=True, verbosity=0)
            call_command('seed_sample_data', confirm_production=True, verbosity=0)
    except Exception as e:
        import logging
        logging.getLogger('django').warning(f"Vercel SQLite init warning: {e}")

