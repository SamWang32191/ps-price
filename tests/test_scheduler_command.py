from __future__ import annotations

from datetime import time

from django.core.management import call_command
from django.core.management.base import CommandError
import pytest

from ps_price_sync.services import scheduler


def test_run_daily_sync_scheduler_loads_settings_and_starts_loop(monkeypatch):
    captured: dict[str, object] = {}

    def fake_load_settings() -> scheduler.SchedulerSettings:
        captured["load_settings_called"] = True
        return scheduler.SchedulerSettings(
            mode="catalog-and-snapshot",
            max_pages=500,
            timezone_name="Asia/Taipei",
            run_at=time(3, 30),
        )

    def fake_run_scheduler_loop(settings: scheduler.SchedulerSettings) -> None:
        captured["settings"] = settings

    monkeypatch.setattr(scheduler, "load_settings", fake_load_settings)
    monkeypatch.setattr(scheduler, "run_scheduler_loop", fake_run_scheduler_loop)

    call_command("run_daily_sync_scheduler")

    assert captured["load_settings_called"] is True
    assert captured["settings"] == scheduler.SchedulerSettings(
        mode="catalog-and-snapshot",
        max_pages=500,
        timezone_name="Asia/Taipei",
        run_at=time(3, 30),
    )


def test_run_daily_sync_scheduler_reports_invalid_settings(monkeypatch) -> None:
    monkeypatch.setattr(
        scheduler,
        "load_settings",
        lambda: (_ for _ in ()).throw(ValueError("PS_PRICE_SYNC_AT")),
    )

    with pytest.raises(CommandError, match="PS_PRICE_SYNC_AT"):
        call_command("run_daily_sync_scheduler")
