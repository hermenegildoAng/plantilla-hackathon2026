"""Local development settings."""

import os

from .base import *  # noqa: F401,F403


DEBUG = True
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "*")  # noqa: F405

DATABASES["default"].setdefault("OPTIONS", {})  # noqa: F405

# Keep local runs quiet unless the developer opts in to SQL logging.
if env_bool("DJANGO_LOG_SQL", False):  # noqa: F405
    LOGGING["loggers"]["django.db.backends"] = {  # noqa: F405
        "handlers": ["console"],
        "level": "DEBUG",
        "propagate": False,
    }

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Vite dev server origins are allowed by default in base settings. Extra
# origins can be added through CORS_ALLOWED_ORIGINS without touching code.
if os.environ.get("CORS_ALLOW_ALL_ORIGINS", "").lower() in {"1", "true", "yes"}:
    CORS_ALLOW_ALL_ORIGINS = True
