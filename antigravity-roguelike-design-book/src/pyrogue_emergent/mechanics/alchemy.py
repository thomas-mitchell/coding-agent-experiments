"""
Chemical alchemy, reagent transformation, and fluid mixing dynamics.
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
from pyrogue_emergent.world.grid import FluidType, GasType


@dataclass(frozen=True)
class ReactionResult:
    resulting_fluid: FluidType
    resulting_volume: int
    resulting_gas: GasType = GasType.NONE
    gas_amount: int = 0
    temperature_delta: int = 0
    message: str = ""


class AlchemySystem:
    """
    Evaluates dynamic chemical reactions between fluids, catalysts, and gases.
    """
    @staticmethod
    def mix_fluids(
        fluid_a: FluidType, vol_a: int,
        fluid_b: FluidType, vol_b: int,
        ambient_temp: int = 20
    ) -> ReactionResult:
        """
        Calculates the thermodynamic and chemical outcome of mixing two fluids.
        """
        if fluid_a == FluidType.NONE:
            return ReactionResult(fluid_b, vol_b)
        if fluid_b == FluidType.NONE:
            return ReactionResult(fluid_a, vol_a)
        if fluid_a == fluid_b:
            return ReactionResult(fluid_a, vol_a + vol_b)

        pair = {fluid_a, fluid_b}

        # Acid + Water: exothermic dilution
        if pair == {FluidType.ACID, FluidType.WATER}:
            total_vol = vol_a + vol_b
            return ReactionResult(
                resulting_fluid=FluidType.WATER,
                resulting_volume=total_vol,
                resulting_gas=GasType.STEAM,
                gas_amount=20,
                temperature_delta=40,
                message="Acid violently hissed as it was diluted by water, sending up acrid steam!"
            )

        # Oil + Water: immiscible (oil sits on top, preserves total volume)
        if pair == {FluidType.OIL, FluidType.WATER}:
            return ReactionResult(
                resulting_fluid=FluidType.OIL if vol_a >= vol_b else FluidType.WATER,
                resulting_volume=vol_a + vol_b,
                message="Oil and water formed separated layers across the floor."
            )

        # Alcohol + Acid: volatile reaction
        if pair == {FluidType.ALCOHOL, FluidType.ACID}:
            return ReactionResult(
                resulting_fluid=FluidType.NONE,
                resulting_volume=0,
                resulting_gas=GasType.POISON_GAS,
                gas_amount=60,
                temperature_delta=60,
                message="Alcohol and acid synthesized violently into a billowing toxic vapor cloud!"
            )

        # Default fallback: dominant fluid volume
        dominant = fluid_a if vol_a >= vol_b else fluid_b
        return ReactionResult(dominant, vol_a + vol_b)
