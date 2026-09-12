"""Nmap XML output parser.

Parses ``nmap -oX -`` (XML to stdout) output into a list of finding dicts.

Example fixture for tests::

    <?xml version="1.0"?>
    <nmaprun ...>
      <host>
        <address addr="93.184.216.34" addrtype="ipv4"/>
        <ports>
          <port protocol="tcp" portid="80">
            <state state="open" .../>
            <service name="http" product="Apache" version="2.4.57" .../>
          </port>
          <port protocol="tcp" portid="443">
            <state state="open" .../>
            <service name="https" product="nginx" .../>
          </port>
        </ports>
      </host>
    </nmaprun>
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any


def parse_nmap_xml(output: str) -> list[dict[str, Any]]:
    """Parse Nmap XML output and return a list of port/service finding dicts.

    Returns an empty list on parse failure (graceful degradation).
    """
    if not output.strip():
        return []

    findings: list[dict[str, Any]] = []

    try:
        root = ET.fromstring(output)
    except ET.ParseError:
        return []

    for host in root.findall("host"):
        # Extract host address
        addr_el = host.find("address[@addrtype='ipv4']")
        if addr_el is None:
            addr_el = host.find("address")
        ip_address = addr_el.get("addr", "unknown") if addr_el is not None else "unknown"

        # Host status
        status_el = host.find("status")
        host_state = status_el.get("state", "unknown") if status_el is not None else "unknown"

        # Ports
        ports_el = host.find("ports")
        if ports_el is None:
            continue

        for port_el in ports_el.findall("port"):
            portid = port_el.get("portid", "0")
            protocol = port_el.get("protocol", "tcp")

            state_el = port_el.find("state")
            port_state = state_el.get("state", "unknown") if state_el is not None else "unknown"

            service_el = port_el.find("service")
            service_info: dict[str, str] = {}
            if service_el is not None:
                service_info = {
                    "name": service_el.get("name", ""),
                    "product": service_el.get("product", ""),
                    "version": service_el.get("version", ""),
                    "extra_info": service_el.get("extrainfo", ""),
                    "tunnel": service_el.get("tunnel", ""),
                }

            # Scripts (NSE results)
            scripts: list[dict[str, str]] = []
            for script_el in port_el.findall("script"):
                scripts.append({
                    "id": script_el.get("id", ""),
                    "output": script_el.get("output", ""),
                })

            findings.append({
                "type": "port",
                "ip_address": ip_address,
                "host_state": host_state,
                "protocol": protocol,
                "port": int(portid),
                "state": port_state,
                "service": service_info,
                "scripts": scripts,
            })

    return findings


def parse_nmap_greppable(output: str) -> list[dict[str, Any]]:
    """Parse Nmap greppable output (``-oG``).

    Fallback parser when XML output is not available.
    """
    findings: list[dict[str, Any]] = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "Ports:" in line:
            parts = line.split("\t")
            ip = ""
            ports_str = ""
            for part in parts:
                part = part.strip()
                if part.startswith("Host:"):
                    ip = part.split()[1] if len(part.split()) > 1 else ""
                elif part.startswith("Ports:"):
                    ports_str = part[6:].strip()

            for port_entry in ports_str.split(","):
                port_entry = port_entry.strip()
                if not port_entry:
                    continue
                tokens = port_entry.split("/")
                if len(tokens) >= 4:
                    findings.append({
                        "type": "port",
                        "ip_address": ip,
                        "port": int(tokens[0]) if tokens[0].isdigit() else 0,
                        "state": tokens[1],
                        "protocol": tokens[2],
                        "service": {"name": tokens[4] if len(tokens) > 4 else ""},
                        "scripts": [],
                    })

    return findings
