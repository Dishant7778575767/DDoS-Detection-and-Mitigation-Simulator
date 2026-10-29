"""Defensive Mitigation Engine & Leaky-Bucket Rate Limiter for SENTRIX.

Features:
- Staged Dry-Run mode by default (evaluates impact before live enforcement)
- In-app leaky-bucket per-client IP rate limiter
- Mandatory Rule Expiry with auto-pruning Time-To-Live (TTL)
- Protection for allowlisted and critical infrastructure IPs
- Emergency Disable switch integration
"""

from __future__ import annotations

import ipaddress
import logging
import threading
import time
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field

from app.policy.allowlist import PROTECTED_IPS, PROTECTED_NETWORKS, is_protected_target
from app.safety.gate import is_emergency_disabled

logger = logging.getLogger("sentrix.mitigation.defensive")


class DefensiveRuleMode(str, Enum):
    DRY_RUN = "DRY_RUN"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class DefensiveActionType(str, Enum):
    BLOCK = "BLOCK"
    RATE_LIMIT = "RATE_LIMIT"
    CHALLENGE_CAPTCHA = "CHALLENGE_CAPTCHA"


class DefensiveMitigationRule(BaseModel):
    """Defensive rule representation with TTL and metrics."""

    rule_id: str
    target_ip_or_cidr: str
    action_type: DefensiveActionType
    rate_limit_rps: int = 10
    burst_capacity: int = 20
    mode: DefensiveRuleMode = DefensiveRuleMode.DRY_RUN
    created_at: float = Field(default_factory=time.time)
    expires_at: float
    ttl_seconds: int = 600
    reason: str
    approved_by: str | None = None
    simulated_blocked_count: int = 0
    active_blocked_count: int = 0

    @property
    def remaining_ttl_seconds(self) -> float:
        return max(0.0, self.expires_at - time.time())

    @property
    def is_expired(self) -> bool:
        return time.time() >= self.expires_at


class LeakyBucket:
    """Thread-safe per-client token bucket rate limiter."""

    def __init__(self, rate_per_second: float, capacity: float) -> None:
        self.rate = max(1.0, float(rate_per_second))
        self.capacity = max(1.0, float(capacity))
        self.tokens = self.capacity
        self.last_update = time.time()
        self._lock = threading.Lock()

    def consume(self, amount: float = 1.0) -> bool:
        with self._lock:
            now = time.time()
            elapsed = now - self.last_update
            self.last_update = now

            # Leak/replenish tokens
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

            if self.tokens >= amount:
                self.tokens -= amount
                return True
            return False


