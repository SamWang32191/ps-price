from __future__ import annotations

from datetime import datetime
from datetime import time
import logging
from zoneinfo import ZoneInfo

import pytest

from ps_price_sync.services import scheduler


def test_load_settings_uses_defaults() -> None:
    settings = scheduler.load_settings({})

    assert settings == scheduler.SchedulerSettings(
        mode="catalog-and-snapshot",
        max_pages=500,
        timezone_name="Asia/Taipei",
        run_at=time(3, 30),
    )


def test_load_settings_reads_environment_values() -> None:
    settings = scheduler.load_settings(
        {
            "PS_PRICE_SYNC_MODE": "catalog-only",
            "PS_PRICE_SYNC_MAX_PAGES": "25",
            "PS_PRICE_SYNC_TIMEZONE": "UTC",
            "PS_PRICE_SYNC_AT": "04:05",
        }
    )

    assert settings == scheduler.SchedulerSettings(
        mode="catalog-only",
        max_pages=25,
        timezone_name="UTC",
        run_at=time(4, 5),
    )


@pytest.mark.parametrize(
    ("env", "message"),
    [
        ({"PS_PRICE_SYNC_MODE": "bad"}, "PS_PRICE_SYNC_MODE"),
        ({"PS_PRICE_SYNC_MAX_PAGES": "0"}, "PS_PRICE_SYNC_MAX_PAGES"),
        ({"PS_PRICE_SYNC_MAX_PAGES": "abc"}, "PS_PRICE_SYNC_MAX_PAGES"),
        ({"PS_PRICE_SYNC_AT": "bad"}, "PS_PRICE_SYNC_AT"),
        ({"PS_PRICE_SYNC_TIMEZONE": "Mars/Base"}, "PS_PRICE_SYNC_TIMEZONE"),
    ],
)
def test_load_settings_rejects_invalid_values(env: dict[str, str], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        scheduler.load_settings(env)


def test_snapshot_date_uses_configured_timezone() -> None:
    now = datetime(2026, 5, 15, 18, 0, tzinfo=ZoneInfo("UTC"))

    assert scheduler.snapshot_date_for(now, "Asia/Taipei").isoformat() == "2026-05-16"


def test_next_run_at_uses_today_when_time_has_not_passed() -> None:
    settings = scheduler.SchedulerSettings(
        mode="catalog-and-snapshot",
        max_pages=500,
        timezone_name="Asia/Taipei",
        run_at=time(3, 30),
    )
    now = datetime(2026, 5, 16, 2, 0, tzinfo=ZoneInfo("Asia/Taipei"))

    assert scheduler.next_run_at(now, settings) == datetime(2026, 5, 16, 3, 30, tzinfo=ZoneInfo("Asia/Taipei"))


def test_next_run_at_uses_now_when_time_matches_schedule() -> None:
    settings = scheduler.SchedulerSettings(
        mode="catalog-and-snapshot",
        max_pages=500,
        timezone_name="Asia/Taipei",
        run_at=time(3, 30),
    )
    now = datetime(2026, 5, 16, 3, 30, tzinfo=ZoneInfo("Asia/Taipei"))

    assert scheduler.next_run_at(now, settings) == now


def test_next_run_at_uses_tomorrow_when_time_has_passed() -> None:
    settings = scheduler.SchedulerSettings(
        mode="catalog-and-snapshot",
        max_pages=500,
        timezone_name="Asia/Taipei",
        run_at=time(3, 30),
    )
    now = datetime(2026, 5, 16, 4, 0, tzinfo=ZoneInfo("Asia/Taipei"))

    assert scheduler.next_run_at(now, settings) == datetime(2026, 5, 17, 3, 30, tzinfo=ZoneInfo("Asia/Taipei"))


def test_run_sync_once_calls_sync_command(monkeypatch) -> None:
    calls: list[tuple[str, str, str, str, str, str, str, str, str]] = []

    def fake_call_command(*args: object) -> None:
        calls.append(tuple(str(arg) for arg in args))

    monkeypatch.setattr(scheduler, "call_command", fake_call_command)
    settings = scheduler.SchedulerSettings(
        mode="catalog-and-snapshot",
        max_pages=500,
        timezone_name="Asia/Taipei",
        run_at=time(3, 30),
    )
    now = datetime(2026, 5, 15, 18, 0, tzinfo=ZoneInfo("UTC"))

    scheduler.run_sync_once(settings, now=now)

    assert calls == [
        (
            "sync_ps_store",
            "--mode",
            "catalog-and-snapshot",
            "--until-last",
            "--max-pages",
            "500",
            "--snapshot-date",
            "2026-05-16",
        )
    ]


def test_run_scheduler_loop_runs_one_iteration() -> None:
    settings = scheduler.SchedulerSettings(
        mode="catalog-and-snapshot",
        max_pages=500,
        timezone_name="Asia/Taipei",
        run_at=time(3, 30),
    )
    sleeps: list[float] = []
    runs: list[datetime] = []
    now_values = iter(
        [
            datetime(2026, 5, 16, 3, 0, tzinfo=ZoneInfo("Asia/Taipei")),
            datetime(2026, 5, 16, 3, 30, tzinfo=ZoneInfo("Asia/Taipei")),
        ]
    )

    def fake_now() -> datetime:
        return next(now_values)

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    def fake_run_once(settings: scheduler.SchedulerSettings, now: datetime) -> None:
        del settings
        runs.append(now)

    scheduler.run_scheduler_loop(
        settings,
        sleep=fake_sleep,
        now_func=fake_now,
        run_once=fake_run_once,
        iterations=1,
    )

    assert sleeps == [1800.0]
    assert runs == [datetime(2026, 5, 16, 3, 30, tzinfo=ZoneInfo("Asia/Taipei"))]


def test_run_scheduler_loop_runs_ambiguous_time_once_per_local_date() -> None:
    settings = scheduler.SchedulerSettings(
        mode="catalog-and-snapshot",
        max_pages=500,
        timezone_name="America/New_York",
        run_at=time(1, 30),
    )
    sleeps: list[float] = []
    runs: list[datetime] = []
    now_values = iter(
        [
            datetime(2026, 11, 1, 1, 30, fold=0, tzinfo=ZoneInfo("America/New_York")),
            datetime(2026, 11, 1, 1, 30, fold=0, tzinfo=ZoneInfo("America/New_York")),
            datetime(2026, 11, 1, 1, 31, fold=0, tzinfo=ZoneInfo("America/New_York")),
            datetime(2026, 11, 2, 1, 30, tzinfo=ZoneInfo("America/New_York")),
        ]
    )

    def fake_now() -> datetime:
        return next(now_values)

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    def fake_run_once(settings: scheduler.SchedulerSettings, now: datetime) -> None:
        del settings
        runs.append(now)

    scheduler.run_scheduler_loop(
        settings,
        sleep=fake_sleep,
        now_func=fake_now,
        run_once=fake_run_once,
        iterations=2,
    )

    assert sleeps == [0.0, 89940.0]
    assert [run.date().isoformat() for run in runs] == ["2026-11-01", "2026-11-02"]


def test_seconds_until_next_run_uses_elapsed_time_across_dst() -> None:
    settings = scheduler.SchedulerSettings(
        mode="catalog-and-snapshot",
        max_pages=500,
        timezone_name="America/New_York",
        run_at=time(3, 30),
    )
    now = datetime(2026, 3, 8, 1, 30, tzinfo=ZoneInfo("America/New_York"))

    assert scheduler.seconds_until_next_run(now, settings) == 3600.0


def test_seconds_until_next_run_skips_nonexistent_dst_time() -> None:
    settings = scheduler.SchedulerSettings(
        mode="catalog-and-snapshot",
        max_pages=500,
        timezone_name="America/New_York",
        run_at=time(2, 30),
    )
    now = datetime(2026, 3, 8, 1, 30, tzinfo=ZoneInfo("America/New_York"))

    assert scheduler.seconds_until_next_run(now, settings) == 86400.0


def test_seconds_until_next_run_skips_next_day_nonexistent_dst_time() -> None:
    settings = scheduler.SchedulerSettings(
        mode="catalog-and-snapshot",
        max_pages=500,
        timezone_name="America/New_York",
        run_at=time(2, 30),
    )
    now = datetime(2026, 3, 7, 3, 0, tzinfo=ZoneInfo("America/New_York"))

    assert scheduler.seconds_until_next_run(now, settings) == 167400.0


def test_seconds_until_next_run_uses_future_fold_across_dst() -> None:
    settings = scheduler.SchedulerSettings(
        mode="catalog-and-snapshot",
        max_pages=500,
        timezone_name="America/New_York",
        run_at=time(1, 30),
    )
    now = datetime(2026, 11, 1, 1, 15, fold=1, tzinfo=ZoneInfo("America/New_York"))

    assert scheduler.seconds_until_next_run(now, settings) == 900.0


def test_run_scheduler_loop_logs_failure_and_continues(caplog: pytest.LogCaptureFixture) -> None:
    settings = scheduler.SchedulerSettings(
        mode="catalog-and-snapshot",
        max_pages=500,
        timezone_name="Asia/Taipei",
        run_at=time(3, 30),
    )
    sleeps: list[float] = []
    now_values = iter(
        [
            datetime(2026, 5, 16, 3, 0, tzinfo=ZoneInfo("Asia/Taipei")),
            datetime(2026, 5, 16, 3, 30, tzinfo=ZoneInfo("Asia/Taipei")),
            datetime(2026, 5, 16, 3, 31, tzinfo=ZoneInfo("Asia/Taipei")),
            datetime(2026, 5, 17, 3, 30, tzinfo=ZoneInfo("Asia/Taipei")),
        ]
    )
    calls = 0

    def fake_now() -> datetime:
        return next(now_values)

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    def fake_run_once(settings: scheduler.SchedulerSettings, now: datetime) -> None:
        nonlocal calls
        del settings, now
        calls += 1
        if calls == 1:
            raise RuntimeError("sync failed")

    with caplog.at_level(logging.ERROR, logger="ps_price_sync.services.scheduler"):
        scheduler.run_scheduler_loop(
            settings,
            sleep=fake_sleep,
            now_func=fake_now,
            run_once=fake_run_once,
            iterations=2,
        )

    assert calls == 2
    assert sleeps == [1800.0, 86340.0]
    assert "Daily sync failed; waiting for next scheduled run" in caplog.text
