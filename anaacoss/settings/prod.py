from .base import *  # noqa
from django.core.exceptions import ImproperlyConfigured

DEBUG = False

if SECRET_KEY == "dev-only-change-me-with-at-least-32-bytes":
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set in production.")

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
