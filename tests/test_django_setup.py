from pathlib import Path
from importlib import import_module

from django.apps import apps
from django.conf import settings


def test_manage_py_exists() -> None:
    assert Path("manage.py").exists()


def test_django_settings_module_is_configured() -> None:
    settings_path = Path("src/ps_price_site/settings.py")
    assert settings_path.exists()
    assert 'TIME_ZONE = "Asia/Taipei"' in settings_path.read_text()

    assert settings.configured
    assert settings.TIME_ZONE == "Asia/Taipei"
    assert settings.USE_TZ
    assert settings.INSTALLED_APPS == [
        "django.contrib.contenttypes",
        "django.contrib.staticfiles",
        "ps_price_sync",
    ]
    assert settings.STATIC_URL == "static/"
    assert settings.TEMPLATES[0]["BACKEND"] == "django.template.backends.django.DjangoTemplates"
    assert settings.TEMPLATES[0]["APP_DIRS"] is True
    assert apps.get_app_config("ps_price_sync").name == "ps_price_sync"
    assert import_module(settings.ROOT_URLCONF).__name__ == "ps_price_site.urls"


def test_readme_mentions_django_sync_commands() -> None:
    readme_content = Path("README.md").read_text()
    assert "uv run python manage.py migrate" in readme_content
    assert "uv run python manage.py sync_ps_store --mode catalog-and-snapshot" in readme_content
