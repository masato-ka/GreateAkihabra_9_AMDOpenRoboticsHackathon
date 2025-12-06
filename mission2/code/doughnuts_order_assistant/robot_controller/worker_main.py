#!/usr/bin/env python
"""ワーカーエントリポイント: CLI引数からRTCDemoConfigを構築してPersistentRobotWorkerを起動する。"""

from __future__ import annotations

import asyncio
import logging

# Import RTCDemoConfig after registering third-party devices
# This ensures bi_so101_follower is registered before RTCDemoConfig is parsed
import robot_controller.vla_controller_rtc as vla_module
from lerobot.configs import parser
from lerobot.utils.import_utils import register_third_party_devices
from robot_controller.worker import PersistentRobotWorker
from state_controller.machine import OrderStateManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@parser.wrap()
def main_cli(cfg: vla_module.RTCDemoConfig) -> None:
    """ワーカーを起動する。"""
    logger.info("[WORKER_MAIN] Starting persistent robot worker...")
    logger.info(f"[WORKER_MAIN] Policy: {cfg.policy.pretrained_path}")
    logger.info(f"[WORKER_MAIN] Robot: {cfg.robot.type}")
    logger.info(f"[WORKER_MAIN] Device: {cfg.device}")

    state_manager = OrderStateManager()
    worker = PersistentRobotWorker(cfg, state_manager)

    try:
        asyncio.run(worker.run())
    except KeyboardInterrupt:
        logger.info("[WORKER_MAIN] Shutting down worker...")
    except Exception as e:
        logger.error(f"[WORKER_MAIN] Fatal error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    # Register third-party devices (e.g., bi_so101_follower) before parsing config
    register_third_party_devices()
    main_cli()
