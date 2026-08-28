"""Message log with attrs Message and MessageLog classes."""
from __future__ import annotations

import attrs


@attrs.define
class Message:
    """A single log entry with optional color."""

    text: str
    fg: tuple[int, int, int] = (255, 255, 255)

    @property
    def plain_text(self) -> str:
        return self.text


@attrs.define
class MessageLog:
    """Collects messages and keeps only the most recent ones."""

    messages: list[Message] = attrs.Factory(list)
    capacity: int = 8

    def add(
        self, text: str, fg: tuple[int, int, int] = (255, 255, 255)
    ) -> None:
        if not text:
            return
        self.messages.append(Message(text=text, fg=fg))
        while len(self.messages) > self.capacity:
            self.messages.pop(0)

    def __iter__(self):
        return iter(self.messages)

    def __len__(self) -> int:
        return len(self.messages)
