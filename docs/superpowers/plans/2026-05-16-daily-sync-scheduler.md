# Daily Sync Scheduler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a daily scheduler that runs full-catalog PlayStation Store syncs automatically through the existing Django sync boundary.

**Architecture:** Extend the existing sync command so it can traverse catalog pages until `CatalogPage.is_last == true` with a `max-pages` guard. Add a thin scheduler service and `run_daily_sync_scheduler` management command that computes the Taipei `snapshot_date`, sleeps until the configured daily time, and calls `sync_ps_store --until-last`. Keep crawler parsing, ingestion, and scheduler concerns separated.

**Tech Stack:** Python 3.12+, Django 5.2, SQLite, pytest, pytest-django, standard-library `zoneinfo`.

---

## File Structure

- Modify `src/ps_price_sync/services/ingestion.py`
  - Add a small `record_catalog_coverage()` helper that merges traversal coverage into `SyncRun.summary`.
  - Keep existing ingestion functions responsible for product and snapshot writes.
- Modify `src/ps_price_sync/services/sync_runner.py`
  - Add until-last traversal support to catalog, snapshot, and combined sync paths.
  - Add `MaxPagesExceededError`.
  - Record max-pages traversal failures as `SyncError` rows.
- Modify `src/ps_price_sync/management/commands/sync_ps_store.py`
  - Add `--until-last` and `--max-pages`.
  - Keep existing `--pages` behavior for bounded manual runs.
  - Preserve partial status when a guarded traversal fails after successful writes.
- Create `src/ps_price_sync/services/scheduler.py`
  - Parse scheduler environment settings.
  - Calculate next run time and snapshot date.
  - Call the existing sync command with until-last arguments.
- Create `src/ps_price_sync/management/commands/run_daily_sync_scheduler.py`
  - Long-running scheduler process.
  - Delegates all scheduling logic to `services.scheduler`.
- Modify `tests/test_ingestion_service.py`
  - Add summary coverage merge test.
- Modify `tests/test_sync_runner.py`
  - Add until-last traversal and max-pages guard tests.
- Modify `tests/test_sync_command.py`
  - Add command argument and exception status tests.
- Create `tests/test_scheduler_service.py`
  - Unit-test pure scheduler settings and timing helpers.
- Create `tests/test_scheduler_command.py`
  - Test management command wiring without entering a real infinite loop.
- Modify `README.md`
  - Add daily scheduler usage.

## Task 1: Catalog Coverage Summary Helper

**Files:**
- Modify: `src/ps_price_sync/services/ingestion.py`
- Test: `tests/test_ingestion_service.py`

- [ ] **Step 1: Write the failing coverage summary test**

Add this test near the existing summary tests in `tests/test_ingestion_service.py`:

```python
@pytest.mark.django_db
def test_record_catalog_coverage_merges_with_existing_summary() -> None:
    sync_run = SyncRun.objects.create(
        sync_type="catalog_and_snapshot",
        status="running",
        summary=json.dumps(
            {
                "observed_items": 48,
                "persisted_products": 47,
                "skipped_missing_product_id": 1,
            }
        ),
    )

    from ps_price_sync.services.ingestion import record_catalog_coverage

    record_catalog_coverage(
        sync_run=sync_run,
        pages_fetched=2,
        last_page_reached=True,
        max_pages_hit=False,
        last_page_number=2,
        catalog_total_count=48,
    )

    sync_run.refresh_from_db()
    assert json.loads(sync_run.summary) == {
        "observed_items": 48,
        "persisted_products": 47,
        "skipped_missing_product_id": 1,
        "pages_fetched": 2,
        "last_page_reached": True,
        "max_pages_hit": False,
        "last_page_number": 2,
        "catalog_total_count": 48,
    }
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
uv run --extra dev pytest tests/test_ingestion_service.py::test_record_catalog_coverage_merges_with_existing_summary -q
```

