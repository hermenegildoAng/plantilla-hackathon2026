"""Production hardening settings."""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403


DEBUG = False

if SECRET_KEY == "django-insecure-development-only-change-me":  # noqa: F405
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be configured with a strong value in production."
    )

if not ALLOWED_HOSTS:  # noqa: F405
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be configured in production.")

SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True

# TLS is terminated by the reverse proxy in front of Django.
USE_X_FORWARDED_HOST = True

LOGGING["handlers"]["console"] = {  # noqa: F405
    "class": "logging.StreamHandler",
    "formatter": "verbose",
}
LOGGING["root"]["level"] = "WARNING"  # noqa: F405
LOGGING["loggers"]["apps"]["level"] = "INFO"  # noqa: F405
