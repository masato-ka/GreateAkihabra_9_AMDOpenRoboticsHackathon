#!/usr/bin/env python
"""ワーカーエントリポイント: CLI引数からRTCDemoConfigを構築してPersistentRobotWorkerを起動する。"""

from __future__ import annotations

import asyncio
import logging

from lerobot.configs import parser
from robot_controller.vla_controller_rtc import RTCDemoConfig
from robot_controller.worker import PersistentRobotWorker
from state_controller.machine import OrderStateManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@parser.wrap()
def main(cfg: RTCDemoConfig) -> None:
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
    main()