Expected: FAIL with `ImportError` or `AttributeError` for `record_catalog_coverage`.

- [ ] **Step 3: Implement the coverage helper**

In `src/ps_price_sync/services/ingestion.py`, add this helper after `_load_summary()`:

```python
def _load_summary_mapping(summary_text: str | None) -> dict[str, object]:
    if not summary_text:
        return {}
    try:
        parsed = json.loads(summary_text)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return dict(parsed)


def record_catalog_coverage(
    *,
    sync_run: SyncRun,
    pages_fetched: int,
    last_page_reached: bool,
    max_pages_hit: bool,
    last_page_number: int | None,
    catalog_total_count: int | None,
) -> None:
    summary = _load_summary_mapping(sync_run.summary)
    summary.update(
        {
            "pages_fetched": pages_fetched,
            "last_page_reached": last_page_reached,
            "max_pages_hit": max_pages_hit,
            "last_page_number": last_page_number,
            "catalog_total_count": catalog_total_count,
        }
    )
    sync_run.summary = json.dumps(summary)
    sync_run.updated_at = timezone.now()
    sync_run.save(update_fields=["summary", "updated_at"])
```

- [ ] **Step 4: Run the focused test and verify it passes**

Run:

```bash
uv run --extra dev pytest tests/test_ingestion_service.py::test_record_catalog_coverage_merges_with_existing_summary -q
```

Expected: PASS.

- [ ] **Step 5: Run existing ingestion tests**

Run:

```bash
uv run --extra dev pytest tests/test_ingestion_service.py -q
```

Expected: PASS. Existing exact summary assertions must remain unchanged unless the test explicitly calls `record_catalog_coverage()`.

- [ ] **Step 6: Commit**

```bash
git add src/ps_price_sync/services/ingestion.py tests/test_ingestion_service.py
git commit -m "feat: record catalog sync coverage summary"
```

## Task 2: Until-Last Traversal In Sync Runner

**Files:**
- Modify: `src/ps_price_sync/services/sync_runner.py`
- Test: `tests/test_sync_runner.py`

- [ ] **Step 1: Write failing test for combined sync until-last traversal**

Add this test to `tests/test_sync_runner.py` after `test_run_catalog_and_snapshot_sync_fetches_each_catalog_page_once`:

