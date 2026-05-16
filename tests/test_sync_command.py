from datetime import date

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from ps_price_sync.models import SyncRun
from ps_price_sync.services import sync_runner


@pytest.mark.django_db
def test_catalog_only_command_creates_succeeded_run(monkeypatch):
    def fake_run_catalog_sync(*, sync_run: SyncRun, page_limit: int, snapshot_date: date) -> None:
        del page_limit, snapshot_date
        sync_run.success_count = 3
        sync_run.save(update_fields=["success_count", "updated_at"])

    monkeypatch.setattr(sync_runner, "run_catalog_sync", fake_run_catalog_sync)

    call_command(
        "sync_ps_store",
        "--mode",
        "catalog-only",
        "--pages",
        "2",
        "--snapshot-date",
        "2026-05-16",
    )

    latest = SyncRun.objects.latest("created_at")
    assert latest.sync_type == "catalog_only"
    assert latest.status == "succeeded"
    assert latest.success_count == 3


@pytest.mark.django_db
def test_partial_failures_mark_run_partial(monkeypatch):
    def fake_run_snapshot_sync(*, sync_run: SyncRun, page_limit: int, snapshot_date: date) -> None:
        del page_limit, snapshot_date
        sync_run.success_count = 2
        sync_run.error_count = 1
        sync_run.save(update_fields=["success_count", "error_count", "updated_at"])

    monkeypatch.setattr(sync_runner, "run_snapshot_sync", fake_run_snapshot_sync)

    call_command(
        "sync_ps_store",
        "--mode",
        "snapshot-only",
        "--pages",
        "1",
        "--snapshot-date",
        "2026-05-16",
    )

    latest = SyncRun.objects.latest("created_at")
    assert latest.sync_type == "snapshot_only"
    assert latest.status == "partial"
    assert latest.success_count == 2
    assert latest.error_count == 1


def test_pages_must_be_positive(monkeypatch):
    del monkeypatch

    with pytest.raises(CommandError, match="--pages must be >= 1"):
        call_command(
            "sync_ps_store",
            "--mode",
            "snapshot-only",
            "--pages",
            "0",
            "--snapshot-date",
            "2026-05-16",
        )
