"""Configuration Exporters for Reverse Proxies (Nginx, Caddy, Cloudflare).

Generates production-grade, syntax-valid defense configurations from SENTRIX
active mitigation rules.
"""

from __future__ import annotations

import datetime
from typing import Any

from app.mitigation.defensive_engine import (
    DefensiveActionType,
    DefensiveMitigationRule,
    DefensiveRuleMode,
)


def export_nginx_config(rules: list[DefensiveMitigationRule]) -> str:
    """Generate production-ready Nginx configuration block."""
    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    lines: list[str] = [
        "# ============================================================================",
        "# SENTRIX Autonomous Defense Platform — Nginx Mitigation Configuration",
        f"# Exported At (UTC): {now_utc}",
        f"# Total Active Rules: {len(rules)}",
        "# ============================================================================",
        "",
        "# 1. Rate Limiting Zones",
        "limit_req_zone $binary_remote_addr zone=sentrix_general_limit:10m rate=15r/s;",
        "limit_req_zone $binary_remote_addr zone=sentrix_strict_limit:10m rate=2r/s;",
        "limit_req_status 429;",
        "",
        "# 2. Dynamic IP Blocklist & Rate Limits",
    ]

    has_blocks = False
    for rule in rules:
        if rule.is_expired or rule.mode in (
            DefensiveRuleMode.EXPIRED,
            DefensiveRuleMode.REVOKED,
        ):
            continue

        exp_iso = datetime.datetime.fromtimestamp(
            rule.expires_at, datetime.timezone.utc
        ).isoformat()
        lines.append(
            f"# Rule ID: {rule.rule_id} | Mode: {rule.mode.value} | Expires: {exp_iso}"
        )
        lines.append(f"# Reason: {rule.reason}")

        if rule.action_type == DefensiveActionType.BLOCK:
            has_blocks = True
            lines.append(f"deny {rule.target_ip_or_cidr};")
        elif rule.action_type == DefensiveActionType.RATE_LIMIT:
            lines.append(
                f"# Rate Limit: {rule.rate_limit_rps} r/s (burst {rule.burst_capacity}) for {rule.target_ip_or_cidr}"
            )
            lines.append(
                f"limit_req zone=sentrix_general_limit burst={rule.burst_capacity} nodelay;"
            )
        lines.append("")

    if not has_blocks:
        lines.append("# (No IP blocks currently active)")

    lines.extend(
        [
            "",
            "# 3. Example Location Block Integration",
            "# location / {",
            "#     include /etc/nginx/conf.d/sentrix_blocklist.conf;",
            "#     limit_req zone=sentrix_general_limit burst=20 nodelay;",
            "#     proxy_pass http://upstream_backend;",
            "# }",
        ]
    )

    return "\n".join(lines)


def export_caddy_config(rules: list[DefensiveMitigationRule]) -> str:
    """Generate production-ready Caddyfile route matcher snippet."""
    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    lines: list[str] = [
        "# ============================================================================",
        "# SENTRIX Autonomous Defense Platform — Caddyfile Configuration",
        f"# Exported At (UTC): {now_utc}",
        f"# Total Rules: {len(rules)}",
        "# ============================================================================",
        "",
    ]

    block_ips: list[str] = []
    for rule in rules:
        if rule.is_expired or rule.mode in (
            DefensiveRuleMode.EXPIRED,
            DefensiveRuleMode.REVOKED,
        ):
            continue
        if rule.action_type == DefensiveActionType.BLOCK:
            block_ips.append(rule.target_ip_or_cidr)

    if block_ips:
        lines.append("@sentrix_blocked {")
        lines.append(f"    remote_ip {' '.join(block_ips)}")
        lines.append("}")
        lines.append('respond @sentrix_blocked "Access Denied by SENTRIX Defense" 403')
    else:
        lines.append("# No IP blocking matchers active")

    return "\n".join(lines)


def export_cloudflare_waf_rules(
    rules: list[DefensiveMitigationRule],
) -> list[dict[str, Any]]:
    """Generate Cloudflare Custom WAF Rules payload."""
    payloads: list[dict[str, Any]] = []
    for rule in rules:
        if rule.is_expired or rule.mode in (
            DefensiveRuleMode.EXPIRED,
            DefensiveRuleMode.REVOKED,
        ):
            continue

        action = (
            "block" if rule.action_type == DefensiveActionType.BLOCK else "challenge"
        )
        expr = f"(ip.src eq {rule.target_ip_or_cidr})"

        payloads.append(
            {
                "id": rule.rule_id,
                "description": f"SENTRIX Defense Rule: {rule.reason}",
                "expression": expr,
                "action": action,
                "enabled": rule.mode == DefensiveRuleMode.ACTIVE,
            }
        )
    return payloads
