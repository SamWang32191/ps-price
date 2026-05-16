from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from datetime import timezone as dt_timezone
import logging
import os
import time as _time
from zoneinfo import ZoneInfo
from zoneinfo import ZoneInfoNotFoundError

from django.core.management import call_command
from django.utils import timezone


VALID_SYNC_MODES = {"catalog-only", "snapshot-only", "catalog-and-snapshot"}
logger = logging.getLogger(__name__)


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
    if not (len(value) == 5 and value[2] == ":" and value[:2].isdigit() and value[3:].isdigit()):
        raise ValueError("PS_PRICE_SYNC_AT")
    hour = int(value[:2])
    minute = int(value[3:])
    if hour > 23 or minute > 59:
        raise ValueError("PS_PRICE_SYNC_AT")
    return time(hour, minute)


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
    current_utc = current_local.astimezone(dt_timezone.utc)

    candidates = _scheduled_candidates(
        current_local.year,
        current_local.month,
        current_local.day,
        settings.run_at,
        local_tz,
    )
    for candidate in candidates:
        if candidate.astimezone(dt_timezone.utc) >= current_utc:
            return candidate

    tomorrow = current_local + timedelta(days=1)
    return _scheduled_candidates(
        tomorrow.year,
        tomorrow.month,
        tomorrow.day,
        settings.run_at,
        local_tz,
    )[0]


def _scheduled_candidates(year: int, month: int, day: int, run_at: time, local_tz: ZoneInfo) -> list[datetime]:
    candidates = []
    seen_utc: set[datetime] = set()
    for fold in (0, 1):
        candidate = datetime(year, month, day, run_at.hour, run_at.minute, tzinfo=local_tz, fold=fold)
        if not _is_valid_local_time(candidate):
            continue
        candidate_utc = candidate.astimezone(dt_timezone.utc)
        if candidate_utc in seen_utc:
            continue
        candidates.append(candidate)
        seen_utc.add(candidate_utc)
    return sorted(candidates, key=lambda candidate: candidate.astimezone(dt_timezone.utc))


def _is_valid_local_time(candidate: datetime) -> bool:
    round_tripped = candidate.astimezone(dt_timezone.utc).astimezone(candidate.tzinfo)
    return (
        round_tripped.year == candidate.year
        and round_tripped.month == candidate.month
        and round_tripped.day == candidate.day
        and round_tripped.hour == candidate.hour
        and round_tripped.minute == candidate.minute
    )


def seconds_until_next_run(now: datetime, settings: SchedulerSettings) -> float:
    return _seconds_until_next_run_after_date(now, settings, after_date=None)


def _seconds_until_next_run_after_date(
    now: datetime,
    settings: SchedulerSettings,
    after_date: date | None,
) -> float:
    local_tz = ZoneInfo(settings.timezone_name)
    current_local = now.astimezone(local_tz) if now.tzinfo else now.replace(tzinfo=local_tz)
    next_run = _next_run_after_date(current_local, settings, after_date)
    return (
        next_run.astimezone(dt_timezone.utc) - current_local.astimezone(dt_timezone.utc)
    ).total_seconds()


def _next_run_after_date(now: datetime, settings: SchedulerSettings, after_date: date | None) -> datetime:
    next_run = next_run_at(now, settings)
    if after_date is None or next_run.date() != after_date:
        return next_run

    local_tz = ZoneInfo(settings.timezone_name)
    tomorrow = now.astimezone(local_tz).date() + timedelta(days=1)
    return _scheduled_candidates(
        tomorrow.year,
        tomorrow.month,
        tomorrow.day,
        settings.run_at,
        local_tz,
    )[0]


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
    completed = 0
    last_attempt_date: date | None = None
    while iterations is None or completed < iterations:
        current = now_func()
        sleep(_seconds_until_next_run_after_date(current, settings, last_attempt_date))
        run_at = now_func()
        try:
            run_once(settings, run_at)
        except Exception:
            logger.exception("Daily sync failed; waiting for next scheduled run")
        finally:
            last_attempt_date = snapshot_date_for(run_at, settings.timezone_name)
        completed += 1
