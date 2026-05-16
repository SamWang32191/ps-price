import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


def _database_name_from_env() -> Path | str:
    configured_path = os.environ.get("PS_PRICE_DATABASE_PATH", "").strip()
    if configured_path:
        return configured_path
    return BASE_DIR / "db.sqlite3"


def _allowed_hosts_from_env() -> list[str]:
    raw_hosts = os.environ.get("PS_PRICE_ALLOWED_HOSTS")
    if raw_hosts is None:
        return []
    return [host.strip() for host in raw_hosts.split(",") if host.strip()]


SECRET_KEY = "dev-only-ps-price"

DEBUG = True

ALLOWED_HOSTS = _allowed_hosts_from_env()

USE_TZ = True
TIME_ZONE = "Asia/Taipei"

ROOT_URLCONF = "ps_price_site.urls"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "ps_price_sync",
    "ps_price_web",
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

STATIC_URL = "static/"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": _database_name_from_env(),
    }
}
