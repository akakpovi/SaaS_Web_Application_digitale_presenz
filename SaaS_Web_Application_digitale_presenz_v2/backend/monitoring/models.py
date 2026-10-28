import random
from datetime import timedelta
from typing import Final

from django.db import models
from django.utils import timezone

from websites.models import Website


INTERVAL_MAP: Final[dict[str, timedelta]] = {
    "5m":  timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "30m": timedelta(minutes=30),
    "1h":  timedelta(hours=1),
    "6h":  timedelta(hours=6),
    "24h": timedelta(hours=24),
}


class MonitoringConfig(models.Model):
    class ScanPolicy(models.TextChoices):
        """Which scan type the scheduler launches.

        ``health`` is the historical behaviour (internal, passive checks).
        ``security`` adds the external tools (ZAP, Nuclei, nmap, …) and
        ``full`` runs both.  Active scanners are opt-in per website because
        they generate real traffic against the customer's site.
        """

        HEALTH = "health", "Health checks only"
        SECURITY = "security", "Security scanners (ZAP, Nuclei, …)"
        FULL = "full", "Health + security"

    class Interval(models.TextChoices):
        FIVE_MIN    = "5m",  "Every 5 minutes"
        FIFTEEN_MIN = "15m", "Every 15 minutes"
        THIRTY_MIN  = "30m", "Every 30 minutes"
        ONE_HOUR    = "1h",  "Every hour"
        SIX_HOURS   = "6h",  "Every 6 hours"
        TWENTY_FOUR = "24h", "Every 24 hours"

    website = models.OneToOneField(
        Website,
        on_delete=models.CASCADE,
        related_name="monitoring_config",
    )
    # Continuous monitoring is opt-in: a website is created with monitoring
    # off and no schedule.  The scheduler only picks up a config once the
    # owner explicitly activates it (after the first scan, or from the
    # monitoring page), so no site is scanned repeatedly without consent.
    enabled = models.BooleanField(default=False)
    interval = models.CharField(
        max_length=4,
        choices=Interval.choices,
        default=Interval.TWENTY_FOUR,
    )
    scan_type = models.CharField(
        max_length=16,
        choices=ScanPolicy.choices,
        default=ScanPolicy.HEALTH,
        help_text="Scan type launched by the scheduler for this website.",
    )
    last_scan_at = models.DateTimeField(null=True, blank=True)
    next_scan_at = models.DateTimeField(null=True, blank=True)
    consecutive_failures = models.IntegerField(default=0)
    escalation_level = models.IntegerField(
        default=0,
        help_text="0=ok, 1=warning, 2=critical",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["enabled", "next_scan_at"])]
        verbose_name = "Monitoring Config"
        verbose_name_plural = "Monitoring Configs"

    def __str__(self) -> str:
        return f"MonitoringConfig({self.website.domain}, {self.interval})"

    def schedule_next_scan(
        self,
        now: timezone.datetime | None = None,
        jitter_max_minutes: int = 5,
    ) -> None:
        now = now or timezone.now()
        interval_td = INTERVAL_MAP.get(self.interval, timedelta(hours=24))
        jitter = timedelta(minutes=random.randint(0, jitter_max_minutes))
        self.last_scan_at = now
        self.next_scan_at = now + interval_td + jitter
        self.save(update_fields=["last_scan_at", "next_scan_at", "updated_at"])

    def record_failure(self) -> None:
        self.consecutive_failures += 1
        self.escalation_level = 2 if self.consecutive_failures >= 3 else 1
        self.save(update_fields=["consecutive_failures", "escalation_level", "updated_at"])

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.escalation_level = 0
        self.save(update_fields=["consecutive_failures", "escalation_level", "updated_at"])