```python
@pytest.mark.django_db
def test_run_catalog_and_snapshot_sync_until_last_fetches_until_last_page(monkeypatch):
    fetched_pages: list[int] = []

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def fetch_catalog_page(self, page: int):
            fetched_pages.append(page)
            return f"https://store.playstation.com/zh-hant-tw/category/test/{page}", f"catalog-page-{page}"

    def fake_parse_catalog_page(html: str, source_url: str) -> CatalogPage:
        page_number = int(html.rsplit("-", maxsplit=1)[1])
        return CatalogPage(
            source_url=source_url,
            category_id="test",
            total_count=72,
            offset=(page_number - 1) * 24,
            size=24,
            is_last=page_number == 3,
            items=(
                CatalogItem(
                    concept_id=f"22311{page_number}",
                    name=f"Game {page_number}",
                    product_ids=(f"UP1821-PAGE{page_number}",),
                    image_url=None,
                    price=None,
                ),
            ),
        )

    def fake_ingest_catalog_page(*args, **kwargs):
        del args, kwargs
        return CatalogIngestionResult(
            observed_items=1,
            persisted_products=1,
            skipped_missing_product_id=0,
            observed_product_ids={"UP1821-PAGE"},
        )

    def fake_normalize_catalog_item_price(item: CatalogItem) -> NormalizedPrice:
        del item
        return NormalizedPrice(
            state=PriceState.PAID,
            currency="TWD",
            base_amount_cents=169000,
            discounted_amount_cents=169000,
            plus_amount_cents=None,
            base_display="NT$1,690",
            discounted_display="NT$1,690",
            discount_text=None,
            service_branding=(),
            upsell_text=None,
            source="catalog",
            raw_missing_reason=None,
        )

    def fake_choose_snapshot_source(item: CatalogItem, normalized_price: NormalizedPrice) -> SnapshotSourceDecision:
        del item, normalized_price
        return SnapshotSourceDecision(
            source="catalog",
            reason="catalog_price_snapshot",
            reason_codes=("clear_catalog_price", "product_ids_present"),
            normalized_state=PriceState.PAID,
            product_ids=("UP1821-PAGE",),
            missing_metadata_fields=(),
        )

    sync_run = SyncRun.objects.create(sync_type="catalog_and_snapshot", status="running")

    monkeypatch.setattr(sync_runner, "PlayStationStoreClient", lambda: FakeClient())
    monkeypatch.setattr(sync_runner, "parse_catalog_page", fake_parse_catalog_page)
    monkeypatch.setattr(sync_runner, "ingest_catalog_page", fake_ingest_catalog_page)
    monkeypatch.setattr(sync_runner, "normalize_catalog_item_price", fake_normalize_catalog_item_price)
    monkeypatch.setattr(sync_runner, "choose_snapshot_source", fake_choose_snapshot_source)
    monkeypatch.setattr(sync_runner, "ingest_catalog_snapshot", lambda **kwargs: object())
    monkeypatch.setattr(sync_runner, "finalize_catalog_visibility", lambda *args, **kwargs: None)

    sync_runner.run_catalog_and_snapshot_sync(
        sync_run=sync_run,
        page_limit=None,
        until_last=True,
        max_pages=10,
        snapshot_date=date(2026, 5, 16),
    )

    assert fetched_pages == [1, 2, 3]
```

- [ ] **Step 2: Write failing max-pages guard test**

Add this test to `tests/test_sync_runner.py`:

```python
@pytest.mark.django_db
def test_run_catalog_sync_until_last_records_error_when_max_pages_hit(monkeypatch):
    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def fetch_catalog_page(self, page: int):
            return f"https://store.playstation.com/zh-hant-tw/category/test/{page}", f"catalog-page-{page}"

    def fake_parse_catalog_page(html: str, source_url: str) -> CatalogPage:
        page_number = int(html.rsplit("-", maxsplit=1)[1])
        return CatalogPage(
            source_url=source_url,
            category_id="test",
            total_count=72,
            offset=(page_number - 1) * 24,
            size=24,
            is_last=False,
            items=(
                CatalogItem(
                    concept_id=f"22311{page_number}",
                    name=f"Game {page_number}",
                    product_ids=(f"UP1821-PAGE{page_number}",),
                    image_url=None,
                    price=None,
                ),
            ),
        )

    sync_run = SyncRun.objects.create(sync_type="catalog_only", status="running")
    finalize_calls: list[set[str]] = []

    monkeypatch.setattr(sync_runner, "PlayStationStoreClient", lambda: FakeClient())
    monkeypatch.setattr(sync_runner, "parse_catalog_page", fake_parse_catalog_page)
    monkeypatch.setattr(
        sync_runner,
        "finalize_catalog_visibility",
        lambda sync_run, observed_product_ids: finalize_calls.append(set(observed_product_ids)),
    )

    with pytest.raises(sync_runner.MaxPagesExceededError, match="max_pages=2"):
        sync_runner.run_catalog_sync(
            sync_run=sync_run,
            page_limit=None,
            until_last=True,
            max_pages=2,
            snapshot_date=date(2026, 5, 16),
        )

    sync_run.refresh_from_db()
    assert finalize_calls == []
    assert sync_run.error_count == 1
    assert json.loads(sync_run.summary) == {
        "observed_items": 2,
        "persisted_products": 2,
        "skipped_missing_product_id": 0,
        "pages_fetched": 2,
        "last_page_reached": False,
        "max_pages_hit": True,
        "last_page_number": 2,
        "catalog_total_count": 72,
    }
    assert SyncError.objects.filter(
        sync_run=sync_run,
        stage="catalog_traversal",
        error_type="MaxPagesExceededError",
    ).count() == 1
```

