from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from alerts.models import Alert
    from accounts.models import User


class NotificationProvider(ABC):
    def __init__(self, config: dict) -> None:
        self.config = config

    @abstractmethod
    def send(self, alert: "Alert", user: "User") -> bool:
        """Send notification. Returns True if successful."""
        ...

    @abstractmethod
    def validate_config(self) -> list[str]:
        """Return list of validation errors. Empty = valid."""
        ...
