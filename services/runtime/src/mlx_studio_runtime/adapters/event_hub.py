"""Small in-process fan-out for versioned Runtime events."""

import asyncio
from collections import deque
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RuntimeEvent:
    seq: int
    type: str
    payload: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"seq": self.seq, "type": self.type, "payload": self.payload}


class EventHub:
    def __init__(self) -> None:
        self._sequence = 0
        self._subscribers: set[asyncio.Queue[RuntimeEvent]] = set()
        self._history: deque[RuntimeEvent] = deque(maxlen=1024)

    async def publish(self, event_type: str, payload: dict[str, Any]) -> RuntimeEvent:
        self._sequence += 1
        event = RuntimeEvent(self._sequence, event_type, payload)
        self._history.append(event)
        for queue in tuple(self._subscribers):
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(event)
        return event

    async def subscribe(self, after: int = 0) -> asyncio.Queue[RuntimeEvent]:
        queue: asyncio.Queue[RuntimeEvent] = asyncio.Queue(maxsize=512)
        for event in list(self._history)[-512:]:
            if event.seq > after:
                queue.put_nowait(event)
        self._subscribers.add(queue)
        return queue

    @property
    def sequence(self) -> int:
        return self._sequence

    def unsubscribe(self, queue: asyncio.Queue[RuntimeEvent]) -> None:
        self._subscribers.discard(queue)
