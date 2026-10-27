"""Unit tests verifying dynamic network and server host IP resolution in mitigation status."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.mitigations import (
    get_mitigation_system_status,
    resolve_host_network_info,
)
from app.storage.database import Base


def test_resolve_host_network_info_default_local(monkeypatch) -> None:
    """In local environment without deployment env vars, returns host IP and is_deployed=False."""
    monkeypatch.delenv("RENDER_EXTERNAL_HOSTNAME", raising=False)
    monkeypatch.delenv("SERVER_IP", raising=False)
    monkeypatch.delenv("DEPLOYED_SERVER_IP", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("PRODUCTION", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)

    info = resolve_host_network_info()
    assert "host_ip" in info
    assert info["is_deployed"] is False
    assert info["environment"] == "local"
    assert "dns_gateways" in info
    assert len(info["dns_gateways"]) > 0


def test_resolve_host_network_info_deployed_render(monkeypatch) -> None:
    """When deployed on Render or cloud host, returns the deployed host IP/hostname and is_deployed=True."""
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", "sentrix-api.onrender.com")
    monkeypatch.setenv("RENDER", "true")

    info = resolve_host_network_info()
    assert info["host_ip"] == "sentrix-api.onrender.com"
    assert info["is_deployed"] is True
    assert info["environment"] == "deployed"


def test_resolve_host_network_info_custom_dns_override(monkeypatch) -> None:
    """Custom DNS_GATEWAYS environment variable is parsed dynamically."""
    monkeypatch.setenv("DNS_GATEWAYS", "9.9.9.9, 149.112.112.112")

    info = resolve_host_network_info()
    assert info["dns_gateways"] == ["9.9.9.9", "149.112.112.112"]


def test_get_mitigation_system_status_contract() -> None:
    """Contract: GET /api/v1/mitigations/status contains all dynamic network metadata and bounds."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        status_data = get_mitigation_system_status(session)

    assert "host_ip" in status_data
    assert "dns_gateways" in status_data
    assert "is_deployed" in status_data
    assert "rate_limit_bounds" in status_data
    assert status_data["rate_limit_bounds"]["min_pps"] == 100
    assert status_data["rate_limit_bounds"]["max_pps"] == 50000
    assert status_data["duration_bounds"]["min_seconds"] == 10
    assert status_data["duration_bounds"]["max_seconds"] == 300
    assert status_data["cooldown_ticks"] == 10
