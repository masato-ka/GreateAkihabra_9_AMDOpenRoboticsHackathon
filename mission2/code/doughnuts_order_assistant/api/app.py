from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from robot_controller.vla_controller_rtc import RTCDemoConfig
from robot_controller.worker import PersistentRobotWorker
from services.orders import OrderService
from state_controller.events import iter_events
from state_controller.machine import OrderStateManager

from .schemas import CancelResponse, OrderCreated, OrderRequest

logger = logging.getLogger(__name__)

_worker: PersistentRobotWorker | None = None
_worker_task: asyncio.Task | None = None


def _create_worker_config() -> RTCDemoConfig:
    """ワーカー用の設定を作成する。"""
    import sys

    from lerobot.configs import parser as lerobot_parser
    from lerobot.configs.policies import PreTrainedConfig
    from lerobot.configs.types import RTCAttentionSchedule
    from lerobot.policies.rtc.configuration_rtc import RTCConfig
    from lerobot.utils.import_utils import register_third_party_devices

    register_third_party_devices()

    # Policy config
    policy = PreTrainedConfig.from_pretrained("masato-ka/smolvla-donuts-shop-v1")
    policy.pretrained_path = "masato-ka/smolvla-donuts-shop-v1"
    policy.device = "cuda"
    policy.input_features = {"observation.state": {"type": "STATE", "shape": [12]}}
    policy.output_features = {"action": {"type": "ACTION", "shape": [12]}}

    # RTC config
    rtc = RTCConfig(
        execution_horizon=12,
        max_guidance_weight=10.0,
        prefix_attention_schedule=RTCAttentionSchedule.EXP,
    )

    # RTCDemoConfigを構築するために、CLI引数のような形式でdraccusを使う
    # __post_init__がCLI引数を期待しているので、一時的にsys.argvを設定する
    import draccus

    original_argv = sys.argv.copy()
    try:
        cli_args = [
            "--policy.path=masato-ka/smolvla-donuts-shop-v1",
            "--robot.type=bi_so101_follower",
            "--robot.id=bi_robot",
            "--robot.left_arm_port=/dev/ttyACM3",
            "--robot.right_arm_port=/dev/ttyACM2",
            "--robot.cameras.front.type=opencv",
            "--robot.cameras.front.index_or_path=/dev/video4",
            "--robot.cameras.front.width=640",
            "--robot.cameras.front.height=480",
            "--robot.cameras.front.fps=30",
            "--robot.cameras.back.type=opencv",
            "--robot.cameras.back.index_or_path=/dev/video6",
            "--robot.cameras.back.width=640",
            "--robot.cameras.back.height=480",
            "--robot.cameras.back.fps=30",
        ]
        # Use draccus to parse the config
        cfg = draccus.parse(config_class=RTCDemoConfig, args=cli_args)
        # 設定を上書き（policyは既に設定されているので、__post_init__でスキップされる）
        cfg.policy = policy
        cfg.rtc = rtc
        cfg.duration = 120.0
        cfg.fps = 30.0
        cfg.device = "cuda"
        cfg.use_torch_compile = False
        return cfg
    finally:
        sys.argv = original_argv


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPIのlifespanイベント: ワーカーを起動・停止する。"""
    global _worker, _worker_task, _state_manager, _order_service

    # Startup: ワーカーを起動
    logger.info("[APP] Starting robot worker...")
    _state_manager = OrderStateManager()
    cfg = _create_worker_config()
    _worker = PersistentRobotWorker(cfg, _state_manager)

    # OrderServiceを初期化（state_managerを共有）
    _order_service = OrderService(state_manager=_state_manager)

    # ワーカーを別タスクで実行
    _worker_task = asyncio.create_task(_worker.run())

    # ワーカーが初期化されるまで少し待つ
    await asyncio.sleep(2.0)

    logger.info("[APP] Robot worker started")

    yield

    # Shutdown: ワーカーを停止
    logger.info("[APP] Stopping robot worker...")
    if _worker_task:
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
    logger.info("[APP] Robot worker stopped")


app = FastAPI(title="Doughnuts Order Assistant Gateway", lifespan=lifespan)

_order_service: OrderService | None = None
_state_manager: OrderStateManager | None = None


def get_order_service() -> OrderService:
    global _order_service
    if _order_service is None:
        raise RuntimeError("OrderService not initialized. Worker may not have started.")
    return _order_service


@app.post("/orders", response_model=OrderCreated)
async def create_order(
    body: OrderRequest,
    service: OrderService = Depends(get_order_service),
) -> OrderCreated:
    request_id = await service.create_order(
        flavor=body.flavor,
    )
    return OrderCreated(request_id=request_id)


@app.post("/orders/{request_id}/cancel", response_model=CancelResponse)
async def cancel_order(
    request_id: str,
    service: OrderService = Depends(get_order_service),
) -> CancelResponse:
    canceled = await service.cancel_order(request_id)
    if not canceled:
        raise HTTPException(status_code=404, detail="order not found")
    return CancelResponse(canceled=True)


@app.get("/events")
async def sse_events(request: Request) -> StreamingResponse:
    """SSE によるイベントストリーム。

    Chat Backend はここに1本接続しておき、request_id ごとのイベントを購読する。
    """

    async def event_generator():
        async for line in iter_events():
            if await request.is_disconnected():
                break
            yield line

    return StreamingResponse(event_generator(), media_type="text/event-stream")


__all__ = ["app"]
