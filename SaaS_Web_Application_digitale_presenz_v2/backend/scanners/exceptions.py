"""Exceptions for the Scanner Engine."""


class ScannerError(Exception):
    """Base exception for all scanner errors."""


class ScannerUnavailableError(ScannerError):
    """Raised when a required external binary is not installed."""

    def __init__(self, scanner_name: str, binary: str) -> None:
        self.scanner_name = scanner_name
        self.binary = binary
        super().__init__(
            f"Scanner '{scanner_name}' is unavailable: binary '{binary}' not found."
        )


class ScannerTimeoutError(ScannerError):
    """Raised when a scanner exceeds its configured timeout."""

    def __init__(self, scanner_name: str, timeout_s: int) -> None:
        self.scanner_name = scanner_name
        self.timeout_s = timeout_s
        super().__init__(f"Scanner '{scanner_name}' timed out after {timeout_s}s.")


class ScannerOutputTooLargeError(ScannerError):
    """Raised when scanner output exceeds the configured limit."""

    def __init__(self, scanner_name: str, max_bytes: int) -> None:
        self.scanner_name = scanner_name
        self.max_bytes = max_bytes
        super().__init__(f"Scanner '{scanner_name}' output exceeded {max_bytes} bytes.")


class TargetValidationError(ScannerError):
    """Raised when the scan target fails security validation.

    This wraps ``core.security.DomainValidationError`` and
    ``core.security.SSRFBlockedError`` in a scanner-layer exception so
    individual scanner implementations don't need to import from ``core``.
    """
