from __future__ import annotations

from enum import Enum, auto


class Actions(Enum):
    MOVE = auto()
    PICKUP = auto()
    INVENTORY = auto()
    EQUIPMENT = auto()
    DROP = auto()
    LOOK = auto()
    LOG = auto()
    EXIT = auto()
    WAIT = auto()
    CONFIRM = auto()
    CANCEL = auto()
    SELECT = auto()
    USE = auto()
    EQUIP = auto()
    UNEQUIP = auto()
    CONFIRM_YES = auto()
    CONFIRM_NO = auto()
    LEVEL_UP_HP = auto()
    LEVEL_UP_POWER = auto()
    LEVEL_UP_DEFENSE = auto()


class Action:
    def __init__(self, action_type: Actions, **kwargs) -> None:
        self.action_type = action_type
        self.kwargs = kwargs

    def __repr__(self) -> str:
        return f"Action({self.action_type}, {self.kwargs})"


class MoveAction(Action):
    def __init__(self, dx: int, dy: int) -> None:
        super().__init__(Actions.MOVE, dx=dx, dy=dy)


class PickupAction(Action):
    def __init__(self) -> None:
        super().__init__(Actions.PICKUP)


class InventoryAction(Action):
    def __init__(self) -> None:
        super().__init__(Actions.INVENTORY)


class EquipmentAction(Action):
    def __init__(self) -> None:
        super().__init__(Actions.EQUIPMENT)


class DropAction(Action):
    def __init__(self) -> None:
        super().__init__(Actions.DROP)


class LookAction(Action):
    def __init__(self) -> None:
        super().__init__(Actions.LOOK)


class LogAction(Action):
    def __init__(self) -> None:
        super().__init__(Actions.LOG)


class ExitAction(Action):
    def __init__(self) -> None:
        super().__init__(Actions.EXIT)


class WaitAction(Action):
    def __init__(self) -> None:
        super().__init__(Actions.WAIT)


class ConfirmAction(Action):
    def __init__(self) -> None:
        super().__init__(Actions.CONFIRM)


class CancelAction(Action):
    def __init__(self) -> None:
        super().__init__(Actions.CANCEL)


class SelectAction(Action):
    def __init__(self, index: int) -> None:
        super().__init__(Actions.SELECT, index=index)


class UseAction(Action):
    def __init__(self, item_id: int) -> None:
        super().__init__(Actions.USE, item_id=item_id)


class EquipAction(Action):
    def __init__(self, item_id: int) -> None:
        super().__init__(Actions.EQUIP, item_id=item_id)


class DropItemAction(Action):
    def __init__(self, item_id: int) -> None:
        super().__init__(Actions.DROP, item_id=item_id)


class LevelUpAction(Action):
    def __init__(self, stat: str) -> None:
        super().__init__(Actions.LEVEL_UP_HP, stat=stat)
