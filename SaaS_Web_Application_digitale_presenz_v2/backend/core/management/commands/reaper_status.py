"""Print the reaper counters recorded by the Celery beat sweep."""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from core.reaper_metrics import read_reaper_metrics


class Command(BaseCommand):
    help = (
        "Show how many AI runs/scans/journeys each reaper closed and when "
        "its last tick ran.  Reads the shared cache (Redis in normal "
        "deployments)."
    )

    def handle(self, *args, **options):
        self.stdout.write(json.dumps(read_reaper_metrics(), indent=2, sort_keys=True))
