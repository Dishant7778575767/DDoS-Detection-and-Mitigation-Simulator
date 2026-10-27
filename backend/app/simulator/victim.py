"""Virtual victim capacity model and resource pressure calculations.

Part of Phase 8 (Work Package 8.1): Models virtual bandwidth, concurrent connections,
CPU processing capacity, synthetic queue latency, drops, and availability per tick.
Contains 100% pure mathematical calculations. No host or network APIs are used.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.simulator.mitigation_effects import VirtualMitigation


class VirtualVictimConfig(BaseModel):
    """Configuration for virtual victim service capacity."""

    model_config = {"extra": "forbid"}

    bandwidth_mbps: float = Field(
        default=100.0,
        ge=1.0,
        le=10000.0,
        description="Virtual bandwidth throughput capacity in Megabits per second (Mbps).",
    )
    max_active_connections: int = Field(
        default=10000,
        ge=100,
        le=1_000_000,
        description="Maximum concurrent connection slots in victim connection table.",
    )
    cpu_capacity_pps: float = Field(
        default=5000.0,
        ge=100.0,
        le=1_000_000.0,
        description="Maximum packet processing throughput in packets per second (PPS).",
    )
    baseline_latency_ms: float = Field(
        default=15.0,
        ge=1.0,
        le=500.0,
        description="Baseline network round-trip latency under zero or low load in milliseconds.",
    )
    max_latency_ms: float = Field(
        default=5000.0,
        ge=500.0,
        le=30000.0,
        description="Maximum latency cap / timeout ceiling under severe saturation in milliseconds.",
    )


class VictimMetrics(BaseModel):
    """Calculated per-tick victim capacity, load, latency, and availability metrics."""

    model_config = {"extra": "forbid"}

    tick: int = Field(..., ge=0)

    # Offered load (before victim ingress filtering)
    offered_legitimate_pps: float = Field(..., ge=0.0)
    offered_attack_pps: float = Field(..., ge=0.0)
    offered_total_pps: float = Field(..., ge=0.0)
    offered_bandwidth_mbps: float = Field(..., ge=0.0)
    offered_connections: int = Field(..., ge=0)

    # Mitigation filter effects
    blocked_attack_pps: float = Field(default=0.0, ge=0.0)
    collateral_legitimate_pps: float = Field(default=0.0, ge=0.0)

    # Served vs dropped throughput
    served_legitimate_pps: float = Field(..., ge=0.0)
    served_attack_pps: float = Field(..., ge=0.0)
    dropped_legitimate_pps: float = Field(..., ge=0.0)
    dropped_attack_pps: float = Field(..., ge=0.0)

    # Health and QoS outcomes
    latency_ms: float = Field(..., ge=0.0)
    availability_pct: float = Field(..., ge=0.0, le=100.0)

    # Utilization ratios (0.0 to 100.0%)
    bandwidth_utilization_pct: float = Field(..., ge=0.0, le=100.0)
    cpu_utilization_pct: float = Field(..., ge=0.0, le=100.0)
    connection_utilization_pct: float = Field(..., ge=0.0, le=100.0)

    # Bottleneck capacity pressure (1.0 = exactly 100% capacity; >1.0 = overloaded)
    bottleneck_pressure: float = Field(..., ge=0.0)


class VirtualVictim:
    """Pure mathematical model of a virtual victim system.

    Calculates offered vs served load, bottleneck pressure, queue latency,
    packet drops, and legitimate service availability under arbitrary traffic.
    """

    def __init__(self, config: VirtualVictimConfig | None = None) -> None:
        self.config = config or VirtualVictimConfig()

    def evaluate_tick(
        self,
        tick: int,
        offered_legitimate_pps: float,
        offered_attack_pps: float,
        active_mitigations: list[VirtualMitigation] | None = None,
        avg_legit_packet_bytes: float = 450.0,
        avg_attack_packet_bytes: float = 300.0,
    ) -> VictimMetrics:
        """Evaluate resource consumption and QoS metrics for a single simulation tick.

        Formulae and steps:
        1. Ingress filtering: Active mitigations drop an attack percentage and
           inadvertently drop a small collateral percentage of legitimate traffic.
        2. Ingress resource demand: Compute total bandwidth (Mbps), CPU (PPS),
           and concurrent connections arriving at the victim.
        3. Bottleneck pressure: rho = max(BW_util, CPU_util, Conn_util).
        4. Latency:
           - If rho <= 1.0: baseline * (1 + rho^2 * 1.5)
           - If rho > 1.0: min(max_latency, baseline * 2.5 + (rho - 1.0) * 150.0)
        5. Capacity drops & availability:
           - If rho <= 1.0: no capacity drops.
           - If rho > 1.0: service_ratio = 1.0 / rho; excess traffic dropped.
           - availability_pct = (served_legit / offered_legit) * 100.0
        """
        active_mits = [m for m in (active_mitigations or []) if m.is_active(tick)]

        # Step 1: Ingress Mitigation Filtering (FR-19)
        attack_pass_ratio = 1.0
        legit_pass_ratio = 1.0

        for mit in active_mits:
            attack_pass_ratio *= 1.0 - mit.attack_reduction_rate
            legit_pass_ratio *= 1.0 - mit.collateral_drop_rate

        blocked_attack_pps = offered_attack_pps * (1.0 - attack_pass_ratio)
        collateral_legit_pps = offered_legitimate_pps * (1.0 - legit_pass_ratio)

        ingress_attack_pps = offered_attack_pps * attack_pass_ratio
        ingress_legit_pps = offered_legitimate_pps * legit_pass_ratio
        ingress_total_pps = ingress_attack_pps + ingress_legit_pps

        # Step 2: Resource calculations
        # Bandwidth calculation (bits/sec -> Mbps)
        offered_bps = (
            offered_legitimate_pps * avg_legit_packet_bytes
            + offered_attack_pps * avg_attack_packet_bytes
        ) * 8.0
        offered_bandwidth_mbps = round(offered_bps / 1_000_000.0, 4)

        ingress_bps = (
            ingress_legit_pps * avg_legit_packet_bytes
            + ingress_attack_pps * avg_attack_packet_bytes
        ) * 8.0
        ingress_bandwidth_mbps = ingress_bps / 1_000_000.0

        # Concurrent connections: legitimate connections hold ~2s on avg; attack holds ~4s
        offered_connections = int(
            offered_legitimate_pps * 2.0 + offered_attack_pps * 4.0
        )
        ingress_connections = int(ingress_legit_pps * 2.0 + ingress_attack_pps * 4.0)

        # Step 3: Capacity pressures
        bw_pressure = ingress_bandwidth_mbps / self.config.bandwidth_mbps
        cpu_pressure = ingress_total_pps / self.config.cpu_capacity_pps
        conn_pressure = ingress_connections / self.config.max_active_connections

        bottleneck_pressure = max(bw_pressure, cpu_pressure, conn_pressure)

        # Step 4: Synthetic latency model
        if bottleneck_pressure <= 1.0:
            # Low to moderate load: slight polynomial queueing delay
            latency_ms = self.config.baseline_latency_ms * (
                1.0 + (bottleneck_pressure**2) * 1.5
            )
        else:
            # Overloaded: buffer queue saturation and retransmission delays
            excess = bottleneck_pressure - 1.0
            latency_ms = min(
                self.config.max_latency_ms,
                self.config.baseline_latency_ms * 2.5 + excess * 150.0,
            )

        # Step 5: Capacity drops & Served throughput
        if bottleneck_pressure <= 1.0:
            # Victim capacity satisfies all ingress traffic
            served_legit_pps = ingress_legit_pps
            served_attack_pps = ingress_attack_pps
            capacity_dropped_legit = 0.0
            capacity_dropped_attack = 0.0
        else:
            # Over capacity: indiscriminate tail drop at the victim
            service_ratio = 1.0 / bottleneck_pressure
            served_legit_pps = ingress_legit_pps * service_ratio
            served_attack_pps = ingress_attack_pps * service_ratio
            capacity_dropped_legit = ingress_legit_pps - served_legit_pps
            capacity_dropped_attack = ingress_attack_pps - served_attack_pps

        total_dropped_legit = collateral_legit_pps + capacity_dropped_legit
        total_dropped_attack = blocked_attack_pps + capacity_dropped_attack

        # Step 6: Availability calculation
        if offered_legitimate_pps > 0.0:
            availability_pct = (served_legit_pps / offered_legitimate_pps) * 100.0
            availability_pct = round(max(0.0, min(100.0, availability_pct)), 2)
        else:
            availability_pct = 100.0

        # Step 7: Display utilization percentages (capped at 100%)
        bw_util_pct = round(min(100.0, bw_pressure * 100.0), 2)
        cpu_util_pct = round(min(100.0, cpu_pressure * 100.0), 2)
        conn_util_pct = round(min(100.0, conn_pressure * 100.0), 2)

        return VictimMetrics(
            tick=tick,
            offered_legitimate_pps=round(offered_legitimate_pps, 2),
            offered_attack_pps=round(offered_attack_pps, 2),
            offered_total_pps=round(offered_legitimate_pps + offered_attack_pps, 2),
            offered_bandwidth_mbps=offered_bandwidth_mbps,
            offered_connections=offered_connections,
            blocked_attack_pps=round(blocked_attack_pps, 2),
            collateral_legitimate_pps=round(collateral_legit_pps, 2),
            served_legitimate_pps=round(served_legit_pps, 2),
            served_attack_pps=round(served_attack_pps, 2),
            dropped_legitimate_pps=round(total_dropped_legit, 2),
            dropped_attack_pps=round(total_dropped_attack, 2),
            latency_ms=round(latency_ms, 2),
            availability_pct=availability_pct,
            bandwidth_utilization_pct=bw_util_pct,
            cpu_utilization_pct=cpu_util_pct,
            connection_utilization_pct=conn_util_pct,
            bottleneck_pressure=round(bottleneck_pressure, 4),
        )
