from __future__ import annotations

import asyncio
import logging
import sys
from typing import Final

from state_controller.machine import OrderStateManager
from state_controller.states import OrderPhase

logger = logging.getLogger(__name__)

_DEBOUNCE_WINDOW_SEC: Final[float] = 0.3
_POST_R_DELAY_SEC: Final[float] = 10.0


async def _wait_for_r(prompt: str) -> None:
    """Wait until the user presses 'R' (debounced), then apply a short delay.

    - Multiple rapid 'R' presses are treated as a single input.
    - After accepting 'R', we wait `_POST_R_DELAY_SEC` seconds before returning.
    """

    def _block() -> None:
        import select
        import time

        print(prompt)

        # Drain any pending input before we start waiting.
        while True:
            rlist, _, _ = select.select([sys.stdin], [], [], 0)
            if not rlist:
                break
            sys.stdin.read(1)

        # Wait for first 'r' / 'R'.
        while True:
            ch = sys.stdin.read(1)
            if not ch:
                continue
            if ch.lower() == "r":
                # Debounce: swallow additional key presses for a short window.
                end = time.time() + _DEBOUNCE_WINDOW_SEC
                while time.time() < end:
                    rlist, _, _ = select.select([sys.stdin], [], [], 0.05)
                    if rlist:
                        sys.stdin.read(1)
                break

    # Block in a thread so that the event loop stays responsive.
    await asyncio.to_thread(_block)
    # Global delay after the operator confirms with R.
    await asyncio.sleep(_POST_R_DELAY_SEC)


class SimulationDonutRobotAdapter:
    """Simulation adapter for development without a real robot.

    Two logical phases:
      1. Put doughnuts into the box
      2. Close the lid

    Each phase advances only after the operator presses the `R` key.
    """

    def __init__(self, state_manager: OrderStateManager) -> None:
        self._state_manager = state_manager

    async def run_order(self, request_id: str) -> None:
        """Run a full order flow with two phases and R-key gating."""

        logger.info("[SimulationDonutRobotAdapter] start order %s", request_id)

        # Phase 1: put doughnuts into the box
        await self._state_manager.set_phase(
            request_id,
            OrderPhase.PUTTING_DONUT,
            "Putting doughnuts into the box...",
            progress=0.5,
        )
        await _wait_for_r("Phase 1 done. Press 'R' to start closing the lid.")

        # Phase 2: close the lid
        await self._state_manager.set_phase(
            request_id,
            OrderPhase.CLOSING_LID,
            "Closing the box lid...",
            progress=0.9,
        )
        await _wait_for_r("Phase 2 done. Press 'R' to mark the order as completed.")

        # Completed
        await self._state_manager.mark_completed(request_id)
        logger.info("[SimulationDonutRobotAdapter] completed order %s", request_id)

    async def cancel_order(self, request_id: str) -> None:
        logger.info("[SimulationDonutRobotAdapter] cancel order %s", request_id)
        await self._state_manager.mark_canceled(request_id)


class LerobotDonutRobotAdapter(SimulationDonutRobotAdapter):
    """Extension point to hook into `vla_controller_rtc.py` and the real robot.

    For now this behaves the same as the simulation adapter.
    Real SmolVLA + robot integration can be implemented later.
    """

    # TODO: Implement real robot control using `vla_controller_rtc.py`.
    pass
