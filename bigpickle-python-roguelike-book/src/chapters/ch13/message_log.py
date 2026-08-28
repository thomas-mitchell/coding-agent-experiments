"""Message log for combat and game messages."""
from __future__ import annotations

import attrs


@attrs.define
class Message:
    text: str
    color: tuple[int, int, int] = (255, 255, 255)


@attrs.define
class MessageLog:
    messages: list[Message] = attrs.Factory(list)
    max_messages: int = 50

    def add(self, text: str, color: tuple[int, int, int] = (255, 255, 255)) -> None:
        self.messages.append(Message(text=text, color=color))
        if len(self.messages) > self.max_messages:
            self.messages.pop(0)

    @property
    def recent(self) -> list[Message]:
        return self.messages[-5:]  # Last 5 messages