- [ ] **Step 3: Run the new sync runner tests and verify they fail**

Run:

```bash
uv run --extra dev pytest tests/test_sync_runner.py::test_run_catalog_and_snapshot_sync_until_last_fetches_until_last_page tests/test_sync_runner.py::test_run_catalog_sync_until_last_records_error_when_max_pages_hit -q
```

Expected: FAIL because `until_last`, `max_pages`, and `MaxPagesExceededError` do not exist yet.

- [ ] **Step 4: Implement runner support**

In `src/ps_price_sync/services/sync_runner.py`, update imports:

```python
import json
from ps_price_sync.services.ingestion import (
    finalize_catalog_visibility,
    ingest_catalog_page,
    ingest_catalog_snapshot,
    ingest_product_detail_snapshot,
    record_catalog_coverage,
)
```

Add this exception near the top:

```python
class MaxPagesExceededError(RuntimeError):
    pass
```

Add these helpers near `_increment_success()`:

```python
def _page_ceiling(*, page_limit: int | None, until_last: bool, max_pages: int | None) -> int:
    if until_last:
        if max_pages is None or max_pages < 1:
            raise ValueError("max_pages must be >= 1 when until_last is enabled")
        return max_pages
    if page_limit is None or page_limit < 1:
        raise ValueError("page_limit must be >= 1")
    return page_limit


def _record_max_pages_exceeded(
    *,
    sync_run: SyncRun,
    max_pages: int,
    pages_fetched: int,
    last_page_number: int | None,
    catalog_total_count: int | None,
) -> None:
    message = f"Catalog traversal reached max_pages={max_pages} without seeing is_last"
    SyncError.objects.create(
        sync_run=sync_run,
        stage="catalog_traversal",
        error_type="MaxPagesExceededError",
        error_message=message,
    )
    sync_run.error_count += 1
    sync_run.save(update_fields=["error_count", "updated_at"])
    record_catalog_coverage(
        sync_run=sync_run,
        pages_fetched=pages_fetched,
        last_page_reached=False,
        max_pages_hit=True,
        last_page_number=last_page_number,
        catalog_total_count=catalog_total_count,
    )
    raise MaxPagesExceededError(message)
```

Change the three public runner signatures to include defaults:

```python
def run_catalog_sync(
    *,
    sync_run: SyncRun,
    page_limit: int | None,
    snapshot_date: date,
    until_last: bool = False,
    max_pages: int | None = None,
) -> None:
```

```python
def run_snapshot_sync(
    *,
    sync_run: SyncRun,
    page_limit: int | None,
    snapshot_date: date,
    until_last: bool = False,
    max_pages: int | None = None,
) -> None:
```

```python
def run_catalog_and_snapshot_sync(
    *,
    sync_run: SyncRun,
    page_limit: int | None,
    snapshot_date: date,
    until_last: bool = False,
    max_pages: int | None = None,
) -> None:
```

Inside each function, replace `if page_limit < 1` and `range(1, page_limit + 1)` with this traversal shape:

```python
page_ceiling = _page_ceiling(page_limit=page_limit, until_last=until_last, max_pages=max_pages)
pages_fetched = 0
last_page_reached = False
last_page_number: int | None = None
catalog_total_count: int | None = None

with PlayStationStoreClient() as client:
    for page_number in range(1, page_ceiling + 1):
        source_url, html = client.fetch_catalog_page(page_number)
        parsed = parse_catalog_page(html, source_url=source_url)
        pages_fetched += 1
        last_page_number = page_number
        catalog_total_count = parsed.total_count

        # Keep each function's existing per-page ingestion and snapshot logic here.

        if parsed.is_last:
            last_page_reached = True
            if until_last:
                break

if until_last and not last_page_reached:
    _record_max_pages_exceeded(
        sync_run=sync_run,
        max_pages=page_ceiling,
        pages_fetched=pages_fetched,
        last_page_number=last_page_number,
        catalog_total_count=catalog_total_count,
    )

record_catalog_coverage(
    sync_run=sync_run,
    pages_fetched=pages_fetched,
    last_page_reached=last_page_reached,
    max_pages_hit=False,
    last_page_number=last_page_number,
    catalog_total_count=catalog_total_count,
)
```

