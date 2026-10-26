"""Protected IP addresses and subnet allowlist."""

from __future__ import annotations

import ipaddress

# Built-in critical protected infrastructure addresses that must never be targeted for rate-limiting
PROTECTED_IPS: set[str] = {
    "127.0.0.1",
    "::1",
    "0.0.0.0",
    "1.1.1.1",
    "8.8.8.8",
    "8.8.4.4",
}

# Protected subnets (e.g., local loopback)
PROTECTED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
]


def is_protected_target(ip_str: str | None) -> bool:
    """Check if an IP address belongs to protected infrastructure."""
    if not ip_str or not ip_str.strip():
        return False

    cleaned = ip_str.strip()
    if cleaned in PROTECTED_IPS:
        return True

    try:
        ip = ipaddress.ip_address(cleaned)
        for net in PROTECTED_NETWORKS:
            if ip in net:
                return True
    except ValueError:
        return False

    return False
