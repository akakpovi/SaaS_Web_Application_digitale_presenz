from django.apps import AppConfig


class AlertsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "alerts"
    verbose_name = "Alerts"

    def ready(self) -> None:
        import alerts.signals  # noqa: F401
