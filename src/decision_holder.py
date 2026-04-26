"""Per-node-id pause primitive for the approve/reject gate.

A `DecisionHolder` lets the gate node's `func()` open a slot for a node, await a
decision posted by the frontend (or a cancel/timeout), and clean up. Designed
to live as a module-level singleton — one instance per ComfyUI process — but
the class is fully usable for testing without globals.

The interrupt-check hook is dependency-injected so unit tests do not need
ComfyUI installed; production code passes `comfy.model_management.processing_interrupted`.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable


class DecisionHolder:
    def __init__(self) -> None:
        self._events: dict[str, asyncio.Event] = {}
        self._decisions: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def open(self, node_id: str) -> None:
        async with self._lock:
            self._events[node_id] = asyncio.Event()
            self._decisions.pop(node_id, None)

    async def submit(self, node_id: str, decision: dict[str, Any]) -> bool:
        async with self._lock:
            event = self._events.get(node_id)
            if event is None:
                return False
            self._decisions[node_id] = decision
            event.set()
            return True

    async def cancel(self, node_id: str) -> bool:
        return await self.submit(node_id, {"action": "cancel"})

    async def wait(
        self,
        node_id: str,
        timeout_s: float | None = None,
        interrupt_check_fn: Callable[[], bool] | None = None,
        poll_interval_s: float = 0.25,
    ) -> dict[str, Any]:
        async with self._lock:
            event = self._events.get(node_id)
        if event is None:
            raise KeyError(f"No open decision slot for node_id {node_id!r}")

        decision_task = asyncio.create_task(event.wait())
        interrupt_task: asyncio.Task[None] | None = None
        if interrupt_check_fn is not None:
            interrupt_task = asyncio.create_task(
                self._poll_interrupt(interrupt_check_fn, poll_interval_s)
            )

        waiters: list[asyncio.Task[Any]] = [decision_task]
        if interrupt_task is not None:
            waiters.append(interrupt_task)

        try:
            done, pending = await asyncio.wait(
                waiters,
                timeout=timeout_s,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            # Drain cancellations so we don't leak warnings
            for task in pending:
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

            if not done:
                return {"action": "timeout"}
            if decision_task in done:
                async with self._lock:
                    return self._decisions.get(node_id, {"action": "cancel"})
            # Interrupt task fired
            return {"action": "cancel"}
        finally:
            async with self._lock:
                self._events.pop(node_id, None)
                self._decisions.pop(node_id, None)

    @staticmethod
    async def _poll_interrupt(
        check: Callable[[], bool], interval_s: float
    ) -> None:
        while True:
            if check():
                return
            await asyncio.sleep(interval_s)


holder = DecisionHolder()
