from .base import *  # noqa
from django.core.exceptions import ImproperlyConfigured

DEBUG = False

if SECRET_KEY == "django-insecure-anaacoss-2026-super-secret-key-change-this-93x7k2m8q1":
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set in production.")

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
