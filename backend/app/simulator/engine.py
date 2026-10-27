"""Scenario Engine coordinating deterministic simulation ticks and ground truth."""

from __future__ import annotations

import random
from collections.abc import Iterator

from app.simulator.generator import generate_tick_traffic
from app.simulator.scenarios import GroundTruth, ScenarioConfig


class ScenarioEngine:
    """Deterministic PRNG-based scenario engine.

    Guarantees:
    - Same seed + same configuration -> 100% byte-identical records across runs and platforms.
    - Zero label leakage: Ground truth is never injected into the feature dictionary.
    - Zero host networking: Generation is pure in-memory mathematics.
    """

    def __init__(self, config: ScenarioConfig) -> None:
        self.config = config
        self.total_ticks = config.total_ticks

    def _get_seeded_prng(self, tick: int) -> random.Random:
        """Create a tick-specific deterministic PRNG.

        Combining the master seed with the tick index ensures that tick N is
        independent of whether earlier ticks were skipped or stepped through.
        """
        combined_seed = (self.config.seed * 1_000_003 + tick) & 0xFFFFFFFF
        return random.Random(combined_seed)

    def generate_tick(self, tick: int) -> tuple[dict[str, float], GroundTruth]:
        """Generate the traffic observation and ground truth for a specific tick index."""
        if tick < 0 or tick > self.total_ticks:
            raise ValueError(
                f"Tick index {tick} is out of bounds for simulation duration (0..{self.total_ticks})"
            )

        prng = self._get_seeded_prng(tick)
        return generate_tick_traffic(self.config, tick, prng)

    def iter_ticks(self) -> Iterator[tuple[int, dict[str, float], GroundTruth]]:
        """Yield all simulation ticks in sequence."""
        for tick in range(self.total_ticks + 1):
            features, ground_truth = self.generate_tick(tick)
            yield tick, features, ground_truth

    def generate_all(self) -> list[tuple[dict[str, float], GroundTruth]]:
        """Precompute or collect all ticks as a list."""
        return [self.generate_tick(tick) for tick in range(self.total_ticks + 1)]