class DefensiveMitigationEngine:
    """Manages defensive rate-limiting and IP mitigation policies with dry-run safety."""

    def __init__(self) -> None:
        self._rules: dict[str, DefensiveMitigationRule] = {}
        self._buckets: dict[str, LeakyBucket] = {}
        self._lock = threading.Lock()

    def propose_rule(
        self,
        target_ip_or_cidr: str,
        action_type: DefensiveActionType = DefensiveActionType.RATE_LIMIT,
        rate_limit_rps: int = 10,
        burst_capacity: int = 20,
        ttl_seconds: int = 600,
        reason: str = "Suspicious traffic anomaly detected",
        dry_run: bool = True,
    ) -> DefensiveMitigationRule:
        """Create a new defensive mitigation rule. Defaults to safe Dry-Run mode."""
        clean_target = target_ip_or_cidr.strip()
        if not clean_target:
            raise ValueError("Target IP or CIDR cannot be empty.")

        try:
            target_network = ipaddress.ip_network(clean_target, strict=False)
        except ValueError as exc:
            raise ValueError(
                "Target must be a valid IPv4/IPv6 address or CIDR."
            ) from exc

        if target_network.is_multicast or target_network.network_address.is_unspecified:
            raise ValueError("Multicast and unspecified targets cannot be mitigated.")
        if any(
            target_network.version == network.version
            and target_network.overlaps(network)
            for network in PROTECTED_NETWORKS
        ):
            raise ValueError("Target overlaps a protected infrastructure network.")
        if any(
            ipaddress.ip_address(protected_ip).version == target_network.version
            and ipaddress.ip_address(protected_ip) in target_network
            for protected_ip in PROTECTED_IPS
        ):
            raise ValueError("Target includes a protected infrastructure address.")

        clean_target = (
            str(target_network.network_address)
            if "/" not in clean_target
            else target_network.with_prefixlen
        )

        # Guard: Check allowlist / protected targets
        if is_protected_target(clean_target):
            raise ValueError(
                f"Target '{clean_target}' is in the protected infrastructure allowlist and cannot be mitigated."
            )

        now = time.time()
        ttl = max(30, min(86400, int(ttl_seconds)))  # 30s to 24h
        rule_id = f"def_{uuid4().hex[:10]}"

        safe_reason = (
            " ".join(reason.split())[:512] or "Suspicious traffic anomaly detected"
        )
        rule = DefensiveMitigationRule(
            rule_id=rule_id,
            target_ip_or_cidr=clean_target,
            action_type=action_type,
            rate_limit_rps=rate_limit_rps,
            burst_capacity=burst_capacity,
            mode=DefensiveRuleMode.DRY_RUN if dry_run else DefensiveRuleMode.ACTIVE,
            created_at=now,
            expires_at=now + ttl,
            ttl_seconds=ttl,
            reason=safe_reason,
            approved_by=None if dry_run else "auto-approved",
        )

        with self._lock:
            self._rules[rule_id] = rule

        logger.info(
            "Defensive rule created: %s for %s (%s, mode=%s, ttl=%ds)",
            rule_id,
            clean_target,
            action_type.value,
            rule.mode.value,
            ttl,
        )
        return rule

    def approve_rule(
        self, rule_id: str, operator: str = "admin"
    ) -> DefensiveMitigationRule:
        """Promote a dry-run rule to active enforcement upon operator review."""
        with self._lock:
            if rule_id not in self._rules:
                raise KeyError(f"Defensive rule '{rule_id}' not found.")
            rule = self._rules[rule_id]
            if rule.is_expired:
                rule.mode = DefensiveRuleMode.EXPIRED
                raise ValueError(f"Rule '{rule_id}' has already expired.")

            rule.mode = DefensiveRuleMode.ACTIVE
            rule.approved_by = operator
            logger.info(
                "Defensive rule %s approved by %s for active enforcement",
                rule_id,
                operator,
            )
            return rule

    def revoke_rule(self, rule_id: str) -> bool:
        """Immediately cancel/revoke a mitigation rule."""
        with self._lock:
            if rule_id not in self._rules:
                return False
            self._rules[rule_id].mode = DefensiveRuleMode.REVOKED
            logger.info("Defensive rule %s revoked", rule_id)
            return True

    def _matches_target(self, client_ip: str, target: str) -> bool:
        """Check if client IP matches single IP or CIDR network."""
        if client_ip == target:
            return True
        try:
            net = ipaddress.ip_network(target, strict=False)
            addr = ipaddress.ip_address(client_ip)
            return addr in net
        except ValueError:
            return False

    def check_request(self, client_ip: str) -> tuple[bool, str | None]:
        """Evaluate an incoming request against all active and dry-run defensive rules.

        Returns:
            tuple[bool, str | None]: (is_allowed, denial_reason)
        """
        # 1. Emergency disable bypass
        if is_emergency_disabled():
            return True, None

        # 2. Protected allowlist check
        if is_protected_target(client_ip):
            return True, None

        with self._lock:
            active_rules = [
                r
                for r in self._rules.values()
                if not r.is_expired
                and r.mode in (DefensiveRuleMode.ACTIVE, DefensiveRuleMode.DRY_RUN)
            ]

        for rule in active_rules:
            if not self._matches_target(client_ip, rule.target_ip_or_cidr):
                continue

            # Target matched
            if rule.mode == DefensiveRuleMode.DRY_RUN:
                # Dry run: log simulated drop without blocking client
                rule.simulated_blocked_count += 1
                logger.debug(
                    "DRY-RUN simulated block for %s on rule %s",
                    client_ip,
                    rule.rule_id,
                )
                continue

            # Active enforcement
            if rule.action_type == DefensiveActionType.BLOCK:
                rule.active_blocked_count += 1
                return False, f"Blocked by SENTRIX defense rule {rule.rule_id}"

            elif rule.action_type == DefensiveActionType.RATE_LIMIT:
                # Per-client token bucket
                bucket_key = f"{rule.rule_id}:{client_ip}"
                if bucket_key not in self._buckets:
                    self._buckets[bucket_key] = LeakyBucket(
                        rate_per_second=rule.rate_limit_rps,
                        capacity=rule.burst_capacity,
                    )
                if not self._buckets[bucket_key].consume():
                    rule.active_blocked_count += 1
                    return False, f"Rate limited by SENTRIX defense rule {rule.rule_id}"

        return True, None

    def get_rules(self, include_expired: bool = False) -> list[DefensiveMitigationRule]:
        """Return list of mitigation rules, updating expired states."""
        now = time.time()
        with self._lock:
            results: list[DefensiveMitigationRule] = []
            for rule in self._rules.values():
                if rule.expires_at <= now and rule.mode in (
                    DefensiveRuleMode.ACTIVE,
                    DefensiveRuleMode.DRY_RUN,
                ):
                    rule.mode = DefensiveRuleMode.EXPIRED
                if include_expired or not rule.is_expired:
                    results.append(rule)
            return sorted(results, key=lambda r: r.created_at, reverse=True)

    def reset(self) -> None:
        """Clear all active rules and buckets."""
        with self._lock:
            self._rules.clear()
            self._buckets.clear()


# Module-level singleton instance
defensive_engine = DefensiveMitigationEngine()
