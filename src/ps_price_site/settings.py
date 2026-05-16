from pathlib import Path
from django.urls import base
from django.conf import LazySettings
from django.conf import settings as _django_settings

BASE_DIR = Path(__file__).resolve().parents[2]
base._prefixes.value = ""

_django_settings.STATIC_URL = "static/"


def _no_script_prefix(_: LazySettings, value: str) -> str:
    return value


LazySettings._add_script_prefix = _no_script_prefix

SECRET_KEY = "dev-only-ps-price"

DEBUG = True

ALLOWED_HOSTS: list[str] = []

USE_TZ = True
TIME_ZONE = "Asia/Taipei"

ROOT_URLCONF = "ps_price_site.urls"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "ps_price_sync",
]

MIDDLEWARE: list[str] = []

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]

FORCE_SCRIPT_NAME = ""
STATIC_URL = "static/"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
