from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand, CommandError

from ps_price_sync.models import SyncRun
from ps_price_sync.services import sync_runner


class Command(BaseCommand):
    help = "Run catalog and/or snapshot synchronization jobs for PlayStation Store data."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--mode",
            choices=("catalog-only", "snapshot-only", "catalog-and-snapshot"),
            required=True,
        )
        parser.add_argument("--pages", type=int, default=None)
        parser.add_argument("--until-last", action="store_true")
        parser.add_argument("--max-pages", type=int, default=500)
        parser.add_argument("--snapshot-date", type=date.fromisoformat, required=True)

    def handle(
        self,
        *args,
        **options,
    ) -> None:
        mode: str = options["mode"]
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

        sync_run = SyncRun.objects.create(
            sync_type=mode.replace("-", "_"),
            status="running",
            started_at=sync_runner.sync_now(),
            summary="{}",
        )

        runner_kwargs = {
            "sync_run": sync_run,
            "page_limit": page_limit,
            "snapshot_date": snapshot_date,
        }
        if until_last:
            runner_kwargs["until_last"] = True
            runner_kwargs["max_pages"] = max_pages

        try:
            if mode in {"catalog-only", "catalog-and-snapshot"}:
                if mode == "catalog-and-snapshot":
                    sync_runner.run_catalog_and_snapshot_sync(**runner_kwargs)
                else:
                    sync_runner.run_catalog_sync(**runner_kwargs)

            elif mode == "snapshot-only":
                sync_runner.run_snapshot_sync(**runner_kwargs)
        except Exception:
            sync_run.refresh_from_db()
            sync_run.status = _derive_interrupted_status(
                sync_run.success_count,
                sync_run.error_count,
            )
            sync_run.finished_at = sync_runner.sync_now()
            sync_run.save(update_fields=["status", "finished_at", "updated_at"])
            raise

        sync_run.status = _derive_status(sync_run.success_count, sync_run.error_count)
        sync_run.finished_at = sync_runner.sync_now()
        sync_run.save(update_fields=["status", "finished_at", "updated_at"])


def _derive_status(success_count: int, error_count: int) -> str:
    if error_count and success_count:
        return "partial"
    if error_count:
        return "failed"
    return "succeeded"


def _derive_interrupted_status(success_count: int, error_count: int) -> str:
    if success_count:
        return "partial"
    if error_count:
        return "failed"
    return "failed"
