"""Rule generators and validation for Linux nftables and tc enforcement."""

from __future__ import annotations

import ipaddress
import re
from typing import Any

# Designated isolated lab network boundaries
APPROVED_LAB_INTERFACE: str = "sentrix0"
APPROVED_LAB_SUBNET: str = "10.200.0.0/24"
LAB_NETWORK = ipaddress.ip_network(APPROVED_LAB_SUBNET)

# Lab gateway and broadcast are strictly protected within the lab
PROTECTED_LAB_HOSTS: set[str] = {
    "10.200.0.1",   # Lab namespace gateway
    "10.200.0.255", # Lab broadcast
    "127.0.0.1",    # Local loopback
    "::1",
}

# Operational bounding
MIN_RATE_LIMIT_PPS: int = 100
MAX_RATE_LIMIT_PPS: int = 50_000
MIN_DURATION_SECONDS: int = 10
MAX_DURATION_SECONDS: int = 300

NFTABLES_TABLE_NAME: str = "sentrix_mitigation"
NFTABLES_CHAIN_NAME: str = "forward"


class EnforcementValidationError(ValueError):
    """Raised when an enforcement rule parameter violates lab isolation or safety bounds."""


def validate_lab_target(target_ip: str) -> str:
    """Validate that the target IP resides strictly within the approved isolated lab subnet."""
    cleaned = target_ip.strip()
    try:
        ip = ipaddress.ip_address(cleaned)
    except ValueError as exc:
        raise EnforcementValidationError(f"Invalid IP address: '{target_ip}'") from exc

    if ip in [ipaddress.ip_address(h) for h in PROTECTED_LAB_HOSTS]:
        raise EnforcementValidationError(
            f"Target IP '{cleaned}' is a protected lab infrastructure host and cannot be mitigated."
        )

    if ip not in LAB_NETWORK:
        raise EnforcementValidationError(
            f"Target IP '{cleaned}' is outside approved lab subnet '{APPROVED_LAB_SUBNET}'. "
            f"Enforcement is strictly forbidden outside the isolated lab."
        )

    return cleaned


def validate_enforcement_bounds(rate_limit_pps: int, duration_seconds: int) -> None:
    """Enforce strict operational rate and duration limits."""
    if rate_limit_pps < MIN_RATE_LIMIT_PPS or rate_limit_pps > MAX_RATE_LIMIT_PPS:
        raise EnforcementValidationError(
            f"Rate limit {rate_limit_pps} pps is outside allowed safety bounds "
            f"[{MIN_RATE_LIMIT_PPS}, {MAX_RATE_LIMIT_PPS}]."
        )
    if duration_seconds < MIN_DURATION_SECONDS or duration_seconds > MAX_DURATION_SECONDS:
        raise EnforcementValidationError(
            f"Duration {duration_seconds}s is outside allowed safety bounds "
            f"[{MIN_DURATION_SECONDS}, {MAX_DURATION_SECONDS}]."
        )


def build_nftables_init_commands() -> list[list[str]]:
    """Build parameterized command lists to initialize the dedicated SENTRIX nftables table and chain."""
    return [
        ["nft", "add", "table", "inet", NFTABLES_TABLE_NAME],
        [
            "nft",
            "add",
            "chain",
            "inet",
            NFTABLES_TABLE_NAME,
            NFTABLES_CHAIN_NAME,
            "{",
            "type",
            "filter",
            "hook",
            "forward",
            "priority",
            "-100",
            ";",
            "policy",
            "accept",
            ";",
            "}",
        ],
    ]


def build_nftables_apply_commands(
    action_id: str,
    target_ip: str,
    rate_limit_pps: int,
) -> list[list[str]]:
    """Build parameterized commands to apply a tagged rate-limiting rule to the lab interface."""
    # Sanitize action_id for safe comment usage
    safe_action_id = re.sub(r"[^a-zA-Z0-9_\-]", "", action_id)

    # 1. Rate-limit burst rule: allows packets up to rate_limit_pps
    # 2. Drop remainder for this specific target
    return [
        [
            "nft",
            "add",
            "rule",
            "inet",
            NFTABLES_TABLE_NAME,
            NFTABLES_CHAIN_NAME,
            "iifname",
            APPROVED_LAB_INTERFACE,
            "ip",
            "saddr",
            target_ip,
            "limit",
            "rate",
            f"{rate_limit_pps}/second",
            "accept",
            "comment",
            f"sentrix:{safe_action_id}",
        ],
        [
            "nft",
            "add",
            "rule",
            "inet",
            NFTABLES_TABLE_NAME,
            NFTABLES_CHAIN_NAME,
            "iifname",
            APPROVED_LAB_INTERFACE,
            "ip",
            "saddr",
            target_ip,
            "drop",
            "comment",
            f"sentrix:{safe_action_id}:drop",
        ],
    ]


def build_nftables_delete_rule_command(handle: int) -> list[str]:
    """Build command to delete a specific rule by handle."""
    return [
        "nft",
        "delete",
        "rule",
        "inet",
        NFTABLES_TABLE_NAME,
        NFTABLES_CHAIN_NAME,
        "handle",
        str(handle),
    ]


def build_nftables_flush_table_command() -> list[str]:
    """Build command to delete only the dedicated SENTRIX nftables table."""
    return ["nft", "delete", "table", "inet", NFTABLES_TABLE_NAME]


def parse_nftables_rules_output(output_text: str) -> list[dict[str, Any]]:
    """Parse output of `nft -a list table inet sentrix_mitigation` to extract active handles and action IDs."""
    rules: list[dict[str, Any]] = []
    # Pattern matching lines like:
    # iifname "sentrix0" ip saddr 10.200.0.50 limit rate 1000/second accept comment "sentrix:act_001" # handle 4
    pattern = re.compile(
        r'ip saddr (?P<ip>[\d\.]+).*comment "sentrix:(?P<action>[a-zA-Z0-9_\-]+)(?::drop)?".*# handle (?P<handle>\d+)'
    )
    for line in output_text.splitlines():
        match = pattern.search(line)
        if match:
            rules.append(
                {
                    "target_ip": match.group("ip"),
                    "action_id": match.group("action"),
                    "handle": int(match.group("handle")),
                    "is_drop": ":drop" in line,
                }
            )
    return rules
