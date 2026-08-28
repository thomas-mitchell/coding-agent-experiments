"""
Multi-phase, priority-ordered event dispatcher with recursion guard and causality tracking.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, TypeVar, Generic
import uuid


class Phase(Enum):
    """
    Phases of event resolution in an emergent interaction pipeline.
    """
    VALIDATE = auto()   # Check if action can proceed; listeners can cancel or mutate
    INTENTION = auto()  # Pre-execution hooks (e.g. reactive shields, telegraphs)
    EXECUTE = auto()    # Primary state mutation occurs
    REACTION = auto()   # Direct immediate secondary reactions
    CASCADE = auto()    # Asynchronous or queued consequential interactions


@dataclass
class Event:
    """Base event payload with unique ID and causality tracking."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    parent_id: str | None = None
    cancelled: bool = False
    cancel_reason: str = ""
    depth: int = 0
    data: dict[str, Any] = field(default_factory=dict)

    def cancel(self, reason: str = "") -> None:
        self.cancelled = True
        self.cancel_reason = reason


E = TypeVar("E", bound=Event)
EventHandler = Callable[[E, Phase], None]


@dataclass(order=True)
class _PrioritizedHandler:
    priority: int
    handler: EventHandler = field(compare=False)


class EventBus:
    """
    Central event dispatcher supporting phased processing, priorities,
    depth limits (infinite loop guards), and causality logging.
    """
    def __init__(self, max_cascade_depth: int = 12) -> None:
        self._handlers: dict[type[Event], dict[Phase, list[_PrioritizedHandler]]] = {}
        self.max_cascade_depth = max_cascade_depth
        self.history: list[Event] = []
        self._queue: list[Event] = []

    def subscribe(
        self,
        event_type: type[Event],
        phase: Phase,
        handler: EventHandler,
        priority: int = 100,
    ) -> None:
        """
        Subscribes a handler to an event type during a specific phase.
        Lower priority number executes first (e.g. 10 runs before 100).
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = {p: [] for p in Phase}
        handlers_list = self._handlers[event_type][phase]
        handlers_list.append(_PrioritizedHandler(priority=priority, handler=handler))
        handlers_list.sort(key=lambda h: h.priority)

    def dispatch_phase(self, event: E, phase: Phase) -> bool:
        """
        Dispatches an event through all handlers subscribed to the given phase.
        Returns True if the event was NOT cancelled.
        """
        if event.depth > self.max_cascade_depth:
            event.cancel(f"Max cascade depth ({self.max_cascade_depth}) exceeded")
            return False

        # Execute registered handlers for exact type and its superclasses
        for ev_cls in type(event).__mro__:
            if issubclass(ev_cls, Event) and ev_cls in self._handlers:
                phase_handlers = self._handlers[ev_cls][phase]
                for ph in phase_handlers:
                    if event.cancelled and phase != Phase.VALIDATE:
                        break
                    ph.handler(event, phase)

        return not event.cancelled

    def dispatch_full_pipeline(self, event: E) -> bool:
        """
        Executes a complete 5-phase pipeline for an event:
        VALIDATE -> INTENTION -> EXECUTE -> REACTION -> CASCADE (queued).
        """
        self.history.append(event)

        # 1. Validation
        if not self.dispatch_phase(event, Phase.VALIDATE):
            return False

        # 2. Intention
        if not self.dispatch_phase(event, Phase.INTENTION):
            return False

        # 3. Execution
        if not self.dispatch_phase(event, Phase.EXECUTE):
            return False

        # 4. Immediate Reaction
        self.dispatch_phase(event, Phase.REACTION)

        # 5. Cascades
        self.dispatch_phase(event, Phase.CASCADE)
        return True

    def queue_cascade(self, event: Event, parent: Event) -> None:
        """Enqueues a secondary cascade event spawned by a parent event."""
        event.parent_id = parent.event_id
        event.depth = parent.depth + 1
        if event.depth <= self.max_cascade_depth:
            self._queue.append(event)

    def flush_cascades(self) -> None:
        """Processes all enqueued cascade events until the queue is exhausted."""
        while self._queue:
            next_event = self._queue.pop(0)
            self.dispatch_full_pipeline(next_event)
