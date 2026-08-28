"""
Utility AI architecture for evaluating actions and exploiting environmental hazards.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Callable
from pyrogue_emergent.core.math2d import Vec2
from pyrogue_emergent.ecs.entity import EntityManager
from pyrogue_emergent.ecs.components import Position, CombatStats, Faction, Physics
from pyrogue_emergent.world.grid import LayeredGrid, FluidType


@dataclass
class UtilityAction:
    action_name: str
    target_pos: Vec2 | None = None
    target_id: int | None = None
    utility_score: float = 0.0


class UtilityAI:
    """
    Scores potential actions based on creature state, proximity, and environmental opportunities.
    """
    def __init__(self, ecs: EntityManager, grid: LayeredGrid) -> None:
        self.ecs = ecs
        self.grid = grid

    def evaluate_best_action(self, actor_id: int, enemy_id: int | None) -> UtilityAction:
        """
        Evaluates potential choices and selects the highest scoring utility action.
        """
        actor_pos = self.ecs.get_component(actor_id, Position)
        actor_stats = self.ecs.get_component(actor_id, CombatStats)

        if not actor_pos or not actor_stats:
            return UtilityAction("wait", utility_score=0.0)

        best_action = UtilityAction("wait", utility_score=1.0)

        # 1. Self-preservation: Low HP triggers flee scoring
        hp_ratio = actor_stats.hp / max(1, actor_stats.max_hp)
        if hp_ratio < 0.25 and enemy_id:
            flee_score = (1.0 - hp_ratio) * 10.0
            if flee_score > best_action.utility_score:
                best_action = UtilityAction("flee", target_id=enemy_id, utility_score=flee_score)

        # 2. Environmental interaction: Ignite oil puddle if enemy is standing in oil
        if enemy_id:
            enemy_pos = self.ecs.get_component(enemy_id, Position)
            if enemy_pos:
                enemy_cell = self.grid.get_cell(enemy_pos.pos)
                if enemy_cell.fluid_type == FluidType.OIL and enemy_cell.fire_intensity == 0:
                    # High utility to ignite the oil under the enemy
                    oil_score = 8.5
                    if oil_score > best_action.utility_score:
                        best_action = UtilityAction(
                            "ignite_hazard",
                            target_pos=enemy_pos.pos,
                            utility_score=oil_score,
                        )

        # 3. Direct Melee Attack if adjacent to enemy
        if enemy_id:
            enemy_pos = self.ecs.get_component(enemy_id, Position)
            if enemy_pos and actor_pos.pos.chebyshev_dist(enemy_pos.pos) == 1:
                melee_score = 6.0
                if melee_score > best_action.utility_score:
                    best_action = UtilityAction("attack", target_id=enemy_id, utility_score=melee_score)

        # 4. Approach / Hunt Enemy
        if enemy_id and best_action.action_name == "wait":
            best_action = UtilityAction("approach", target_id=enemy_id, utility_score=4.0)

        return best_action
