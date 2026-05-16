from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from ps_price_sync.services import scheduler


class Command(BaseCommand):
    help = "Run the daily PlayStation Store sync scheduler loop."

    def handle(self, *args, **options) -> None:
        del args, options
        try:
            settings = scheduler.load_settings()
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            (
                "Starting daily sync scheduler with "
                f"mode={settings.mode}, "
                f"max_pages={settings.max_pages}, "
                f"timezone={settings.timezone_name}, "
                f"run_at={settings.run_at:%H:%M}"
            )
        )

        scheduler.run_scheduler_loop(settings)
