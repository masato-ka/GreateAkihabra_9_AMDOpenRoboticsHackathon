from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import sys
import time
from dataclasses import dataclass
from enum import Enum
from threading import Event, Thread
from typing import Optional

import evdev
from evdev import ecodes
from robot_controller.vla_controller_rtc import (
    RobotWrapper,
    RTCDemoConfig,
    _apply_torch_compile,
    actor_control,
    get_actions,
    run_episode,
)
from state_controller.machine import OrderStateManager
from state_controller.states import OrderPhase

logger = logging.getLogger(__name__)

# R-key detection constants
_DEBOUNCE_WINDOW_SEC: float = 0.3
_POST_R_DELAY_SEC: float = 5.0

# Worker socket path
_WORKER_SOCKET_PATH = "/tmp/doughnut_worker.sock"


class WorkerCommandType(str, Enum):
    START_ORDER = "start_order"
    CANCEL_ORDER = "cancel_order"
    SHUTDOWN = "shutdown"


@dataclass
class WorkerCommand:
    type: WorkerCommandType
    request_id: str | None = None
    flavor: str | None = None


class PersistentRobotWorker:
    """常駐ワーカー: モデルを1回ロードし、複数の注文を処理する。"""

    def __init__(
        self,
        cfg: RTCDemoConfig,
        state_manager: OrderStateManager,
    ) -> None:
        self._cfg = cfg
        self._state_manager = state_manager
        self._policy = None
        self._robot_wrapper: RobotWrapper | None = None
        self._robot_observation_processor = None
        self._robot_action_processor = None
        self._shutdown_event = Event()
        self._current_request_id: str | None = None
        self._current_flavor: str | None = None
        self._current_get_actions_thread: Thread | None = None
        self._current_actor_thread: Thread | None = None
        self._current_action_queue = None
        self._r_key_device: evdev.InputDevice | None = None

    def _find_keyboard_device(self) -> Optional[evdev.InputDevice]:
        """Find the input device for R key detection.

        Priority:
        1. Environment variable R_KEY_EVENT (set by worker_cli.py)
        2. First device with EV_KEY capability
        """
        # Check environment variable first
        env_device = os.environ.get("R_KEY_EVENT")
        if env_device:
            try:
                dev = evdev.InputDevice(env_device)
                caps = dev.capabilities().get(ecodes.EV_KEY, [])
                if caps:
                    logger.info(
                        "[WORKER] Using input device for R detection from R_KEY_EVENT: %s (%s)",
                        env_device,
                        dev.name,
                    )
                    return dev
                else:
                    logger.warning(
                        "[WORKER] Device from R_KEY_EVENT has no EV_KEY capability: %s",
                        env_device,
                    )
            except Exception as e:
                logger.warning(
                    "[WORKER] Failed to open device from R_KEY_EVENT=%s: %s",
                    env_device,
                    e,
                )

        # Fallback: find first device with EV_KEY
        for path in evdev.list_devices():
            try:
                dev = evdev.InputDevice(path)
                caps = dev.capabilities().get(ecodes.EV_KEY, [])
                if caps:
                    logger.info(
                        "[WORKER] Using input device for R detection: %s (%s)",
                        path,
                        dev.name,
                    )
                    return dev
            except Exception as e:
                logger.debug("[WORKER] Failed to open device %s: %s", path, e)
                continue
        return None

    def _initialize_model_and_robot(self) -> None:
        """モデルとロボットを1回だけ初期化する。"""
        from lerobot.configs.policies import PreTrainedConfig
        from lerobot.policies.factory import get_policy_class
        from lerobot.processor.factory import (
            make_default_robot_action_processor,
            make_default_robot_observation_processor,
        )
        from lerobot.robots.utils import make_robot_from_config
        from lerobot.utils.import_utils import register_third_party_devices

        register_third_party_devices()

        logger.info("[WORKER] Initializing model and robot...")

        policy_class = get_policy_class(self._cfg.policy.type)

        # Load config
        config = PreTrainedConfig.from_pretrained(self._cfg.policy.pretrained_path)

        if self._cfg.policy.type == "smolvla":
            config.input_features = self._cfg.policy.input_features
            config.output_features = self._cfg.policy.output_features

        if self._cfg.policy.type == "pi05" or self._cfg.policy.type == "pi0":
            config.compile_model = self._cfg.use_torch_compile

        self._policy = policy_class.from_pretrained(
            self._cfg.policy.pretrained_path, config=config
        )

        # Turn on RTC
        self._policy.config.rtc_config = self._cfg.rtc
        self._policy.init_rtc_processor()

        assert self._policy.name in [
            "smolvla",
            "pi05",
            "pi0",
        ], "Only smolvla, pi05, and pi0 are supported for RTC"

        self._policy = self._policy.to(self._cfg.device)
        self._policy.eval()

        # Apply torch.compile if enabled
        if self._cfg.use_torch_compile:
            self._policy = _apply_torch_compile(self._policy, self._cfg)

        # Create robot
        logger.info(f"[WORKER] Initializing robot: {self._cfg.robot.type}")
        robot = make_robot_from_config(self._cfg.robot)
        robot.connect()
        self._robot_wrapper = RobotWrapper(robot)

        # Create processors
        self._robot_observation_processor = make_default_robot_observation_processor()
        self._robot_action_processor = make_default_robot_action_processor()

        logger.info("[WORKER] Model and robot initialized successfully")

    def _wait_for_r_key(self) -> bool:
        """物理キーボードの 'r' キーを検知する（デバウンス付き）。

        Returns:
            True if R key was detected, False if shutdown was requested
        """
        if self._r_key_device is None:
            self._r_key_device = self._find_keyboard_device()
            if self._r_key_device is None:
                logger.error(
                    "[WORKER] No keyboard-like input device found; cannot detect R key."
                )
                return False

        last_press = 0.0
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:

            async def read_loop():
                async for event in self._r_key_device.async_read_loop():
                    if self._shutdown_event.is_set():
                        return False
                    if event.type != ecodes.EV_KEY:
                        continue
                    if event.code != ecodes.KEY_R:
                        continue
                    if event.value not in (1, 2):  # key down or autorepeat
                        continue

                    now = loop.time()
                    if now - last_press < _DEBOUNCE_WINDOW_SEC:
                        continue
                    return True
                return False

            result = loop.run_until_complete(read_loop())
            return result
        except Exception as e:
            logger.error(f"[WORKER] Error waiting for R key: {e}")
            return False
        finally:
            loop.close()

    async def _wait_for_r_key_async(self) -> bool:
        """物理キーボードの 'r' キーを検知する（非同期版、デバウンス付き）。

        Returns:
            True if R key was detected, False if shutdown was requested
        """
        if self._r_key_device is None:
            self._r_key_device = self._find_keyboard_device()
            if self._r_key_device is None:
                logger.error(
                    "[WORKER] No keyboard-like input device found; cannot detect R key."
                )
                return False

        # Clear any pending events in the queue before starting to wait
        # This prevents detecting old R key presses from previous phases
        # Reopen the device to clear the event queue
        device_path = self._r_key_device.path
        try:
            self._r_key_device.close()
        except Exception:
            pass
        try:
            self._r_key_device = evdev.InputDevice(device_path)
        except Exception as e:
            logger.warning(f"[WORKER] Failed to reopen device for event clearing: {e}")

        last_press = [0.0]  # Use list to allow modification in nested function
        loop = asyncio.get_event_loop()

        try:
            async for event in self._r_key_device.async_read_loop():
                if self._shutdown_event.is_set():
                    return False
                if event.type != ecodes.EV_KEY:
                    continue
                if event.code != ecodes.KEY_R:
                    continue
                if event.value not in (1, 2):  # key down or autorepeat
                    continue

                now = loop.time()
                if now - last_press[0] < _DEBOUNCE_WINDOW_SEC:
                    continue
                last_press[0] = now
                logger.info("[WORKER] R key detected")
                return True
        except Exception as e:
            logger.error(f"[WORKER] Error in R key detection loop: {e}")
            return False

        return False

    async def _execute_order(self, request_id: str, flavor: str) -> None:
        """注文を実行する（2フェーズ: ピック&箱入れ → 箱閉め）。"""
        self._current_request_id = request_id
        self._current_flavor = flavor

        try:
            # Phase 1: Put doughnuts into the box
            # Note: Different prompt formats for chocolate and strawberry
            task_phase1 = (
                "Please take the chocolate donuts and into the box."
                if flavor == "chocolate"
                else "Pick up the strawberry donut and place it in the box."
            )

            # Notify that Phase 1 (box packing) has started
            await self._state_manager.set_phase(
                request_id,
                OrderPhase.PUTTING_DONUT,
                f"ドーナツの箱詰めを開始しました ({flavor})",
                progress=0.5,
            )

            logger.info(
                f"[WORKER] Starting Phase 1 for order {request_id} with task: {task_phase1}"
            )

            # Run episode 1 and R-key detection in parallel
            loop = asyncio.get_event_loop()
            episode_shutdown = Event()

            async def run_episode_async():
                """Run episode in executor and return result."""
                logger.info(
                    f"[WORKER] run_episode_async: About to call run_episode with task: '{task_phase1}'"
                )
                logger.info(
                    f"[WORKER] run_episode_async: cfg.task = '{self._cfg.task}'"
                )
                return await loop.run_in_executor(
                    None,
                    run_episode,
                    self._policy,
                    self._robot_wrapper,
                    self._robot_observation_processor,
                    self._robot_action_processor,
                    episode_shutdown,
                    self._cfg,
                    task_phase1,
                    self._cfg.duration,
                    self._current_get_actions_thread,
                    self._current_actor_thread,
                )

            async def wait_for_r_and_shutdown():
                """Wait for R key and set shutdown event."""
                logger.info(
                    "[WORKER] Waiting for R key to stop Phase 1 and proceed to Phase 2..."
                )
                r_detected = await self._wait_for_r_key_async()
                if r_detected:
                    logger.info(
                        "[WORKER] R key detected during Phase 1, stopping episode..."
                    )
                    episode_shutdown.set()
                    return True
                return False

            # Run episode and R-key detection in parallel
            episode_task = asyncio.create_task(run_episode_async())
            r_key_task = asyncio.create_task(wait_for_r_and_shutdown())

            # Wait for either episode to complete or R key to be pressed
            done, pending = await asyncio.wait(
                [episode_task, r_key_task], return_when=asyncio.FIRST_COMPLETED
            )

            # Check if R key was detected
            r_detected = False
            if r_key_task in done:
                r_detected = await r_key_task
                # R key was pressed, wait for episode to finish gracefully
                # (episode_shutdown.set() was already called, so it should finish soon)
                logger.info(
                    "[WORKER] Waiting for episode to finish after R key detection..."
                )
            else:
                # Episode completed naturally, cancel R key task
                r_key_task.cancel()
                try:
                    await r_key_task
                except asyncio.CancelledError:
                    pass

            # Get episode result (wait for it to finish)
            (
                self._current_get_actions_thread,
                self._current_actor_thread,
                self._current_action_queue,
            ) = await episode_task

            if not r_detected:
                # R key was not pressed during episode, wait for it now
                logger.info(
                    "[WORKER] Phase 1 completed. Waiting for R key to start Phase 2..."
                )
                r_detected = await self._wait_for_r_key_async()

            if not r_detected or self._shutdown_event.is_set():
                logger.warning("[WORKER] R key not detected or shutdown requested")
                await self._state_manager.mark_error(
                    request_id, "Phase 1 completed but R key not detected"
                )
                return

            # Phase 1 completed - notify before delay
            await self._state_manager.set_phase(
                request_id,
                OrderPhase.PUTTING_DONUT,
                "Phase 1完了: ドーナツを箱に入れました。Phase 2の準備中...",
                progress=0.7,
            )

            await asyncio.sleep(_POST_R_DELAY_SEC)

            # Phase 2: Close the box
            task_phase2 = "Please close the box."

            await self._state_manager.set_phase(
                request_id,
                OrderPhase.CLOSING_LID,
                "Executing policy to close the box...",
                progress=0.9,
            )

            logger.info(
                f"[WORKER] Starting Phase 2 for order {request_id} with task: {task_phase2}"
            )

            # Run episode 2 and R-key detection in parallel
            loop = asyncio.get_event_loop()
            episode_shutdown = Event()

            async def run_episode_async():
                """Run episode in executor and return result."""
                return await loop.run_in_executor(
                    None,
                    run_episode,
                    self._policy,
                    self._robot_wrapper,
                    self._robot_observation_processor,
                    self._robot_action_processor,
                    episode_shutdown,
                    self._cfg,
                    task_phase2,
                    self._cfg.duration,
                    self._current_get_actions_thread,
                    self._current_actor_thread,
                )

            async def wait_for_r_and_shutdown():
                """Wait for R key and set shutdown event."""
                logger.info(
                    "[WORKER] Waiting for R key to stop Phase 2 and mark as completed..."
                )
                r_detected = await self._wait_for_r_key_async()
                if r_detected:
                    logger.info(
                        "[WORKER] R key detected during Phase 2, stopping episode..."
                    )
                    episode_shutdown.set()
                    return True
                return False

            # Run episode and R-key detection in parallel
            episode_task = asyncio.create_task(run_episode_async())
            r_key_task = asyncio.create_task(wait_for_r_and_shutdown())

            # Wait for either episode to complete or R key to be pressed
            done, pending = await asyncio.wait(
                [episode_task, r_key_task], return_when=asyncio.FIRST_COMPLETED
            )

            # Check if R key was detected
            r_detected = False
            if r_key_task in done:
                r_detected = await r_key_task
                # R key was pressed, wait for episode to finish gracefully
                # (episode_shutdown.set() was already called, so it should finish soon)
                logger.info(
                    "[WORKER] Waiting for episode to finish after R key detection..."
                )
            else:
                # Episode completed naturally, cancel R key task
                r_key_task.cancel()
                try:
                    await r_key_task
                except asyncio.CancelledError:
                    pass

            # Get episode result (wait for it to finish)
            (
                self._current_get_actions_thread,
                self._current_actor_thread,
                self._current_action_queue,
            ) = await episode_task

            if not r_detected:
                # R key was not pressed during episode, wait for it now
                logger.info(
                    "[WORKER] Phase 2 completed. Waiting for R key to mark as completed..."
                )
                r_detected = await self._wait_for_r_key_async()

            if not r_detected or self._shutdown_event.is_set():
                logger.warning("[WORKER] R key not detected or shutdown requested")
                await self._state_manager.mark_error(
                    request_id, "Phase 2 completed but R key not detected"
                )
                return

            await asyncio.sleep(_POST_R_DELAY_SEC)

            # Mark as completed
            await self._state_manager.mark_completed(request_id)
            logger.info(f"[WORKER] Order {request_id} completed successfully")

        except Exception as e:
            logger.error(
                f"[WORKER] Error executing order {request_id}: {e}", exc_info=True
            )
            await self._state_manager.mark_error(request_id, str(e))
        finally:
            self._current_request_id = None
            self._current_flavor = None

    async def _handle_command(self, cmd: WorkerCommand) -> dict:
        """コマンドを処理する。"""
        if cmd.type == WorkerCommandType.START_ORDER:
            if cmd.request_id is None or cmd.flavor is None:
                return {"status": "error", "message": "Missing request_id or flavor"}
            asyncio.create_task(self._execute_order(cmd.request_id, cmd.flavor))
            return {"status": "ok", "message": "Order started"}

        elif cmd.type == WorkerCommandType.CANCEL_ORDER:
            if cmd.request_id is None:
                return {"status": "error", "message": "Missing request_id"}
            # Stop current execution if it matches
            if self._current_request_id == cmd.request_id:
                self._shutdown_event.set()
                await self._state_manager.mark_canceled(cmd.request_id)
            return {"status": "ok", "message": "Order canceled"}

        elif cmd.type == WorkerCommandType.SHUTDOWN:
            self._shutdown_event.set()
            return {"status": "ok", "message": "Shutdown requested"}

        return {"status": "error", "message": "Unknown command type"}

    async def _socket_server_loop(self) -> None:
        """Unixソケットでコマンドを受信するループ。"""
        # Remove socket file if it exists
        if os.path.exists(_WORKER_SOCKET_PATH):
            logger.info(
                f"[WORKER] Removing existing socket file: {_WORKER_SOCKET_PATH}"
            )
            os.unlink(_WORKER_SOCKET_PATH)

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            server.bind(_WORKER_SOCKET_PATH)
            logger.info(f"[WORKER] Successfully bound socket to {_WORKER_SOCKET_PATH}")
        except Exception as e:
            logger.error(
                f"[WORKER] Failed to bind socket to {_WORKER_SOCKET_PATH}: {e}"
            )
            raise

        # Verify socket file was created
        if os.path.exists(_WORKER_SOCKET_PATH):
            logger.info(f"[WORKER] Socket file exists: {_WORKER_SOCKET_PATH}")
        else:
            logger.error(
                f"[WORKER] Socket file was NOT created at {_WORKER_SOCKET_PATH}"
            )

        server.listen(1)
        server.setblocking(False)

        logger.info(f"[WORKER] Listening on {_WORKER_SOCKET_PATH}")

        loop = asyncio.get_event_loop()

        while not self._shutdown_event.is_set():
            try:
                # Accept connection (non-blocking)
                client, _ = await loop.sock_accept(server)
                data = await loop.sock_recv(client, 4096)

                if not data:
                    client.close()
                    continue

                # Parse command
                try:
                    cmd_dict = json.loads(data.decode())
                    cmd = WorkerCommand(
                        type=WorkerCommandType(cmd_dict["type"]),
                        request_id=cmd_dict.get("request_id"),
                        flavor=cmd_dict.get("flavor"),
                    )
                    result = await self._handle_command(cmd)
                    response = json.dumps(result).encode()
                    await loop.sock_sendall(client, response)
                except Exception as e:
                    logger.error(f"[WORKER] Error handling command: {e}")
                    error_response = json.dumps(
                        {"status": "error", "message": str(e)}
                    ).encode()
                    await loop.sock_sendall(client, error_response)

                client.close()

            except asyncio.CancelledError:
                break
            except Exception as e:
                if not self._shutdown_event.is_set():
                    logger.error(f"[WORKER] Socket server error: {e}")
                await asyncio.sleep(0.1)

        server.close()
        if os.path.exists(_WORKER_SOCKET_PATH):
            os.unlink(_WORKER_SOCKET_PATH)
        logger.info("[WORKER] Socket server stopped")

    async def run(self) -> None:
        """ワーカーを起動する。"""
        try:
            # Initialize model and robot
            try:
                self._initialize_model_and_robot()
            except Exception as e:
                logger.exception("[WORKER] Failed to initialize model/robot: %s", e)
                return

            # Initialize R key device and log which device is being used
            logger.info("[WORKER] Initializing R key detection device...")
            self._r_key_device = self._find_keyboard_device()
            if self._r_key_device is None:
                logger.error(
                    "[WORKER] No keyboard-like input device found; R key detection will not work."
                )
            else:
                logger.info(
                    "[WORKER] R key detection ready. Device: %s (%s)",
                    self._r_key_device.path,
                    self._r_key_device.name,
                )

            # Start socket server
            logger.info("[WORKER] Starting socket server loop...")
            await self._socket_server_loop()

        finally:
            # Cleanup
            self._shutdown_event.set()

            # Stop current threads
            if (
                self._current_get_actions_thread
                and self._current_get_actions_thread.is_alive()
            ):
                self._current_get_actions_thread.join(timeout=2.0)
            if self._current_actor_thread and self._current_actor_thread.is_alive():
                self._current_actor_thread.join(timeout=2.0)

            # Disconnect robot
            if self._robot_wrapper and self._robot_wrapper.robot:
                try:
                    self._robot_wrapper.robot.disconnect()
                    logger.info("[WORKER] Robot disconnected")
                except Exception as e:
                    logger.error("[WORKER] Error during robot disconnect: %s", e)

            logger.info("[WORKER] Worker stopped")


