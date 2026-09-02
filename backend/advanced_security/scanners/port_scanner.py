import socket

SENSITIVE_PORTS = {21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 3306: "MySQL", 5432: "PostgreSQL", 6379: "Redis"}

def scan_sensitive_ports(domain: str) -> list[dict]:
    open_ports = []
    try:
        ip = socket.gethostbyname(domain)
    except socket.gaierror:
        return []
    
    for port, service in SENSITIVE_PORTS.items():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        if s.connect_ex((ip, port)) == 0:
            open_ports.append({"port": port, "service": service})
        s.close()
    return open_ports
