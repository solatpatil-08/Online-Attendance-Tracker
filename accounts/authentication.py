"""
Custom authentication backends for Online Attendance Tracking System.
"""

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q


class EmailOrUsernameModelBackend(ModelBackend):
    """
    Custom authentication backend permitting authentication using either
    username or primary email address (case-insensitive).

    Strictly enforces:
    1. Cryptographic password hashing verification via check_password().
    2. Active user status enforcement (is_active=True).
    3. Normalization and whitespace stripping of identifiers.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None

        clean_identifier = username.strip()
        if not clean_identifier:
            return None

        User = get_user_model()
        # Query matching case-insensitively on username or email
        user = User.objects.filter(
            Q(username__iexact=clean_identifier) | Q(email__iexact=clean_identifier)
        ).first()

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