Keep the existing `finalize_catalog_visibility()` call after the loop for catalog and combined modes only when traversal completed. For `until_last=True`, completion means `last_page_reached is True`; if max-pages is hit first, record the max-pages error and skip finalization so products from unvisited pages are not marked invisible.

- [ ] **Step 5: Run focused sync runner tests**

Run:

```bash
uv run --extra dev pytest tests/test_sync_runner.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ps_price_sync/services/sync_runner.py tests/test_sync_runner.py
git commit -m "feat: sync catalog pages until last page"
```

## Task 3: Extend `sync_ps_store` Command Flags

**Files:**
- Modify: `src/ps_price_sync/management/commands/sync_ps_store.py`
- Test: `tests/test_sync_command.py`

- [ ] **Step 1: Write failing command argument tests**

Add these tests to `tests/test_sync_command.py`:

```python
@pytest.mark.django_db
def test_until_last_command_uses_max_pages(monkeypatch):
    captured: dict[str, object] = {}

    def fake_run_catalog_and_snapshot_sync(
        *,
        sync_run: SyncRun,
        page_limit: int | None,
        snapshot_date: date,
        until_last: bool,
        max_pages: int,
    ) -> None:
        captured["sync_run_id"] = sync_run.id
        captured["page_limit"] = page_limit
        captured["snapshot_date"] = snapshot_date
        captured["until_last"] = until_last
        captured["max_pages"] = max_pages
        sync_run.success_count = 3
        sync_run.save(update_fields=["success_count", "updated_at"])

    monkeypatch.setattr(sync_runner, "run_catalog_and_snapshot_sync", fake_run_catalog_and_snapshot_sync)

    call_command(
        "sync_ps_store",
        "--mode",
        "catalog-and-snapshot",
        "--until-last",
        "--max-pages",
        "9",
        "--snapshot-date",
        "2026-05-16",
    )

    assert captured["page_limit"] is None
    assert captured["snapshot_date"] == date(2026, 5, 16)
    assert captured["until_last"] is True
    assert captured["max_pages"] == 9


def test_max_pages_must_be_positive_when_until_last_enabled():
    with pytest.raises(CommandError, match="--max-pages must be >= 1"):
        call_command(
            "sync_ps_store",
            "--mode",
            "catalog-only",
            "--until-last",
            "--max-pages",
            "0",
            "--snapshot-date",
            "2026-05-16",
        )
```

- [ ] **Step 2: Write failing exception status test**

Add this test to `tests/test_sync_command.py`:

```python
@pytest.mark.django_db
def test_until_last_guard_failure_preserves_partial_status(monkeypatch):
    def fake_run_catalog_sync(
        *,
        sync_run: SyncRun,
        page_limit: int | None,
        snapshot_date: date,
        until_last: bool,
        max_pages: int,
    ) -> None:
        del page_limit, snapshot_date, until_last, max_pages
        sync_run.success_count = 2
        sync_run.error_count = 1
        sync_run.save(update_fields=["success_count", "error_count", "updated_at"])
        raise sync_runner.MaxPagesExceededError("Catalog traversal reached max_pages=2 without seeing is_last")

    monkeypatch.setattr(sync_runner, "run_catalog_sync", fake_run_catalog_sync)

    with pytest.raises(sync_runner.MaxPagesExceededError):
        call_command(
            "sync_ps_store",
            "--mode",
            "catalog-only",
            "--until-last",
            "--max-pages",
            "2",
            "--snapshot-date",
            "2026-05-16",
        )

    latest = SyncRun.objects.latest("created_at")
    assert latest.status == "partial"
    assert latest.success_count == 2
    assert latest.error_count == 1
```

