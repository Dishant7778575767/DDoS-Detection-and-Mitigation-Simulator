"""SENTRIX Time-Window Aggregation Logic.

Maintains sliding time-windows of recent network observations to extract short-term
traffic statistics (packet rates, byte rates, SYN ratios, burst factors) for hybrid
detection and policy evaluation.
"""

from __future__ import annotations

import collections
from dataclasses import dataclass


@dataclass
class FlowObservation:
    """Individual flow snapshot recorded in the sliding window."""

    timestamp: float
    packet_count: int
    byte_count: int
    syn_flags: int = 0
    ack_flags: int = 0
    source_ip: str | None = None


@dataclass
class WindowSummary:
    """Summary statistics aggregated over an active time window."""

    window_duration_seconds: float
    observation_count: int
    packet_rate: float
    byte_rate: float
    syn_rate: float
    syn_ack_ratio: float
    unique_sources: int
    is_burst: bool = False


class SlidingWindowAggregator:
    """Maintains a sliding time-window buffer of flow records."""

    def __init__(
        self, window_duration_seconds: float = 10.0, max_observations: int = 50_000
    ):
        if window_duration_seconds <= 0:
            raise ValueError("window_duration_seconds must be positive")
        self.window_duration_seconds = window_duration_seconds
        self.max_observations = max_observations
        self.buffer: collections.deque[FlowObservation] = collections.deque(
            maxlen=max_observations
        )

    def add_observation(
        self,
        timestamp: float,
        packet_count: int,
        byte_count: int,
        syn_flags: int = 0,
        ack_flags: int = 0,
        source_ip: str | None = None,
    ) -> None:
        """Add a flow observation to the sliding window buffer."""
        obs = FlowObservation(
            timestamp=float(timestamp),
            packet_count=max(0, int(packet_count)),
            byte_count=max(0, int(byte_count)),
            syn_flags=max(0, int(syn_flags)),
            ack_flags=max(0, int(ack_flags)),
            source_ip=str(source_ip).strip() if source_ip else None,
        )
        self.buffer.append(obs)
        self._prune(obs.timestamp)

    def _prune(self, current_timestamp: float) -> None:
        """Discard observations older than current_timestamp - window_duration_seconds."""
        cutoff = current_timestamp - self.window_duration_seconds
        while self.buffer and self.buffer[0].timestamp < cutoff:
            self.buffer.popleft()

    def get_summary(self, current_timestamp: float) -> WindowSummary:
        """Compute aggregated rates and statistics over the active window."""
        self._prune(current_timestamp)

        if not self.buffer:
            return WindowSummary(
                window_duration_seconds=self.window_duration_seconds,
                observation_count=0,
                packet_rate=0.0,
                byte_rate=0.0,
                syn_rate=0.0,
                syn_ack_ratio=0.0,
                unique_sources=0,
                is_burst=False,
            )

        total_packets = 0
        total_bytes = 0
        total_syn = 0
        total_ack = 0
        sources: set[str] = set()

        for obs in self.buffer:
            total_packets += obs.packet_count
            total_bytes += obs.byte_count
            total_syn += obs.syn_flags
            total_ack += obs.ack_flags
            if obs.source_ip:
                sources.add(obs.source_ip)

        duration = max(self.window_duration_seconds, 1.0)
        packet_rate = total_packets / duration
        byte_rate = total_bytes / duration
        syn_rate = total_syn / duration
        syn_ack_ratio = (total_syn / total_ack) if total_ack > 0 else float(total_syn)

        return WindowSummary(
            window_duration_seconds=self.window_duration_seconds,
            observation_count=len(self.buffer),
            packet_rate=packet_rate,
            byte_rate=byte_rate,
            syn_rate=syn_rate,
            syn_ack_ratio=syn_ack_ratio,
            unique_sources=len(sources),
            is_burst=syn_rate > 500.0 or packet_rate > 5000.0,
        )

    def reset(self) -> None:
        """Clear all buffered observations."""
        self.buffer.clear()
