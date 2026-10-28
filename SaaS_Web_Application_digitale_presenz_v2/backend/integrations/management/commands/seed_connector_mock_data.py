"""Generate mock encrypted connector rows for rotation/load checks."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from integrations.services.mock_data import seed_mock_connector_data


class Command(BaseCommand):
    help = (
        "Create several mock organizations and encrypted OAuth connections. "
        "Useful for exercising rotate_connector_keys before real traffic."
    )

    def add_arguments(self, parser):
        parser.add_argument("--organizations", type=int, default=5)
        parser.add_argument("--connections-per-org", type=int, default=12)
        parser.add_argument("--prefix", default="loadtest")

    def handle(self, *args, **options):
        try:
            created = seed_mock_connector_data(
                organizations=options["organizations"],
                connections_per_org=options["connections_per_org"],
                prefix=options["prefix"],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from None

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(created)} mock OAuth connection(s) across "
                f"{options['organizations']} organization(s)."
            )
        )
