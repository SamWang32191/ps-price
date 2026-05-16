from importlib import import_module
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.urls import resolve, reverse
from ps_price_site import settings as project_settings


def test_manage_py_exists() -> None:
    assert Path("manage.py").exists()


def test_django_settings_module_is_configured() -> None:
    settings_path = Path("src/ps_price_site/settings.py")
    assert settings_path.exists()
    assert 'TIME_ZONE = "Asia/Taipei"' in settings_path.read_text()
    assert settings.configured
    assert settings.TIME_ZONE == "Asia/Taipei"
    assert settings.USE_TZ
    installed_apps = settings.INSTALLED_APPS
    assert "django.contrib.contenttypes" in installed_apps
    assert "ps_price_sync" in installed_apps
    assert "ps_price_web" in installed_apps
    assert installed_apps.index("ps_price_sync") < installed_apps.index("ps_price_web")
    assert "django.contrib.staticfiles" in installed_apps
    assert settings.TEMPLATES[0]["APP_DIRS"] is True
    assert apps.get_app_config("ps_price_sync").name == "ps_price_sync"
    assert apps.get_app_config("ps_price_web").name == "ps_price_web"
    assert import_module(settings.ROOT_URLCONF).__name__ == "ps_price_site.urls"


def test_web_routes_are_registered() -> None:
    assert reverse("ps_price_web:deals") == "/deals/"
    assert reverse("ps_price_web:product_detail", kwargs={"product_id": "P-100"}) == "/products/P-100/"
    assert resolve("/deals/").view_name == "ps_price_web:deals"
    assert resolve("/products/P-100/").view_name == "ps_price_web:product_detail"


def test_readme_mentions_django_sync_commands() -> None:
    readme_content = Path("README.md").read_text()
    assert "uv run python manage.py migrate" in readme_content
    assert "uv run python manage.py sync_ps_store --mode catalog-and-snapshot" in readme_content


def test_database_name_defaults_to_repo_sqlite(monkeypatch) -> None:
    monkeypatch.delenv("PS_PRICE_DATABASE_PATH", raising=False)

    assert project_settings._database_name_from_env() == project_settings.BASE_DIR / "db.sqlite3"


def test_database_name_uses_environment_path(monkeypatch) -> None:
    monkeypatch.setenv("PS_PRICE_DATABASE_PATH", "/data/db.sqlite3")

    assert project_settings._database_name_from_env() == "/data/db.sqlite3"


def test_allowed_hosts_defaults_to_empty_list(monkeypatch) -> None:
    monkeypatch.delenv("PS_PRICE_ALLOWED_HOSTS", raising=False)

    assert project_settings._allowed_hosts_from_env() == []


def test_allowed_hosts_parses_comma_separated_environment(monkeypatch) -> None:
    monkeypatch.setenv("PS_PRICE_ALLOWED_HOSTS", "localhost, 127.0.0.1,,")

    assert project_settings._allowed_hosts_from_env() == ["localhost", "127.0.0.1"]