- [ ] **Step 3: Run focused command tests and verify they fail**

Run:

```bash
uv run --extra dev pytest tests/test_sync_command.py -q
```

Expected: FAIL because `--until-last` and `--max-pages` are unknown.

- [ ] **Step 4: Implement command arguments and status handling**

In `src/ps_price_sync/management/commands/sync_ps_store.py`, change argument setup:

```python
parser.add_argument("--pages", type=int, default=None)
parser.add_argument("--until-last", action="store_true")
parser.add_argument("--max-pages", type=int, default=500)
parser.add_argument("--snapshot-date", type=date.fromisoformat, required=True)
```

In `handle()`, replace pages validation with:

```python
pages: int | None = options["pages"]
until_last: bool = options["until_last"]
max_pages: int = options["max_pages"]
snapshot_date: date = options["snapshot_date"]

if until_last:
    if max_pages < 1:
        raise CommandError("--max-pages must be >= 1")
    page_limit = None
else:
    page_limit = pages if pages is not None else 1
    if page_limit < 1:
        raise CommandError("--pages must be >= 1")
```

Pass arguments to runners:

```python
runner_kwargs = {
    "sync_run": sync_run,
    "page_limit": page_limit,
    "snapshot_date": snapshot_date,
}
if until_last:
    runner_kwargs["until_last"] = True
    runner_kwargs["max_pages"] = max_pages
```

Use `runner_kwargs` for each runner call:

```python
sync_runner.run_catalog_and_snapshot_sync(**runner_kwargs)
sync_runner.run_catalog_sync(**runner_kwargs)
sync_runner.run_snapshot_sync(**runner_kwargs)
```

Replace the existing `except Exception:` block with:

```python
except Exception:
    sync_run.refresh_from_db()
    sync_run.status = _derive_interrupted_status(sync_run.success_count, sync_run.error_count)
    sync_run.finished_at = sync_runner.sync_now()
    sync_run.save(update_fields=["status", "finished_at", "updated_at"])
    raise
```

Add this helper below `_derive_status()`:

```python
def _derive_interrupted_status(success_count: int, error_count: int) -> str:
    if success_count:
        return "partial"
    if error_count:
        return "failed"
    return "failed"
```

- [ ] **Step 5: Run command tests**

Run:

```bash
uv run --extra dev pytest tests/test_sync_command.py -q
```

Expected: PASS.

- [ ] **Step 6: Run sync runner tests again**

Run:

```bash
uv run --extra dev pytest tests/test_sync_runner.py tests/test_sync_command.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/ps_price_sync/management/commands/sync_ps_store.py tests/test_sync_command.py
git commit -m "feat: add until-last sync command mode"
```

## Task 4: Scheduler Service

**Files:**
- Create: `src/ps_price_sync/services/scheduler.py`
- Test: `tests/test_scheduler_service.py`

- [ ] **Step 1: Write failing scheduler service tests**

Create `tests/test_scheduler_service.py`:

```python
from __future__ import annotations

from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta
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


def test_run_scheduler_loop_runs_one_iteration(monkeypatch) -> None:
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
```

- [ ] **Step 2: Run scheduler service tests and verify they fail**

Run:

```bash
uv run --extra dev pytest tests/test_scheduler_service.py -q
```

Expected: FAIL with import error for `ps_price_sync.services.scheduler`.

- [ ] **Step 3: Implement scheduler service**

Create `src/ps_price_sync/services/scheduler.py`:

