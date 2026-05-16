from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

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

STATIC_URL = "static/"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
