"""Integration tests for Defensive Mitigation Engine & Config Exporters (Milestone 3)."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app
from app.mitigation.config_exporter import export_caddy_config, export_nginx_config
from app.mitigation.defensive_engine import (
    DefensiveActionType,
    DefensiveMitigationEngine,
    DefensiveRuleMode,
    defensive_engine,
)
from app.safety.gate import set_emergency_disabled


def test_defensive_engine_dry_run_and_approval() -> None:
    """Verifies dry-run safety by default and promotion upon operator approval."""
    engine = DefensiveMitigationEngine()
    set_emergency_disabled(False)

    # 1. Reject protected IP
    with pytest.raises(ValueError, match="protected infrastructure"):
        engine.propose_rule(target_ip_or_cidr="127.0.0.1")

    # 2. Propose rule for attacker IP (defaults to DRY_RUN)
    rule = engine.propose_rule(
        target_ip_or_cidr="198.51.100.88",
        action_type=DefensiveActionType.BLOCK,
        ttl_seconds=300,
        reason="Volumetric HTTP Flood detected",
        dry_run=True,
    )
    assert rule.mode == DefensiveRuleMode.DRY_RUN
    assert rule.simulated_blocked_count == 0

    # 3. Request evaluation in DRY_RUN: Request is ALLOWED, simulated count incremented
    allowed, _ = engine.check_request("198.51.100.88")
    assert allowed
    assert rule.simulated_blocked_count == 1
    assert rule.active_blocked_count == 0

    # 4. Operator approves rule -> Mode becomes ACTIVE
    approved_rule = engine.approve_rule(rule.rule_id, operator="sec_analyst")
    assert approved_rule.mode == DefensiveRuleMode.ACTIVE
    assert approved_rule.approved_by == "sec_analyst"

    # 5. Request evaluation in ACTIVE: Request is BLOCKED
    allowed_post, reason_post = engine.check_request("198.51.100.88")
    assert not allowed_post
    assert "Blocked by SENTRIX defense rule" in reason_post
    assert approved_rule.active_blocked_count == 1

    # 6. Emergency disable bypasses all active enforcement
    set_emergency_disabled(True)
    allowed_emg, _ = engine.check_request("198.51.100.88")
    assert allowed_emg
    set_emergency_disabled(False)


def test_config_exporters_syntax() -> None:
    """Verifies exported Nginx and Caddy configuration text."""
    engine = DefensiveMitigationEngine()
    rule1 = engine.propose_rule(
        target_ip_or_cidr="203.0.113.50",
        action_type=DefensiveActionType.BLOCK,
        reason="Repeated Credential Stuffing",
        dry_run=False,
    )
    rule2 = engine.propose_rule(
        target_ip_or_cidr="198.51.100.0/24",
        action_type=DefensiveActionType.RATE_LIMIT,
        rate_limit_rps=5,
        burst_capacity=10,
        reason="Distributed botnet flood",
        dry_run=False,
    )

    rules = [rule1, rule2]

    # Nginx
    nginx_conf = export_nginx_config(rules)
    assert "deny 203.0.113.50;" in nginx_conf
    assert "limit_req_zone" in nginx_conf
    assert "198.51.100.0/24" in nginx_conf

    # Caddy
    caddy_conf = export_caddy_config(rules)
    assert "@sentrix_blocked" in caddy_conf
    assert "203.0.113.50" in caddy_conf


def test_defensive_mitigation_api_endpoints(monkeypatch) -> None:
    """Verifies API contracts for /mitigations/defensive and exports."""
    monkeypatch.setenv("API_AUTH_REQUIRED", "true")
    monkeypatch.setenv("API_AUTH_TOKEN", "valid-test-key")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./sentrix.db")
    get_settings.cache_clear()
    headers = {"Authorization": "Bearer valid-test-key"}

    defensive_engine.reset()

    with TestClient(create_app()) as client:
        # 1. Propose rule via API
        propose_payload = {
            "target_ip_or_cidr": "198.51.100.22",
            "action_type": "BLOCK",
            "ttl_seconds": 600,
            "reason": "Slowloris exhaustion pattern",
            "dry_run": True,
        }
        resp_propose = client.post(
            "/api/v1/mitigations/defensive/propose",
            json=propose_payload,
            headers=headers,
        )
        assert resp_propose.status_code == 201
        data = resp_propose.json()
        rule_id = data["rule_id"]
        assert data["mode"] == "DRY_RUN"
        assert data["target_ip_or_cidr"] == "198.51.100.22"

        # 2. List rules
        resp_list = client.get("/api/v1/mitigations/defensive/rules", headers=headers)
        assert resp_list.status_code == 200
        assert len(resp_list.json()) >= 1

        # 3. Approve rule
        resp_appr = client.post(
            f"/api/v1/mitigations/defensive/{rule_id}/approve",
            headers=headers,
        )
        assert resp_appr.status_code == 200
        assert resp_appr.json()["mode"] == "ACTIVE"

        # 4. Export Nginx configuration
        resp_nginx = client.get("/api/v1/mitigations/export/nginx", headers=headers)
        assert resp_nginx.status_code == 200
        assert "deny 198.51.100.22;" in resp_nginx.text

        # 5. Export Caddy configuration
        resp_caddy = client.get("/api/v1/mitigations/export/caddy", headers=headers)
        assert resp_caddy.status_code == 200
        assert "198.51.100.22" in resp_caddy.text

        # 6. Revoke rule
        resp_rev = client.post(
            f"/api/v1/mitigations/defensive/{rule_id}/revoke",
            headers=headers,
        )
        assert resp_rev.status_code == 200
        assert resp_rev.json()["status"] == "revoked"


def test_defensive_rule_ttl_expiry_and_pruning() -> None:
    """Verifies that expired DRY_RUN and ACTIVE rules transition to EXPIRED and are pruned."""
    engine = DefensiveMitigationEngine()

    rule = engine.propose_rule(
        target_ip_or_cidr="198.51.100.95",
        ttl_seconds=30,
        reason="Testing TTL expiry",
        dry_run=True,
    )
    assert rule.mode == DefensiveRuleMode.DRY_RUN

    # Artificially expire rule by setting expires_at to the past
    rule.expires_at = time.time() - 5.0
    assert rule.is_expired

    rules = engine.get_rules(include_expired=True)
    matching = [r for r in rules if r.rule_id == rule.rule_id]
    assert len(matching) == 1
    assert matching[0].mode == DefensiveRuleMode.EXPIRED

    # When include_expired is False, expired rule must be omitted
    active_only = engine.get_rules(include_expired=False)
    assert not any(r.rule_id == rule.rule_id for r in active_only)


def test_leaky_bucket_burst_and_rate_limit() -> None:
    """Verifies LeakyBucket token exhaustion and replenishment."""
    from app.mitigation.defensive_engine import LeakyBucket

    bucket = LeakyBucket(rate_per_second=2.0, capacity=3.0)
    # Burst 3 tokens
    assert bucket.consume(1.0)
    assert bucket.consume(1.0)
    assert bucket.consume(1.0)
    # 4th immediate token fails
    assert not bucket.consume(1.0)