```python
from __future__ import annotations

from collections.abc import Callable
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta
import os
import time as time_module
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
    values = os.environ if environ is None else environ
    mode = values.get("PS_PRICE_SYNC_MODE", "catalog-and-snapshot")
    if mode not in VALID_SYNC_MODES:
        raise ValueError(f"PS_PRICE_SYNC_MODE must be one of {sorted(VALID_SYNC_MODES)}")

    max_pages_raw = values.get("PS_PRICE_SYNC_MAX_PAGES", "500")
    try:
        max_pages = int(max_pages_raw)
    except ValueError as exc:
        raise ValueError("PS_PRICE_SYNC_MAX_PAGES must be an integer") from exc
    if max_pages < 1:
        raise ValueError("PS_PRICE_SYNC_MAX_PAGES must be >= 1")

    timezone_name = values.get("PS_PRICE_SYNC_TIMEZONE", "Asia/Taipei")
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("PS_PRICE_SYNC_TIMEZONE must be a valid IANA timezone") from exc

    run_at = _parse_hhmm(values.get("PS_PRICE_SYNC_AT", "03:30"))

    return SchedulerSettings(
        mode=mode,
        max_pages=max_pages,
        timezone_name=timezone_name,
        run_at=run_at,
    )


def _parse_hhmm(value: str) -> time:
    try:
        hour_text, minute_text = value.split(":", maxsplit=1)
        hour = int(hour_text)
        minute = int(minute_text)
        return time(hour=hour, minute=minute)
    except (TypeError, ValueError) as exc:
        raise ValueError("PS_PRICE_SYNC_AT must use HH:MM format") from exc


def snapshot_date_for(now: datetime, timezone_name: str) -> date:
    return now.astimezone(ZoneInfo(timezone_name)).date()


def next_run_at(now: datetime, settings: SchedulerSettings) -> datetime:
    local_now = now.astimezone(ZoneInfo(settings.timezone_name))
    candidate = datetime.combine(local_now.date(), settings.run_at, tzinfo=ZoneInfo(settings.timezone_name))
    if candidate <= local_now:
        candidate = candidate + timedelta(days=1)
    return candidate


def seconds_until_next_run(now: datetime, settings: SchedulerSettings) -> float:
    return max(0.0, (next_run_at(now, settings) - now.astimezone(ZoneInfo(settings.timezone_name))).total_seconds())


def run_sync_once(settings: SchedulerSettings, now: datetime | None = None) -> None:
    current = timezone.now() if now is None else now
    snapshot_date = snapshot_date_for(current, settings.timezone_name)
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
    sleep: Callable[[float], None] = time_module.sleep,
    now_func: Callable[[], datetime] = timezone.now,
    run_once: Callable[[SchedulerSettings, datetime], None] = run_sync_once,
    iterations: int | None = None,
) -> None:
    completed = 0
    while iterations is None or completed < iterations:
        sleep_seconds = seconds_until_next_run(now_func(), settings)
        sleep(sleep_seconds)
        run_once(settings, now_func())
        completed += 1
```

- [ ] **Step 4: Run scheduler service tests**

Run:

```bash
uv run --extra dev pytest tests/test_scheduler_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ps_price_sync/services/scheduler.py tests/test_scheduler_service.py
git commit -m "feat: add daily sync scheduler service"
```

## Task 5: Scheduler Management Command

**Files:**
- Create: `src/ps_price_sync/management/commands/run_daily_sync_scheduler.py`
- Test: `tests/test_scheduler_command.py`

- [ ] **Step 1: Write failing scheduler command test**

Create `tests/test_scheduler_command.py`:

```python
from __future__ import annotations

from datetime import time

from django.core.management import call_command

from ps_price_sync.services import scheduler


def test_run_daily_sync_scheduler_loads_settings_and_starts_loop(monkeypatch):
    captured: dict[str, object] = {}

    def fake_load_settings():
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
```

- [ ] **Step 2: Run scheduler command test and verify it fails**

Run:

```bash
uv run --extra dev pytest tests/test_scheduler_command.py -q
```

