import ipaddress

from django.http import HttpRequest

from script_consent.conf import app_settings


def anonymize_ip(ip: str | None) -> str | None:
    if not ip:
        return None

    if not app_settings.ANONYMIZE_IP:
        return ip

    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return None

    if isinstance(addr, ipaddress.IPv4Address):
        parts = str(addr).split(".")
        parts[-1] = "0"
        return ".".join(parts)

    packed = bytearray(addr.packed)
    for i in range(6, 16):
        packed[i] = 0

    return str(ipaddress.IPv6Address(bytes(packed)))


def get_client_ip(request: HttpRequest) -> str | None:
    """
    Client IP for audit log.

    By default uses REMOTE_ADDR only. Set TRUST_X_FORWARDED_FOR=True only when
    a reverse proxy overwrites X-Forwarded-For (spoofing otherwise weakens audit).
    """
    if app_settings.TRUST_X_FORWARDED_FOR:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")

        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR")

    else:
        ip = request.META.get("REMOTE_ADDR")

    return anonymize_ip(ip)
