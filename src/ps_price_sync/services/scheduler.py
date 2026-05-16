from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from datetime import timezone as dt_timezone
import os
import time as _time
from zoneinfo import ZoneInfo
from zoneinfo import ZoneInfoNotFoundError

from django.core.management import call_command
from django.utils import timezone


VALID_SYNC_MODES = {"catalog-only", "snapshot-only", "catalog-and-snapshot"}


@dataclass(frozen=True)
class SchedulerSettings:
    mode: str
    max_pages: int
    timezone_name: str
    run_at: time


def load_settings(environ: Mapping[str, str] | None = None) -> SchedulerSettings:
    env = os.environ if environ is None else environ

    mode = env.get("PS_PRICE_SYNC_MODE", "catalog-and-snapshot")
    if mode not in VALID_SYNC_MODES:
        raise ValueError(f"invalid PS_PRICE_SYNC_MODE={mode!r}")

    raw_max_pages = env.get("PS_PRICE_SYNC_MAX_PAGES", "500")
    try:
        max_pages = int(raw_max_pages)
    except ValueError as exc:
        raise ValueError("PS_PRICE_SYNC_MAX_PAGES") from exc
    if max_pages < 1:
        raise ValueError("PS_PRICE_SYNC_MAX_PAGES")

    timezone_name = env.get("PS_PRICE_SYNC_TIMEZONE", "Asia/Taipei")
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("PS_PRICE_SYNC_TIMEZONE") from exc

    run_at = _parse_hhmm(env.get("PS_PRICE_SYNC_AT", "03:30"))

    return SchedulerSettings(
        mode=mode,
        max_pages=max_pages,
        timezone_name=timezone_name,
        run_at=run_at,
    )


def _parse_hhmm(value: str) -> time:
    try:
        run_at = datetime.strptime(value, "%H:%M").time()
    except ValueError as exc:
        raise ValueError("PS_PRICE_SYNC_AT") from exc
    return run_at


def snapshot_date_for(now: datetime, timezone_name: str) -> date:
    tz = ZoneInfo(timezone_name)
    if now.tzinfo is None:
        return now.replace(tzinfo=dt_timezone.utc).astimezone(tz).date()
    return now.astimezone(tz).date()


def next_run_at(now: datetime, settings: SchedulerSettings) -> datetime:
    local_tz = ZoneInfo(settings.timezone_name)
    if now.tzinfo is None:
        current_local = now.replace(tzinfo=local_tz)
    else:
        current_local = now.astimezone(local_tz)
    scheduled = datetime(
        current_local.year,
        current_local.month,
        current_local.day,
        settings.run_at.hour,
        settings.run_at.minute,
        tzinfo=local_tz,
    )
    if scheduled <= current_local:
        scheduled += timedelta(days=1)
    return scheduled


def seconds_until_next_run(now: datetime, settings: SchedulerSettings) -> float:
    local_tz = ZoneInfo(settings.timezone_name)
    current_local = now.astimezone(local_tz) if now.tzinfo else now.replace(tzinfo=local_tz)
    next_run = next_run_at(current_local, settings)
    return (next_run - current_local).total_seconds()


def run_sync_once(settings: SchedulerSettings, now: datetime | None = None) -> None:
    snapshot_now = now or timezone.now()
    snapshot_date = snapshot_date_for(snapshot_now, settings.timezone_name)
    call_command(
        "sync_ps_store",
        "--mode",
        settings.mode,
        "--until-last",
        "--max-pages",
        str(settings.max_pages),
        "--snapshot-date",
        snapshot_date.isoformat(),
    )


def run_scheduler_loop(
    settings: SchedulerSettings,
    *,
    sleep: Callable[[float], None] = _time.sleep,
    now_func: Callable[[], datetime] = timezone.now,
    run_once: Callable[[SchedulerSettings, datetime], None] = run_sync_once,
    iterations: int | None = None,
) -> None:
    if iterations is None:
        while True:
            current = now_func()
            sleep(seconds_until_next_run(current, settings))
            run_once(settings, now_func())
        return

    for _ in range(iterations):
        current = now_func()
        sleep(seconds_until_next_run(current, settings))
        run_once(settings, now_func())