Expected: FAIL because the command does not exist.

- [ ] **Step 3: Implement scheduler command**

Create `src/ps_price_sync/management/commands/run_daily_sync_scheduler.py`:

```python
from __future__ import annotations

from django.core.management.base import BaseCommand

from ps_price_sync.services import scheduler


class Command(BaseCommand):
    help = "Run the daily PlayStation Store sync scheduler loop."

    def handle(self, *args, **options) -> None:
        del args, options
        settings = scheduler.load_settings()
        self.stdout.write(
            "Starting daily sync scheduler "
            f"mode={settings.mode} "
            f"max_pages={settings.max_pages} "
            f"timezone={settings.timezone_name} "
            f"run_at={settings.run_at.strftime('%H:%M')}"
        )
        scheduler.run_scheduler_loop(settings)
```

- [ ] **Step 4: Run scheduler command test**

Run:

```bash
uv run --extra dev pytest tests/test_scheduler_command.py -q
```

Expected: PASS.

- [ ] **Step 5: Run all scheduler tests**

Run:

```bash
uv run --extra dev pytest tests/test_scheduler_service.py tests/test_scheduler_command.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ps_price_sync/management/commands/run_daily_sync_scheduler.py tests/test_scheduler_command.py
git commit -m "feat: add daily sync scheduler command"
```

## Task 6: README Usage And Full Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add scheduler usage docs**

In `README.md`, add this section after `Django setup and sync usage`:

````markdown
## Daily scheduler usage

The scheduler runs the existing Django sync command once per day. It defaults to a full catalog traversal with a safety guard:

```bash
PS_PRICE_SYNC_AT=03:30 \
PS_PRICE_SYNC_TIMEZONE=Asia/Taipei \
PS_PRICE_SYNC_MODE=catalog-and-snapshot \
PS_PRICE_SYNC_MAX_PAGES=500 \
uv run python manage.py run_daily_sync_scheduler
```

The scheduler calls:

```bash
uv run python manage.py sync_ps_store --mode catalog-and-snapshot --until-last --max-pages 500 --snapshot-date <yyyy-mm-dd>
```

`PS_PRICE_SYNC_MAX_PAGES` is a guardrail, not the target coverage. The sync stops when the parsed catalog page reports `is_last`.
````

- [ ] **Step 2: Run full verification**

Run:

```bash
uv run --extra dev pytest -q
```

Expected: PASS with all tests green.

- [ ] **Step 3: Run placeholder scan**

Run:

```bash
uv run python -c 'from pathlib import Path; patterns=["TB"+"D","TO"+"DO","implement "+"later","待"+"定","未"+"定","之後"+"再","先"+"留","?"+"?"]; files=[Path("docs/superpowers/plans/2026-05-16-daily-sync-scheduler.md"),Path("docs/superpowers/specs/2026-05-16-daily-sync-scheduler-design.md"),Path("README.md")]; hits=[(str(path), pattern) for path in files for pattern in patterns if path.exists() and pattern in path.read_text()]; print(hits); raise SystemExit(1 if hits else 0)'
```

Expected: no matches.

- [ ] **Step 4: Check git status**

Run:

```bash
git status --short
```

Expected: only README or intended implementation files are modified before the final commit.

- [ ] **Step 5: Commit docs**

```bash
git add README.md
git commit -m "docs: add daily scheduler usage"
```

- [ ] **Step 6: Final implementation sanity checklist**

Confirm each item before reporting completion:

- `sync_ps_store --pages N` still works for bounded manual runs.
- `sync_ps_store --until-last --max-pages N` stops at `is_last`.
- Max-pages guard creates a `SyncError` and leaves `SyncRun.status` as `partial` when prior writes succeeded.
- `run_daily_sync_scheduler` starts the long-running scheduler loop.
- Scheduler environment defaults are `catalog-and-snapshot`, `500`, `Asia/Taipei`, and `03:30`.
- Full pytest passes.
