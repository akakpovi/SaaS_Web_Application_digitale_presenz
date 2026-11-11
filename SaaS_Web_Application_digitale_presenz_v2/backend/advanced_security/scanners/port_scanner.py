import logging
import socket

from core.security import DomainValidationError, resolve_public_ip

logger = logging.getLogger(__name__)

SENSITIVE_PORTS = {
    21: "FTP",
    22: "SSH",
    23: "Telnet",
    25: "SMTP",
    3306: "MySQL",
    5432: "PostgreSQL",
    6379: "Redis",
}


def scan_sensitive_ports(domain: str) -> list[dict]:
    """Probe a publicly-routable host for exposed management/database ports.

    The target is validated through ``core.security`` (which uses
    ``validate_domain_for_scan`` + DNS resolution checks) so that raw IP
    literals, internal hostnames and hosts resolving to private, loopback,
    link-local or metadata addresses are refused before any TCP connection.
    """
    try:
        ip = resolve_public_ip(domain)
    except (DomainValidationError, socket.gaierror):
        logger.warning("port_scan_blocked", extra={"domain": domain})
        return []

    open_ports = []
    for port, service in SENSITIVE_PORTS.items():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        try:
            if s.connect_ex((ip, port)) == 0:
                open_ports.append({"port": port, "service": service})
        finally:
            s.close()
    return open_ports
