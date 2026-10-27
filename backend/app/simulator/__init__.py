"""SENTRIX Simulation Engine package."""

from app.simulator.engine import ScenarioEngine
from app.simulator.generator import generate_tick_traffic
from app.simulator.manager import SimulationRunManager
from app.simulator.mitigation_effects import (
    MitigationEffectManager,
    VirtualMitigation,
)
from app.simulator.scenarios import GroundTruth, ScenarioConfig, ScenarioType
from app.simulator.scorecard import SimulationScorecard, compute_scorecard
from app.simulator.tick_evaluator import TickEvaluationResult, TickEvaluator
from app.simulator.victim import VictimMetrics, VirtualVictim, VirtualVictimConfig

__all__ = [
    "GroundTruth",
    "MitigationEffectManager",
    "ScenarioConfig",
    "ScenarioEngine",
    "ScenarioType",
    "SimulationRunManager",
    "SimulationScorecard",
    "TickEvaluationResult",
    "TickEvaluator",
    "VictimMetrics",
    "VirtualMitigation",
    "VirtualVictim",
    "VirtualVictimConfig",
    "compute_scorecard",
    "generate_tick_traffic",
]
