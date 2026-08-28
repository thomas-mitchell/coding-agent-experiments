"""A simple message log used to show game events to the player."""
from __future__ import annotations

DEFAULT_COLOR = (200, 200, 200)


class MessageLog:
    """Collects textual messages (with colors) and keeps only the most recent ones."""

    def __init__(self, capacity: int = 8) -> None:
        self.capacity = capacity
        self.messages: list[tuple[str, tuple[int, int, int]]] = []

    def add(self, message: str, color: tuple[int, int, int] = DEFAULT_COLOR) -> None:
        if not message:
            return
        self.messages.append((message, color))
        while len(self.messages) > self.capacity:
            self.messages.pop(0)

    def __iter__(self):
        return iter(self.messages)

    def __len__(self) -> int:
        return len(self.messages)
