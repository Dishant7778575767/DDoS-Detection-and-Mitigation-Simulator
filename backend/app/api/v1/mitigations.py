"""Mitigation lifecycle and simulation endpoints."""

from __future__ import annotations

import datetime
import logging
import os
import socket
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import require_api_auth
from app.mitigation.lifecycle import (
    IllegalTransitionError,
    validate_lifecycle_transition,
)
from app.mitigation.simulation import SimulationAdapter
from app.safety.gate import (
    MAX_CONCURRENT_MITIGATIONS,
    MAX_DURATION_SECONDS,
    MAX_RATE_LIMIT_PPS,
    MIN_DURATION_SECONDS,
    MIN_RATE_LIMIT_PPS,
    is_emergency_disabled,
    set_emergency_disabled,
    validate_safety_gate,
)
from app.storage.audit import record_audit_event
from app.storage.database import get_db_session
from app.storage.repositories import MitigationRepository, SimulationRunRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mitigations"], dependencies=[Depends(require_api_auth)])
simulation_adapter = SimulationAdapter()


class MitigationItem(BaseModel):
    action_id: str
    detection_id: int | None
    target_ip: str
    target_port: int | None
    action_type: str
    rate_limit_pps: int
    duration_seconds: int
    status: str
    mode: str
    created_at: str
    updated_at: str
    expires_at: str | None
    cancelled_at: str | None


class MitigationsListResponse(BaseModel):
    total_count: int
    limit: int
    offset: int
    mitigations: list[MitigationItem]


class SimulateMitigationRequest(BaseModel):
    target_ip: str = Field(..., description="Target IPv4/IPv6 address to rate-limit")
    target_port: int | None = Field(default=None, ge=0, le=65535)
    rate_limit_pps: int = Field(default=1000, ge=100, le=50000)
    duration_seconds: int = Field(default=60, ge=10, le=300)
    action_type: str | None = Field(default="rate_limit", description="Action type")
    reason: str | None = Field(default=None, description="Operator simulation reason")


