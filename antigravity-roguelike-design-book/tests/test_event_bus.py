"""
Unit tests for the multi-phase event bus and recursion limiter.
"""

import unittest
from pyrogue_emergent.core.event_bus import EventBus, Event, Phase


class SampleEvent(Event):
    pass


class TestEventBus(unittest.TestCase):
    def test_phased_dispatch(self) -> None:
        bus = EventBus()
        execution_order: list[Phase] = []

        for p in Phase:
            bus.subscribe(SampleEvent, p, lambda e, ph, p_curr=p: execution_order.append(p_curr))

        event = SampleEvent()
        success = bus.dispatch_full_pipeline(event)

        self.assertTrue(success)
        self.assertEqual(
            execution_order,
            [Phase.VALIDATE, Phase.INTENTION, Phase.EXECUTE, Phase.REACTION, Phase.CASCADE]
        )

    def test_cancellation_during_validation(self) -> None:
        bus = EventBus()

        def validator(e: SampleEvent, ph: Phase) -> None:
            e.cancel("Invalid move")

        executed = False
        def executor(e: SampleEvent, ph: Phase) -> None:
            nonlocal executed
            executed = True

        bus.subscribe(SampleEvent, Phase.VALIDATE, validator)
        bus.subscribe(SampleEvent, Phase.EXECUTE, executor)

        event = SampleEvent()
        success = bus.dispatch_full_pipeline(event)

        self.assertFalse(success)
        self.assertTrue(event.cancelled)
        self.assertFalse(executed)

    def test_cascade_recursion_limit(self) -> None:
        bus = EventBus(max_cascade_depth=3)
        cascades_run = 0

        def cascade_handler(e: SampleEvent, ph: Phase) -> None:
            nonlocal cascades_run
            cascades_run += 1
            # Recursively queue child cascade
            child = SampleEvent()
            bus.queue_cascade(child, e)

        bus.subscribe(SampleEvent, Phase.CASCADE, cascade_handler)

        root_event = SampleEvent()
        bus.dispatch_full_pipeline(root_event)
        bus.flush_cascades()

        # Root (0) -> Depth 1 -> Depth 2 -> Depth 3 -> Stop at Depth 4
        self.assertEqual(cascades_run, 4)


if __name__ == "__main__":
    unittest.main()
