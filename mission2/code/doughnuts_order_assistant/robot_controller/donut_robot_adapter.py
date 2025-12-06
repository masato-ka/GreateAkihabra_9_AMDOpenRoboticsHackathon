from __future__ import annotations

import asyncio
import logging
import sys
from typing import Final, Optional

import evdev
from evdev import ecodes
from state_controller.machine import OrderStateManager
from state_controller.states import OrderPhase

logger = logging.getLogger(__name__)

_DEBOUNCE_WINDOW_SEC: Final[float] = 0.3
_POST_R_DELAY_SEC: Final[float] = 10.0


def _find_keyboard_device() -> Optional[evdev.InputDevice]:
    """Find the first input device that reports EV_KEY events (likely a keyboard).

    Returns:
        evdev.InputDevice or None if not found.
    """

    for path in evdev.list_devices():
        try:
            dev = evdev.InputDevice(path)
            caps = dev.capabilities().get(ecodes.EV_KEY, [])
            if caps:
                logger.info("Using input device for R detection: %s", path)
                return dev
        except Exception:
            continue
    return None


async def _wait_for_r(prompt: str) -> None:
    """Wait for a physical 'R' key press via evdev (debounced), then sleep 10s."""

    dev = _find_keyboard_device()
    if dev is None:
        logger.error("No keyboard-like input device found; cannot detect R key.")
        return

    print(prompt)

    last_press = 0.0
    loop = asyncio.get_running_loop()

    async for event in dev.async_read_loop():
        if event.type != ecodes.EV_KEY:
            continue
        if event.code != ecodes.KEY_R:
            continue
        if event.value not in (1, 2):  # key down or autorepeat
            continue

        now = loop.time()
        if now - last_press < _DEBOUNCE_WINDOW_SEC:
            continue
        last_press = now
        break

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
    """Adapter that runs `vla_controller_rtc.py` as a subprocess per order.

    NOTE: This still loads the model per order (because `vla_controller_rtc.py`
    is a CLI). It is structured so we can later replace the subprocess call
    with a long-running worker that keeps the model in memory.
    """

    def __init__(self, state_manager: OrderStateManager) -> None:
        super().__init__(state_manager)

        # These values are the ones shared earlier for the demo run.
        self.policy_path = "masato-ka/smolvla-donuts-shop-v1"
        self.robot_type = "bi_so101_follower"
        self.robot_id = "bi_robot"
        self.left_arm_port = "/dev/ttyACM3"
        self.right_arm_port = "/dev/ttyACM2"
        self.cameras = (
            "{ front: {type: opencv, index_or_path: /dev/video4 , width: 640, height: 480, fps: 30}, "
            "back:{type: opencv, index_or_path: /dev/video6, width: 640, height: 480, fps: 30}}"
        )

    async def _run_policy_subprocess(self, task_prompt: str) -> int:
        cmd = [
            sys.executable,
            "-m",
            "robot_controller.vla_controller_rtc",
            f"--policy.path={self.policy_path}",
            "--policy.device=cuda",
            "--rtc.enabled=true",
            "--rtc.execution_horizon=12",
            "--rtc.max_guidance_weight=10.0",
            "--fps=30",
            f"--robot.type={self.robot_type}",
            f"--robot.id={self.robot_id}",
            f"--robot.left_arm_port={self.left_arm_port}",
            f"--robot.right_arm_port={self.right_arm_port}",
            f"--robot.cameras={self.cameras}",
            f"--task={task_prompt}",
            "--duration=120",
            '--policy.input_features={"observation.state": {"type": "STATE", "shape": [12]}}',
            '--policy.output_features={"action": {"type": "ACTION", "shape": [12]}}',
        ]

        proc = await asyncio.create_subprocess_exec(*cmd)
        return await proc.wait()

    async def run_order(self, request_id: str, flavor: str | None = None) -> None:  # type: ignore[override]
        """Run order with real robot subprocess and R-key gating between phases."""

        flavor_str = flavor or "chocolate"
        task_prompt = (
            "Please take the chocolate donuts and into the box."
            if flavor_str == "chocolate"
            else "Please take the strawberry donuts and into the box."
        )

        logger.info(
            "[LerobotDonutRobotAdapter] start order %s flavor=%s",
            request_id,
            flavor_str,
        )

        # Phase 1 label
        await self._state_manager.set_phase(
            request_id,
            OrderPhase.PUTTING_DONUT,
            f"Executing policy for {flavor_str} donuts (pick & place)...",
            progress=0.5,
        )

        # Run the SmolVLA policy as a subprocess (covers both picking and closing)
        rc = await self._run_policy_subprocess(task_prompt)

        if rc != 0:
            msg = f"vla_controller_rtc exited with code {rc}"
            logger.error("[LerobotDonutRobotAdapter] %s", msg)
            await self._state_manager.mark_error(request_id, msg)
            return

        # Phase 2 label (lid closing) — we still gate by R for operator confirmation.
        await self._state_manager.set_phase(
            request_id,
            OrderPhase.CLOSING_LID,
            "Policy finished. Confirm by pressing 'R' to mark completion.",
            progress=0.9,
        )
        await _wait_for_r("Press 'R' to mark the order as completed.")

        await self._state_manager.mark_completed(request_id)
        logger.info("[LerobotDonutRobotAdapter] completed order %s", request_id)
