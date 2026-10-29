"""Configuration Exporters for Reverse Proxies and Edge WAFs (AWS WAFv2, Nginx, Caddy).

Generates reviewable configuration snippets from explicitly approved SENTRIX
mitigation rules. Snippets are not installed or validated against a live server.
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
    active_rules = [
        rule
        for rule in rules
        if not rule.is_expired and rule.mode == DefensiveRuleMode.ACTIVE
    ]
    lines: list[str] = [
        "# ============================================================================",
        "# SENTRIX Autonomous Defense Platform — Nginx Mitigation Configuration",
        f"# Exported At (UTC): {now_utc}",
        f"# Total Active Rules: {len(active_rules)}",
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
        if rule.is_expired or rule.mode != DefensiveRuleMode.ACTIVE:
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
    """Generate a Caddy IP-deny snippet for approved block rules."""
    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    active_count = sum(
        not rule.is_expired and rule.mode == DefensiveRuleMode.ACTIVE for rule in rules
    )
    lines: list[str] = [
        "# ============================================================================",
        "# SENTRIX Autonomous Defense Platform — Caddyfile Configuration",
        f"# Exported At (UTC): {now_utc}",
        f"# Total Active Rules: {active_count}",
        "# ============================================================================",
        "",
    ]

    block_ips: list[str] = []
    for rule in rules:
        if rule.is_expired or rule.mode != DefensiveRuleMode.ACTIVE:
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


def _format_cidr(ip_or_cidr: str) -> str:
    """Ensure an IPv4/IPv6 string has valid CIDR notation for AWS WAFv2 IPSet."""
    cleaned = ip_or_cidr.strip()
    if "/" in cleaned:
        return cleaned
    # Assume IPv4 /32 single host if no colon; IPv6 /128 if colon present
    return f"{cleaned}/128" if ":" in cleaned else f"{cleaned}/32"


def export_aws_wafv2_ipset(
    rules: list[DefensiveMitigationRule],
    ipset_name: str = "sentrix-mitigation-ipset",
) -> dict[str, Any]:
    """Generate AWS WAFv2 IPSet resource definition for CloudFront.

    Note: AWS WAF for CloudFront strictly requires Scope='CLOUDFRONT' and region 'us-east-1'.
    """
    eligible_ips: set[str] = set()
    for rule in rules:
        if rule.is_expired:
            continue
        if rule.mode in (
            DefensiveRuleMode.ACTIVE,
            DefensiveRuleMode.DRY_RUN,
        ) and rule.action_type in (
            DefensiveActionType.BLOCK,
            DefensiveActionType.CHALLENGE_CAPTCHA,
        ):
            eligible_ips.add(_format_cidr(rule.target_ip_or_cidr))

    addresses = sorted(eligible_ips)

    return {
        "Name": ipset_name,
        "Scope": "CLOUDFRONT",
        "Region": "us-east-1",
        "IPAddressVersion": "IPV4",
        "Description": f"SENTRIX Autonomous DDoS Mitigation IPSet ({len(addresses)} addresses)",
        "Addresses": addresses,
    }


def export_aws_wafv2_rules(
    rules: list[DefensiveMitigationRule],
    ipset_arn: str = "arn:aws:wafv2:us-east-1:000000000000:global/ipset/sentrix-mitigation-ipset/sample-id",
) -> list[dict[str, Any]]:
    """Generate AWS WAFv2 WebACL Rule definitions referencing the IPSet.

    Active rules map to Action: Block; Dry-run rules map to Action: Count.
    """
    webacl_rules: list[dict[str, Any]] = []
    priority = 10

    for rule in rules:
        if rule.is_expired:
            continue
        if rule.mode not in (DefensiveRuleMode.ACTIVE, DefensiveRuleMode.DRY_RUN):
            continue

        # In AWS WAF, dry_run mode maps to "Count" action (monitoring/logging without blocking)
        action: dict[str, Any] = (
            {"Block": {}}
            if rule.mode == DefensiveRuleMode.ACTIVE
            and rule.action_type == DefensiveActionType.BLOCK
            else {"Count": {}}
        )

        sanitized_id = rule.rule_id.replace("-", "_")
        webacl_rules.append(
            {
                "Name": f"SENTRIX_{sanitized_id}",
                "Priority": priority,
                "Statement": {
                    "IPSetReferenceStatement": {
                        "ARN": ipset_arn,
                    }
                },
                "Action": action,
                "VisibilityConfig": {
                    "SampledRequestsEnabled": True,
                    "CloudWatchMetricsEnabled": True,
                    "MetricName": f"SENTRIX_{sanitized_id}_Metric",
                },
            }
        )
        priority += 10

    return webacl_rules


def export_aws_wafv2_cli_script(
    rules: list[DefensiveMitigationRule],
    ipset_name: str = "sentrix-mitigation-ipset",
) -> str:
    """Generate an executable AWS CLI bash script to deploy or update the CloudFront IPSet."""
    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    ipset_data = export_aws_wafv2_ipset(rules, ipset_name=ipset_name)
    addresses = ipset_data["Addresses"]
    addr_str = " ".join(f'"{a}"' for a in addresses) if addresses else '""'

    return f"""#!/usr/bin/env bash
