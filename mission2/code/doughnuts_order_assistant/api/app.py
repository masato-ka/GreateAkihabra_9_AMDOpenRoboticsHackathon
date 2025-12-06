from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from robot_controller.vla_controller_rtc import RTCDemoConfig
from robot_controller.worker import PersistentRobotWorker
from services.orders import OrderService
from state_controller.events import (
    iter_events,
    start_event_socket_server,
    stop_event_socket_server,
)
from state_controller.machine import OrderStateManager

from .schemas import CancelResponse, OrderCreated, OrderRequest

logger = logging.getLogger(__name__)

_worker: PersistentRobotWorker | None = None
_worker_task: asyncio.Task | None = None


def _create_worker_config() -> RTCDemoConfig:
    """(非使用) ワーカーは外部プロセスで起動する前提に変更。"""
    raise RuntimeError("Worker must be launched externally (see worker_main.py).")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPIのlifespan: ワーカーは外部プロセスで起動する前提なのでここでは起動しない。"""
    global _order_service, _state_manager

    logger.info(
        "[APP] Skipping internal worker startup; start worker_main.py separately."
    )
    _state_manager = OrderStateManager()
    _order_service = OrderService(state_manager=_state_manager)
    
    # Start Unix socket server to receive events from worker process
    logger.info("[APP] Starting event socket server...")
    await start_event_socket_server()

    yield
    
    # Stop Unix socket server
    logger.info("[APP] Stopping event socket server...")
    await stop_event_socket_server()


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
