"""A simple message log used to show game events to the player."""
from __future__ import annotations


class MessageLog:
    """Collects textual messages and keeps only the most recent ones."""

    def __init__(self, capacity: int = 8) -> None:
        self.capacity = capacity
        self.messages: list[str] = []

    def add(self, message: str) -> None:
        if not message:
            return
        self.messages.append(message)
        while len(self.messages) > self.capacity:
            self.messages.pop(0)

    def __iter__(self):
        return iter(self.messages)

    def __len__(self) -> int:
        return len(self.messages)
