from urllib.parse import urlparse
import socket
import ipaddress


def hostname_resolves_to_private(url: str) -> bool:
    """Return True if the URL's hostname resolves to a private/loopback/link-local IP.

    This resolves DNS (both A and AAAA) and checks each address for being
    loopback, private (RFC1918 / fc00::/7), or link-local (169.254.0.0/16, fe80::/10).
    If the hostname cannot be resolved, the function returns False.
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or url
        if not hostname:
            return False

        # quick rejects for obvious local names
        if hostname.lower() in ("localhost",):
            return True

        infos = socket.getaddrinfo(hostname, None)
    except Exception:
        # DNS failure or invalid hostname — do not treat as private here
        return False

    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue

        if ip.is_loopback or ip.is_private or ip.is_link_local:
            return True

    return False