# ==============================================================================
# SENTRIX Autonomous Defense Platform — AWS WAFv2 CloudFront Deployment
# Generated At (UTC): {now_utc}
# Target Scope: CLOUDFRONT (Requires region us-east-1)
# Addresses to Block/Count: {len(addresses)}
# ==============================================================================

set -euo pipefail

REGION="us-east-1"
SCOPE="CLOUDFRONT"
IPSET_NAME="{ipset_name}"
DESCRIPTION="{ipset_data["Description"]}"

echo "Checking if IPSet $IPSET_NAME exists in AWS WAFv2 ($SCOPE, $REGION)..."

EXISTING_ID=$(aws wafv2 list-ip-sets \\
    --scope "$SCOPE" \\
    --region "$REGION" \\
    --query "IPSets[?Name=='$IPSET_NAME'].Id | [0]" \\
    --output text 2>/dev/null || echo "None")

if [ "$EXISTING_ID" != "None" ] && [ -n "$EXISTING_ID" ]; then
    echo "Found existing IPSet with ID: $EXISTING_ID. Fetching lock token..."
    LOCK_TOKEN=$(aws wafv2 get-ip-set \\
        --name "$IPSET_NAME" \\
        --scope "$SCOPE" \\
        --id "$EXISTING_ID" \\
        --region "$REGION" \\
        --query "LockToken" \\
        --output text)

    echo "Updating IPSet $IPSET_NAME with {len(addresses)} address(es)..."
    aws wafv2 update-ip-set \\
        --name "$IPSET_NAME" \\
        --scope "$SCOPE" \\
        --id "$EXISTING_ID" \\
        --region "$REGION" \\
        --lock-token "$LOCK_TOKEN" \\
        --addresses {addr_str}
    echo "AWS WAFv2 IPSet updated successfully."
else
    echo "Creating new AWS WAFv2 IPSet $IPSET_NAME in $SCOPE ($REGION)..."
    aws wafv2 create-ip-set \\
        --name "$IPSET_NAME" \\
        --scope "$SCOPE" \\
        --region "$REGION" \\
        --ip-address-version IPV4 \\
        --description "$DESCRIPTION" \\
        --addresses {addr_str}
    echo "AWS WAFv2 IPSet created successfully."
fi
"""


def export_cloudflare_waf_rules(
    rules: list[DefensiveMitigationRule],
) -> list[dict[str, Any]]:
    """(Deprecated) Generate legacy Cloudflare Custom WAF Rules payload."""
    payloads: list[dict[str, Any]] = []
    for rule in rules:
        if rule.is_expired or rule.mode != DefensiveRuleMode.ACTIVE:
            continue
        if rule.action_type not in (
            DefensiveActionType.BLOCK,
            DefensiveActionType.CHALLENGE_CAPTCHA,
        ):
            continue

        action = (
            "block"
            if rule.action_type == DefensiveActionType.BLOCK
            else "managed_challenge"
        )
        expr = f"ip.src in {{{rule.target_ip_or_cidr}}}"

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