def resolve_host_network_info(request: Request | None = None) -> dict[str, Any]:
    """Detect dynamic server network metadata (Host IP, Deployed Cloud Domain, DNS Gateways)."""
    # 1. Check cloud hosting environment variables
    deployed_host = (
        os.environ.get("RENDER_EXTERNAL_HOSTNAME")
        or os.environ.get("RAILWAY_PUBLIC_DOMAIN")
        or os.environ.get("FLY_APP_NAME")
        or os.environ.get("SERVER_IP")
        or os.environ.get("DEPLOYED_SERVER_IP")
        or os.environ.get("HOST_DOMAIN")
    )
    is_deployed = bool(
        deployed_host
        or os.environ.get("RENDER")
        or os.environ.get("RAILWAY_ENVIRONMENT")
        or os.environ.get("FLY_ALLOC_ID")
        or os.environ.get("VERCEL")
        or os.environ.get("PRODUCTION") == "true"
        or os.environ.get("APP_ENV") == "production"
    )

    # Check request headers for proxy / cloud hostname if not already determined
    if request is not None:
        req_host = request.headers.get("x-forwarded-host") or request.headers.get(
            "host"
        )
        if req_host:
            host_clean = req_host.split(":")[0].strip()
            if host_clean and host_clean not in (
                "localhost",
                "127.0.0.1",
                "0.0.0.0",
                "testserver",
            ):
                is_deployed = True
                if not deployed_host:
                    deployed_host = host_clean

    # 2. Outward interface IP / Local IP
    local_ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.2)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except OSError:
        try:
            local_ip = socket.gethostbyname(socket.gethostname())
        except OSError:
            local_ip = "127.0.0.1"

    host_ip = deployed_host if (is_deployed and deployed_host) else local_ip
    hostname = "localhost"
    try:
        hostname = socket.gethostname()
    except OSError:
        pass

    # 3. Dynamic DNS Gateways
    dns_gateways = ["8.8.8.8", "1.1.1.1"]
    env_dns = os.environ.get("DNS_GATEWAYS") or os.environ.get("DEFAULT_DNS")
    if env_dns:
        dns_gateways = [d.strip() for d in env_dns.split(",") if d.strip()]
    elif os.name != "nt":
        resolv_path = "/etc/resolv.conf"
        if os.path.exists(resolv_path):
            try:
                found_dns: list[str] = []
                with open(resolv_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("nameserver "):
                            parts = line.split()
                            if len(parts) > 1:
                                ns = parts[1].strip()
                                if ns and ns not in found_dns and ns != "127.0.0.53":
                                    found_dns.append(ns)
                if found_dns:
                    dns_gateways = found_dns[:3]
            except (OSError, UnicodeDecodeError):
                pass

    return {
        "host_ip": host_ip,
        "hostname": hostname,
        "is_deployed": is_deployed,
        "environment": "deployed" if is_deployed else "local",
        "dns_gateways": dns_gateways,
        "protected_gateways": ["192.168.1.1", "10.0.0.1"],
    }


@router.get("/mitigations/status")
def get_mitigation_system_status(
    session: Annotated[Session, Depends(get_db_session)],
    request: Request = None,
) -> dict[str, Any]:
    """Return live status of the mitigation subsystem including safety gates, dynamic network info, and active shield countdown."""
    repo = MitigationRepository(session)
    repo.expire_stale_mitigations()
    active_items = repo.get_active_or_simulated()
    active_count = len(active_items)

    latest_mitigation = None
    shield_active = False

    now_dt = datetime.datetime.now(datetime.timezone.utc)
    for item in active_items:
        rem_sec = 0
        if item.expires_at:
            try:
                exp_dt = datetime.datetime.fromisoformat(
                    item.expires_at.replace("Z", "+00:00")
                )
                rem_sec = max(0, int((exp_dt - now_dt).total_seconds()))
            except (ValueError, TypeError):
                rem_sec = item.duration_seconds
        else:
            rem_sec = item.duration_seconds

        if rem_sec > 0:
            shield_active = True
            latest_mitigation = {
                "action_id": item.action_id,
                "source": "mitigation",
                "target_ip": item.target_ip,
                "target_port": item.target_port,
                "rate_limit_pps": item.rate_limit_pps,
                "duration_seconds": item.duration_seconds,
                "remaining_seconds": rem_sec,
                "status": item.status,
                "expires_at": item.expires_at,
            }
            break

    # Synchronize with active running simulation defense state
    sim_repo = SimulationRunRepository(session)
    running_runs = sim_repo.list_runs(status="running", limit=1)
    if running_runs:
        active_sim = running_runs[0]
        sim_ticks = active_sim.ticks
        latest_tick = sim_ticks[-1] if sim_ticks else None
        if latest_tick and (
            latest_tick.active_mitigations_count > 0
            or latest_tick.policy_action
            in ("request_mitigation", "simulate_mitigation", "rate_limit")
        ):
            shield_active = True
            rem_sim_sec = max(1, int(active_sim.total_ticks - active_sim.current_tick))
            if (
                not latest_mitigation
                or latest_mitigation.get("remaining_seconds", 0) <= 0
            ):
                latest_mitigation = {
                    "action_id": f"sim_{active_sim.run_id}_t{active_sim.current_tick}",
                    "source": "simulation_run",
                    "run_id": active_sim.run_id,
                    "target_ip": "192.168.1.100",
                    "target_port": 80,
                    "rate_limit_pps": 5000,
                    "duration_seconds": active_sim.total_ticks,
                    "remaining_seconds": rem_sim_sec,
                    "status": "active",
                    "expires_at": None,
                }
            else:
                latest_mitigation["remaining_seconds"] = max(
                    latest_mitigation["remaining_seconds"], rem_sim_sec
                )
            latest_mitigation["source"] = "simulation_run"
            latest_mitigation["run_id"] = active_sim.run_id

    network_info = resolve_host_network_info(request)

    return {
        "emergency_disabled": is_emergency_disabled(),
        "mode": "simulation",
        "shield_active": shield_active,
        "active_simulated_count": active_count,
        "max_concurrent_limit": MAX_CONCURRENT_MITIGATIONS,
        "status": "locked_down" if is_emergency_disabled() else "operational",
        "latest_mitigation": latest_mitigation,
        "host_ip": network_info["host_ip"],
        "hostname": network_info["hostname"],
        "is_deployed": network_info["is_deployed"],
        "environment": network_info["environment"],
        "dns_gateways": network_info["dns_gateways"],
        "protected_gateways": network_info["protected_gateways"],
        "rate_limit_bounds": {
            "min_pps": MIN_RATE_LIMIT_PPS,
            "max_pps": MAX_RATE_LIMIT_PPS,
        },
        "duration_bounds": {
            "min_seconds": MIN_DURATION_SECONDS,
            "max_seconds": MAX_DURATION_SECONDS,
        },
        "cooldown_ticks": 10,
    }


@router.get("/mitigations", response_model=MitigationsListResponse)
def list_mitigations(
    session: Annotated[Session, Depends(get_db_session)],
    status_filter: Annotated[
        str | None,
        Query(
            alias="status",
            description="Filter by status (e.g., 'simulated', 'cancelled')",
        ),
    ] = None,
    mode_filter: Annotated[
        str | None,
        Query(alias="mode", description="Filter by mode ('simulation', 'lab')"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MitigationsListResponse:
    """Return filtered and paginated mitigations."""
    safe_limit = limit.default if hasattr(limit, "default") else int(limit)
    safe_offset = offset.default if hasattr(offset, "default") else int(offset)

    repo = MitigationRepository(session)
    items = repo.list_filtered(
        status=status_filter, mode=mode_filter, limit=safe_limit, offset=safe_offset
    )
    total = repo.count_filtered(status=status_filter, mode=mode_filter)

    return MitigationsListResponse(
        total_count=total,
        limit=safe_limit,
        offset=safe_offset,
        mitigations=[
            MitigationItem(
                action_id=m.action_id,
                detection_id=m.detection_id,
                target_ip=m.target_ip,
                target_port=m.target_port,
                action_type=m.action_type,
                rate_limit_pps=m.rate_limit_pps,
                duration_seconds=m.duration_seconds,
                status=m.status,
                mode=m.mode,
                created_at=m.created_at,
                updated_at=m.updated_at,
                expires_at=m.expires_at,
                cancelled_at=m.cancelled_at,
            )
            for m in items
        ],
    )


@router.post("/mitigations/simulate", status_code=status.HTTP_201_CREATED)
def simulate_mitigation(
    payload: SimulateMitigationRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Evaluate safety gate and execute a simulation-only rate-limiting action."""
    logger.info(
        "Simulation mitigation request received: target_ip=%s, rate_limit=%s pps, duration=%ss",
        payload.target_ip,
        payload.rate_limit_pps,
        payload.duration_seconds,
    )
    repo = MitigationRepository(session)
    active_count = repo.count_filtered(status="simulated")

    # Pass through safety gate
    safety_result = validate_safety_gate(
        target_ip=payload.target_ip,
        rate_limit_pps=payload.rate_limit_pps,
        duration_seconds=payload.duration_seconds,
        current_active_count=active_count,
        mitigation_mode="simulation",
    )
    if not safety_result.allowed:
        logger.warning(
            "Safety Gate REJECTED mitigation request: %s (target_ip=%s, rate_limit=%s pps)",
            safety_result.rejection_reason,
            payload.target_ip,
            payload.rate_limit_pps,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=safety_result.rejection_reason
            or "Safety gate rejected the request.",
        )

    # State transition: proposed -> simulated
    validate_lifecycle_transition("proposed", "simulated")
    mitigation = repo.create(
        detection_id=None,
        target_ip=payload.target_ip,
        target_port=payload.target_port,
        action_type="rate_limit",
        rate_limit_pps=payload.rate_limit_pps,
        duration_seconds=payload.duration_seconds,
        status="proposed",
        mode="simulation",
    )

    sim_outcome = simulation_adapter.apply_rate_limit(
        action_id=mitigation.action_id,
        target_ip=payload.target_ip,
        rate_limit_pps=payload.rate_limit_pps,
        duration_seconds=payload.duration_seconds,
    )

    exp_dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        seconds=payload.duration_seconds
    )
    repo.update_status(
        action_id=mitigation.action_id,
        new_status="simulated",
        expires_at=exp_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    record_audit_event(
        session=session,
        event_type="mitigation_simulated",
        action="simulate_rate_limit",
        actor="operator_api",
        details=sim_outcome,
    )

    return sim_outcome


@router.post("/mitigations/{action_id}/cancel")
def cancel_mitigation(
    action_id: Annotated[str, Path(description="The unique action ID to cancel")],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Request cancellation of an active or simulated mitigation action."""
    repo = MitigationRepository(session)
    mitigation = repo.get_by_action_id(action_id)
    if not mitigation:
        # Gracefully handle simulation or virtual mitigation cancellation without raising 404
        if action_id.startswith(("sim_", "sim-", "virtual_")):
            repo.expire_simulation_mitigations()
            try:
                from app.simulator.manager import _RUN_EVALUATORS

                for _engine, _evaluator, _tick in list(_RUN_EVALUATORS.values()):
                    for act in _evaluator.mitigation_manager.all_actions:
                        if act.status == "active":
                            act.cancel(_tick)
            except (KeyError, AttributeError, RuntimeError) as exc:
                logger.debug("Failed to cancel in-memory simulation actions: %s", exc)

            cancelled_timestamp = datetime.datetime.now(datetime.timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            record_audit_event(
                session=session,
                event_type="mitigation_cancelled",
                action="cancel_mitigation",
                actor="operator_api",
                details={
                    "action_id": action_id,
                    "target_ip": "192.168.1.100",
                    "previous_state": "simulated",
                    "cancelled_at": cancelled_timestamp,
                },
            )
            return {
                "action_id": action_id,
                "target_ip": "192.168.1.100",
                "action_type": "rate_limit",
                "rate_limit_pps": 5000,
                "duration_seconds": 60,
                "status": "cancelled",
                "mode": "simulation",
                "host_networking_modified": False,
                "message": f"Simulation mitigation '{action_id}' cancelled.",
            }

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mitigation action '{action_id}' not found.",
        )

    if mitigation.status in ("cancelled", "expired"):
        return {
            "action_id": action_id,
            "status": mitigation.status,
            "message": (
                "Mitigation was already cancelled."
                if mitigation.status == "cancelled"
                else "Mitigation has already expired."
            ),
        }

    # Validate lifecycle transition
    try:
        validate_lifecycle_transition(mitigation.status, "cancelled")
    except IllegalTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    cancel_outcome = simulation_adapter.cancel_rate_limit(
        action_id=action_id,
        target_ip=mitigation.target_ip,
    )

    cancelled_timestamp = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    repo.update_status(
        action_id=action_id,
        new_status="cancelled",
        cancelled_at=cancelled_timestamp,
    )

    if mitigation.mode == "simulation" or action_id.startswith(("sim_", "sim-")):
        repo.expire_simulation_mitigations()
        try:
            from app.simulator.manager import _RUN_EVALUATORS

            for _engine, _evaluator, _tick in list(_RUN_EVALUATORS.values()):
                for act in _evaluator.mitigation_manager.all_actions:
                    if act.action_id == action_id or act.status == "active":
                        act.cancel(_tick)
        except (KeyError, AttributeError, RuntimeError) as exc:
            logger.debug("Failed to cancel in-memory simulation actions: %s", exc)

    record_audit_event(
        session=session,
        event_type="mitigation_cancelled",
        action="cancel_mitigation",
        actor="operator_api",
        details={
            "action_id": action_id,
            "target_ip": mitigation.target_ip,
            "previous_state": mitigation.status,
            "cancelled_at": cancelled_timestamp,
        },
    )

    return cancel_outcome


@router.post("/mitigations/disable")
def emergency_disable_mitigations(
    session: Annotated[Session, Depends(get_db_session)],
    enable: Annotated[
        bool, Query(description="Set to true to re-enable mitigations")
    ] = False,
) -> dict[str, Any]:
    """Activate or deactivate emergency disable switch to halt or restore mitigations."""
    if enable:
        set_emergency_disabled(False)
        record_audit_event(
            session=session,
            event_type="emergency_disable_cleared",
            action="clear_emergency_disable",
            actor="operator_api",
            details={
                "emergency_disabled": False,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
            },
        )
        return {
            "emergency_disabled": False,
            "status": "Mitigation safety gate re-enabled.",
        }

    set_emergency_disabled(True)
    repo = MitigationRepository(session)
    active = repo.get_active_or_simulated()

    cancelled_count = len(active)
    now_ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if active:
        # Perform single batch update instead of sequential loop commits
        from sqlalchemy import update

        from app.storage.models import MitigationModel

        action_ids = [act.action_id for act in active]
        session.execute(
            update(MitigationModel)
            .where(MitigationModel.action_id.in_(action_ids))
            .values(
                status="cancelled",
                cancelled_at=now_ts,
                updated_at=now_ts,
            )
        )
        session.commit()

    record_audit_event(
        session=session,
        event_type="emergency_disable_activated",
        action="emergency_disable",
        actor="operator_api",
        details={
            "cancelled_actions_count": cancelled_count,
            "emergency_disabled": True,
            "timestamp": now_ts,
        },
    )

    return {
        "emergency_disabled": True,
        "cancelled_actions_count": cancelled_count,
        "status": "All mitigation actions have been halted.",
    }


# ---------------------------------------------------------------------------
# Real-World Defensive Mitigation & Staged Dry-Run Endpoints (Milestone 3)
# ---------------------------------------------------------------------------

from fastapi.responses import PlainTextResponse

from app.mitigation.config_exporter import export_caddy_config, export_nginx_config
from app.mitigation.defensive_engine import (
    DefensiveActionType,
    DefensiveMitigationRule,
    defensive_engine,
)


class ProposeDefensiveRuleRequest(BaseModel):
    target_ip_or_cidr: str = Field(
        ..., description="Target IPv4, IPv6, or CIDR network"
    )
    action_type: DefensiveActionType = Field(default=DefensiveActionType.RATE_LIMIT)
    rate_limit_rps: int = Field(default=10, ge=1, le=50000)
    burst_capacity: int = Field(default=20, ge=1, le=50000)
    ttl_seconds: int = Field(default=600, ge=30, le=86400)
    reason: str = Field(default="Suspicious traffic pattern detected")
    dry_run: bool = Field(default=True, description="Staged Dry-Run mode by default")


@router.post(
    "/mitigations/defensive/propose",
    response_model=DefensiveMitigationRule,
    status_code=status.HTTP_201_CREATED,
    summary="Propose a new defensive mitigation policy (Defaults to safe Dry-Run mode)",
)
def propose_defensive_rule(
    payload: ProposeDefensiveRuleRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> DefensiveMitigationRule:
    """Create a defensive mitigation rule.

    Rejects protected infrastructure allowlist IPs. Mitigations start in Dry-Run
    mode to evaluate impact before live enforcement.
    """
    try:
        rule = defensive_engine.propose_rule(
            target_ip_or_cidr=payload.target_ip_or_cidr,
            action_type=payload.action_type,
            rate_limit_rps=payload.rate_limit_rps,
            burst_capacity=payload.burst_capacity,
            ttl_seconds=payload.ttl_seconds,
            reason=payload.reason,
            dry_run=payload.dry_run,
        )
        record_audit_event(
            session=session,
            event_type="defensive_rule_proposed",
            action="propose_rule",
            actor="operator_api",
            details={
                "rule_id": rule.rule_id,
                "target": rule.target_ip_or_cidr,
                "action": rule.action_type.value,
                "mode": rule.mode.value,
                "ttl_seconds": rule.ttl_seconds,
                "reason": rule.reason,
            },
        )
        return rule
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.get(
    "/mitigations/defensive/rules",
    response_model=list[DefensiveMitigationRule],
    summary="List all active and dry-run defensive mitigation rules",
)
def get_defensive_rules(
    include_expired: Annotated[
        bool, Query(description="Include expired rules in response")
    ] = False,
) -> list[DefensiveMitigationRule]:
    """Return all active defensive mitigation rules with remaining TTL countdowns."""
    return defensive_engine.get_rules(include_expired=include_expired)


@router.post(
    "/mitigations/defensive/{rule_id}/approve",
    response_model=DefensiveMitigationRule,
    summary="Operator approval to promote a dry-run rule to active enforcement",
)
def approve_defensive_rule(
    rule_id: Annotated[str, Path(description="Defensive rule ID to approve")],
    session: Annotated[Session, Depends(get_db_session)],
) -> DefensiveMitigationRule:
    """Operator human-in-the-loop approval step to promote a rule from Dry-Run to Active."""
    try:
        rule = defensive_engine.approve_rule(rule_id=rule_id, operator="admin_operator")
        record_audit_event(
            session=session,
            event_type="defensive_rule_approved",
            action="approve_rule",
            actor="admin_operator",
            details={
                "rule_id": rule.rule_id,
                "target": rule.target_ip_or_cidr,
                "mode": "ACTIVE",
                "action": rule.action_type.value,
            },
        )
        return rule
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.post(
    "/mitigations/defensive/{rule_id}/revoke",
    summary="Immediately cancel or revoke an active or dry-run defense rule",
)
def revoke_defensive_rule(
    rule_id: Annotated[str, Path(description="Defensive rule ID to revoke")],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, str]:
    """Revoke and cancel a defensive rule."""
    revoked = defensive_engine.revoke_rule(rule_id=rule_id)
    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule '{rule_id}' not found.",
        )
    record_audit_event(
        session=session,
        event_type="defensive_rule_revoked",
        action="revoke_rule",
        actor="operator_api",
        details={"rule_id": rule_id},
    )
    return {"status": "revoked", "rule_id": rule_id}


@router.get(
    "/mitigations/export/nginx",
    response_class=PlainTextResponse,
    summary="Export active defensive policies as production-grade Nginx configuration",
)
def export_nginx_mitigations() -> PlainTextResponse:
    """Generate and download ready-to-mount Nginx blocklist and rate-limit configuration snippet."""
    rules = defensive_engine.get_rules(include_expired=False)
    content = export_nginx_config(rules)
    return PlainTextResponse(
        content=content,
        media_type="text/plain",
        headers={
            "Content-Disposition": "attachment; filename=sentrix_nginx_defense.conf"
        },
    )


@router.get(
    "/mitigations/export/caddy",
    response_class=PlainTextResponse,
    summary="Export active defensive policies as Caddyfile configuration",
)
def export_caddy_mitigations() -> PlainTextResponse:
    """Generate and download Caddy route matcher snippet."""
    rules = defensive_engine.get_rules(include_expired=False)
    content = export_caddy_config(rules)
    return PlainTextResponse(
        content=content,
        media_type="text/plain",
        headers={
            "Content-Disposition": "attachment; filename=Caddyfile_sentrix.snippet"
        },
    )
