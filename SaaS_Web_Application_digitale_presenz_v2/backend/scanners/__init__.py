"""Scanners package.

Imports all scanner instances and registers them with the ScannerRegistry.

Existing internal scanners (website, ssl, dns, etc.) are registered as-is
and keep backward compatibility.  External tool adapters are registered
when available.
"""

# --- Internal Python scanners (always available) ---
from .website import website_scanner
from .ssl import ssl_scanner
from .dns import dns_scanner
from .email_security import email_security_scanner
from .security_headers import security_headers_scanner
from .performance import performance_scanner
from .uptime import uptime_scanner
from .reviews import reviews_scanner

# --- External tool adapters (graceful degradation if binary missing) ---
from .implementations.nmap import nmap_scanner
from .implementations.nikto import nikto_scanner
from .implementations.nuclei import nuclei_scanner
from .implementations.whatweb import whatweb_scanner
from .implementations.testssl import testssl_scanner
from .implementations.dnsrecon import dnsrecon_scanner
from .implementations.gobuster import gobuster_scanner
from .implementations.feroxbuster import feroxbuster_scanner
from .implementations.zap import zap_scanner
from .implementations.lighthouse import lighthouse_scanner

# --- Registry ---
from .registry import ScannerRegistry

# Register all internal scanners.
for _scanner in [
    website_scanner,
    ssl_scanner,
    dns_scanner,
    email_security_scanner,
    security_headers_scanner,
    performance_scanner,
    uptime_scanner,
    # reviews_scanner is a legacy adapter — register but don't run in orchestrator
    reviews_scanner,
]:
    ScannerRegistry.register(_scanner)

# Register external tool adapters.
for _scanner in [
    nmap_scanner,
    nikto_scanner,
    nuclei_scanner,
    whatweb_scanner,
    testssl_scanner,
    dnsrecon_scanner,
    gobuster_scanner,
    feroxbuster_scanner,
    zap_scanner,
    lighthouse_scanner,
]:
    ScannerRegistry.register(_scanner)


__all__ = [
    # Internal
    "website_scanner",
    "ssl_scanner",
    "dns_scanner",
    "email_security_scanner",
    "security_headers_scanner",
    "performance_scanner",
    "uptime_scanner",
    "reviews_scanner",
    # External
    "nmap_scanner",
    "nikto_scanner",
    "nuclei_scanner",
    "whatweb_scanner",
    "testssl_scanner",
    "dnsrecon_scanner",
    "gobuster_scanner",
    "feroxbuster_scanner",
    "zap_scanner",
    "lighthouse_scanner",
    # Registry
    "ScannerRegistry",
]
