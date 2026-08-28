from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

import tcod.event

from .actions import (
    Action,
    CancelAction,
    DropAction,
    DropItemAction,
    EquipAction,
    EquipmentAction,
    ExitAction,
    InventoryAction,
    LevelUpAction,
    LookAction,
    LogAction,
    MoveAction,
    PickupAction,
    SelectAction,
    UseAction,
    WaitAction,
)

if TYPE_CHECKING:
    from tcod.ecs import World


class MenuState(Enum):
    PLAY = auto()
    INVENTORY = auto()
    EQUIPMENT = auto()
    DROP = auto()
    LOOK = auto()
    LOG_HISTORY = auto()
    LEVEL_UP = auto()
    DEATH = auto()


class InputHandler(tcod.event.EventDispatch[Action]):
    def __init__(self, world: World) -> None:
        self.world = world
        self.menu_state = MenuState.PLAY
        self.look_cursor_x = 0
        self.look_cursor_y = 0
        self.selected_index = 0
        self.has_cursor_been_set = False

    def set_look_cursor(self, x: int, y: int) -> None:
        if not self.has_cursor_been_set:
            self.look_cursor_x = x
            self.look_cursor_y = y
            self.has_cursor_been_set = True

    def reset_cursor(self) -> None:
        self.has_cursor_been_set = False

    def handle_events(self) -> Action | None:
        action: Action | None = None

        for event in tcod.event.wait():
            action = self.dispatch(event)

        return action

    def ev_keydown(self, event: tcod.event.KeyDown) -> Action | None:
        key = event.sym
        modifier = event.mod

        if self.menu_state == MenuState.PLAY:
            return self._handle_play(key, modifier)
        elif self.menu_state == MenuState.INVENTORY:
            return self._handle_inventory(key, modifier)
        elif self.menu_state == MenuState.EQUIPMENT:
            return self._handle_equipment(key, modifier)
        elif self.menu_state == MenuState.DROP:
            return self._handle_drop(key, modifier)
        elif self.menu_state == MenuState.LOOK:
            return self._handle_look(key, modifier)
        elif self.menu_state == MenuState.LOG_HISTORY:
            return self._handle_log_history(key, modifier)
        elif self.menu_state == MenuState.LEVEL_UP:
            return self._handle_level_up(key, modifier)
        elif self.menu_state == MenuState.DEATH:
            return self._handle_death(key, modifier)

        return None

    def _handle_play(self, key: tcod.event.KeySym, modifier: int) -> Action | None:
        move_keys = {
            tcod.event.KeySym.UP: (0, -1),
            tcod.event.KeySym.DOWN: (0, 1),
            tcod.event.KeySym.LEFT: (-1, 0),
            tcod.event.KeySym.RIGHT: (1, 0),
            tcod.event.KeySym.HOME: (-1, -1),
            tcod.event.KeySym.END: (1, -1),
            tcod.event.KeySym.PAGEUP: (-1, 1),
            tcod.event.KeySym.PAGEDOWN: (1, 1),
            tcod.event.KeySym.KP_1: (-1, 1),
            tcod.event.KeySym.KP_2: (0, 1),
            tcod.event.KeySym.KP_3: (1, 1),
            tcod.event.KeySym.KP_4: (-1, 0),
            tcod.event.KeySym.KP_6: (1, 0),
            tcod.event.KeySym.KP_7: (-1, -1),
            tcod.event.KeySym.KP_8: (0, -1),
            tcod.event.KeySym.KP_9: (1, -1),
            tcod.event.KeySym.y: (-1, -1),
            tcod.event.KeySym.u: (1, -1),
            tcod.event.KeySym.b: (-1, 1),
            tcod.event.KeySym.n: (1, 1),
            tcod.event.KeySym.h: (-1, 0),
            tcod.event.KeySym.j: (0, 1),
            tcod.event.KeySym.k: (0, -1),
            tcod.event.KeySym.l: (1, 0),
        }

        if key in move_keys:
            dx, dy = move_keys[key]
            return MoveAction(dx=dx, dy=dy)
        elif key == tcod.event.KeySym.PERIOD and (modifier & tcod.event.Modifier.SHIFT):
            return PickupAction()
        elif key == tcod.event.KeySym.i:
            self.menu_state = MenuState.INVENTORY
            self.selected_index = 0
            return InventoryAction()
        elif key == tcod.event.KeySym.e:
            self.menu_state = MenuState.EQUIPMENT
            self.selected_index = 0
            return EquipmentAction()
        elif key == tcod.event.KeySym.d:
            self.menu_state = MenuState.DROP
            self.selected_index = 0
            return DropAction()
        elif key == tcod.event.KeySym.v:
            self.menu_state = MenuState.LOOK
            player = self.world["player"]
            player_pos = self.world[player, "Position"]
            self.set_look_cursor(player_pos.x, player_pos.y)
            return LookAction()
        elif key == tcod.event.KeySym.z:
            self.menu_state = MenuState.LOG_HISTORY
            self.selected_index = 0
            return LogAction()
        elif key == tcod.event.KeySym.PERIOD:
            return WaitAction()
        elif key == tcod.event.KeySym.ESCAPE:
            return ExitAction()
        elif key == tcod.event.KeySym.g:
            return PickupAction()

        return None

    def _handle_inventory(self, key: tcod.event.KeySym, modifier: int) -> Action | None:
        player = self.world["player"]
        inventory = self.world[player, "Inventory"]

        if key == tcod.event.KeySym.ESCAPE:
            self.menu_state = MenuState.PLAY
            return CancelAction()
        elif key == tcod.event.KeySym.j or key == tcod.event.KeySym.DOWN:
            if inventory.items:
                self.selected_index = (self.selected_index + 1) % len(inventory.items)
        elif key == tcod.event.KeySym.k or key == tcod.event.KeySym.UP:
            if inventory.items:
                self.selected_index = (self.selected_index - 1) % len(inventory.items)
        elif key == tcod.event.KeySym.RETURN:
            if inventory.items and self.selected_index < len(inventory.items):
                item_id = inventory.items[self.selected_index]
                self.menu_state = MenuState.PLAY
                return UseAction(item_id=item_id)

        return None

    def _handle_equipment(self, key: tcod.event.KeySym, modifier: int) -> Action | None:
        player = self.world["player"]
        inventory = self.world[player, "Inventory"]

        if key == tcod.event.KeySym.ESCAPE:
            self.menu_state = MenuState.PLAY
            return CancelAction()
        elif key == tcod.event.KeySym.j or key == tcod.event.KeySym.DOWN:
            if inventory.items:
                self.selected_index = (self.selected_index + 1) % len(inventory.items)
        elif key == tcod.event.KeySym.k or key == tcod.event.KeySym.UP:
            if inventory.items:
                self.selected_index = (self.selected_index - 1) % len(inventory.items)
        elif key == tcod.event.KeySym.RETURN:
            if inventory.items and self.selected_index < len(inventory.items):
                item_id = inventory.items[self.selected_index]
                self.menu_state = MenuState.PLAY
                return EquipAction(item_id=item_id)

        return None

    def _handle_drop(self, key: tcod.event.KeySym, modifier: int) -> Action | None:
        player = self.world["player"]
        inventory = self.world[player, "Inventory"]

        if key == tcod.event.KeySym.ESCAPE:
            self.menu_state = MenuState.PLAY
            return CancelAction()
        elif key == tcod.event.KeySym.j or key == tcod.event.KeySym.DOWN:
            if inventory.items:
                self.selected_index = (self.selected_index + 1) % len(inventory.items)
        elif key == tcod.event.KeySym.k or key == tcod.event.KeySym.UP:
            if inventory.items:
                self.selected_index = (self.selected_index - 1) % len(inventory.items)
        elif key == tcod.event.KeySym.RETURN:
            if inventory.items and self.selected_index < len(inventory.items):
                item_id = inventory.items[self.selected_index]
                self.menu_state = MenuState.PLAY
                return DropItemAction(item_id=item_id)

        return None

    def _handle_look(self, key: tcod.event.KeySym, modifier: int) -> Action | None:
        look_keys = {
            tcod.event.KeySym.UP: (0, -1),
            tcod.event.KeySym.DOWN: (0, 1),
            tcod.event.KeySym.LEFT: (-1, 0),
            tcod.event.KeySym.RIGHT: (1, 0),
            tcod.event.KeySym.h: (-1, 0),
            tcod.event.KeySym.j: (0, 1),
            tcod.event.KeySym.k: (0, -1),
            tcod.event.KeySym.l: (1, 0),
            tcod.event.KeySym.y: (-1, -1),
            tcod.event.KeySym.u: (1, -1),
            tcod.event.KeySym.b: (-1, 1),
            tcod.event.KeySym.n: (1, 1),
        }

        if key in look_keys:
            dx, dy = look_keys[key]
            self.look_cursor_x += dx
            self.look_cursor_y += dy
            return None
        elif key == tcod.event.KeySym.ESCAPE or key == tcod.event.KeySym.v:
            self.menu_state = MenuState.PLAY
            self.reset_cursor()
            return CancelAction()

        return None

    def _handle_log_history(self, key: tcod.event.KeySym, modifier: int) -> Action | None:
        if key == tcod.event.KeySym.ESCAPE or key == tcod.event.KeySym.z:
            self.menu_state = MenuState.PLAY
            return CancelAction()
        elif key == tcod.event.KeySym.j or key == tcod.event.KeySym.DOWN:
            self.selected_index += 1
        elif key == tcod.event.KeySym.k or key == tcod.event.KeySym.UP:
            self.selected_index = max(0, self.selected_index - 1)

        return None

    def _handle_level_up(self, key: tcod.event.KeySym, modifier: int) -> Action | None:
        if key == tcod.event.KeySym.a:
            return LevelUpAction(stat="hp")
        elif key == tcod.event.KeySym.b:
            return LevelUpAction(stat="power")
        elif key == tcod.event.KeySym.c:
            return LevelUpAction(stat="defense")

        return None

    def _handle_death(self, key: tcod.event.KeySym, modifier: int) -> Action | None:
        return ExitAction()

    def ev_mousemotion(self, event: tcod.event.MouseMotion) -> Action | None:
        if self.menu_state == MenuState.LOOK:
            self.look_cursor_x = event.tile.x
            self.look_cursor_y = event.tile.y
        return None

    def ev_mousebuttondown(self, event: tcod.event.MouseButtonDown) -> Action | None:
        if self.menu_state == MenuState.PLAY:
            if event.button == tcod.event.MouseButton.RIGHT:
                return LookAction()
        return None
