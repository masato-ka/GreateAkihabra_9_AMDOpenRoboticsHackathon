from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from robot_controller.vla_controller_rtc import RTCDemoConfig
from robot_controller.worker import PersistentRobotWorker
from services.orders import OrderService
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from state_controller.events import (
    iter_events,
    start_event_socket_server,
    stop_event_socket_server,
    subscribe_events,
)
from state_controller.machine import OrderStateManager

from .schemas import (
    CancelResponse,
    CompletedEvent,
    ErrorEvent,
    OrderCreated,
    OrderRequest,
    OrderStatus,
    StatusUpdateEvent,
)

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
    # APIサーバー側では skip_socket=True を指定（自分自身に送信しない）
    _state_manager = OrderStateManager(skip_socket=True)
    _order_service = OrderService(state_manager=_state_manager)

    # Start Unix socket server to receive events from worker process
    logger.info("[APP] Starting event socket server...")
    await start_event_socket_server()

    # Register event subscriber to sync worker state to API's OrderStateManager
    async def sync_worker_events(event):
        """worker側のイベントをAPI側のOrderStateManagerに同期する。"""
        from state_controller.states import OrderPhase

        try:
            if isinstance(event, StatusUpdateEvent):
                # StatusUpdateEvent を OrderPhase に変換
                phase_map = {
                    "WAITING": OrderPhase.WAITING,
                    "PUTTING_DONUT": OrderPhase.PUTTING_DONUT,
                    "CLOSING_LID": OrderPhase.CLOSING_LID,
                    "DONE": OrderPhase.DONE,
                    "CANCELED": OrderPhase.CANCELED,
                    "ERROR": OrderPhase.ERROR,
                }
                phase = phase_map.get(event.stage, OrderPhase.WAITING)
                await _state_manager.set_phase(
                    event.request_id,
                    phase,
                    event.message,
                    event.progress,
                )
                logger.info(
                    f"[APP] Synced status update: {event.request_id} -> {event.stage}"
                )
            elif isinstance(event, CompletedEvent):
                await _state_manager.mark_completed(event.request_id)
                logger.info(f"[APP] Synced completion: {event.request_id}")
            elif isinstance(event, ErrorEvent) and event.request_id:
                await _state_manager.mark_error(event.request_id, event.message)
                logger.info(
                    f"[APP] Synced error: {event.request_id} -> {event.message}"
                )
        except Exception as e:
            logger.error(f"[APP] Error syncing worker event: {e}", exc_info=True)

    # コールバック関数（coroutineを返す）
    def sync_callback(event):
        """同期コールバックラッパー。coroutineを返す。"""
        return sync_worker_events(event)

    subscribe_events(sync_callback)
    logger.info("[APP] Registered event subscriber for state synchronization")

    yield

    # Stop Unix socket server
    logger.info("[APP] Stopping event socket server...")
    await stop_event_socket_server()


app = FastAPI(title="Doughnuts Order Assistant Gateway", lifespan=lifespan)


# ngrokの警告ページをスキップするためのミドルウェア
class NgrokSkipBrowserWarningMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        # ngrok-skip-browser-warningヘッダーを追加
        request.headers.__dict__["_list"].append(
            (b"ngrok-skip-browser-warning", b"true")
        )
        response = await call_next(request)
        return response


# ngrokの警告ページをスキップするミドルウェアを追加（CORSより前に）
app.add_middleware(NgrokSkipBrowserWarningMiddleware)

# CORS設定を追加
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 開発環境ではすべてのオリジンを許可
    allow_credentials=True,
    allow_methods=["*"],  # GET, POST, OPTIONS などを許可
    allow_headers=["*"],  # すべてのヘッダーを許可
)

_order_service: OrderService | None = None
_state_manager: OrderStateManager | None = None


def get_order_service() -> OrderService:
    global _order_service
    if _order_service is None:
        raise RuntimeError("OrderService not initialized. Worker may not have started.")
    return _order_service


def get_state_manager() -> OrderStateManager:
    global _state_manager
    if _state_manager is None:
        raise RuntimeError(
            "OrderStateManager not initialized. Worker may not have started."
        )
    return _state_manager


@app.post("/orders", response_model=OrderCreated)
async def create_order(
    body: OrderRequest,
    service: OrderService = Depends(get_order_service),
) -> OrderCreated:
    request_id = await service.create_order(
        flavor=body.flavor,
    )
    return OrderCreated(request_id=request_id)


@app.get("/orders/{request_id}/status", response_model=OrderStatus)
async def get_order_status(
    request_id: str,
    state_manager: OrderStateManager = Depends(get_state_manager),
) -> OrderStatus:
    """注文のステータスを取得する（ポーリング用）。"""
    from state_controller.states import OrderPhase

    state = state_manager.get_order(request_id)
    if state is None:
        raise HTTPException(status_code=404, detail="order not found")

    # DONE または ERROR の場合は done: true
    done = state.phase in (OrderPhase.DONE, OrderPhase.ERROR, OrderPhase.CANCELED)

    return OrderStatus(
        request_id=state.request_id,
        stage=state.phase.name,
        progress=state.progress,
        message=state.message,
        done=done,
    )


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

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # nginx用の設定
        },
    )


__all__ = ["app"]
