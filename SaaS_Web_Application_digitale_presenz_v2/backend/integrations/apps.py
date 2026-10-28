from django.apps import AppConfig


class IntegrationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "integrations"
    verbose_name = "Social integrations"

    def ready(self) -> None:
        # Importing the module registers the fail-closed KEK system check.
        from . import checks  # noqa: F401