def send_command_to_worker(cmd: WorkerCommand) -> dict:
    """ワーカーにコマンドを送信する（同期版）。"""
    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(_WORKER_SOCKET_PATH)

        cmd_dict = {
            "type": cmd.type.value,
            "request_id": cmd.request_id,
            "flavor": cmd.flavor,
        }
        client.sendall(json.dumps(cmd_dict).encode())

        response_data = client.recv(4096)
        client.close()

        return json.loads(response_data.decode())
    except Exception as e:
        logger.error(f"Error sending command to worker: {e}")
        return {"status": "error", "message": str(e)}


async def send_command_to_worker_async(cmd: WorkerCommand) -> dict:
    """ワーカーにコマンドを送信する（非同期版）。"""
    try:
        loop = asyncio.get_event_loop()
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        await loop.sock_connect(client, _WORKER_SOCKET_PATH)

        cmd_dict = {
            "type": cmd.type.value,
            "request_id": cmd.request_id,
            "flavor": cmd.flavor,
        }
        await loop.sock_sendall(client, json.dumps(cmd_dict).encode())

        response_data = await loop.sock_recv(client, 4096)
        client.close()

        return json.loads(response_data.decode())
    except Exception as e:
        logger.error(f"Error sending command to worker: {e}")
        return {"status": "error", "message": str(e)}
