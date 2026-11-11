from celery import shared_task
from advanced_security.models import SecurityIncident
from advanced_security.scanners.port_scanner import scan_sensitive_ports
from advanced_security.scanners.malware import check_malware_list
from websites.models import Website


@shared_task
def run_security_scan(website_id: int) -> dict:
    website = Website.objects.get(id=website_id)
    incidents = 0

    open_ports = scan_sensitive_ports(website.domain)
    for p in open_ports:
        _, created = SecurityIncident.objects.get_or_create(
            website=website,
            incident_type=SecurityIncident.IncidentType.OPEN_PORT,
            evidence={"port": p["port"], "service": p["service"]},
            defaults={
                "severity": SecurityIncident.Severity.HIGH,
                "title": f"Database / Mgmt port {p['port']} exposed",
                "description": f"The port {p['port']} ({p['service']}) was found publicly accessible.",
            },
        )
        if created:
            incidents += 1

    malware_res = check_malware_list(website.domain)
    if malware_res.get("threat_found"):
        _, created = SecurityIncident.objects.get_or_create(
            website=website,
            incident_type=SecurityIncident.IncidentType.MALWARE,
            defaults={
                "severity": SecurityIncident.Severity.CRITICAL,
                "title": "Domain blacklisted for malware",
                "description": "This website is listed as propagating malware or scams.",
                "evidence": malware_res.get("sources", {}),
            },
        )
        if created:
            incidents += 1

    return {"incidents_created": incidents}
