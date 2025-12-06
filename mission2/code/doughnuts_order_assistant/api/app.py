from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from services.orders import OrderService
from state_controller.events import iter_events

from .schemas import CancelResponse, OrderCreated, OrderRequest

app = FastAPI(title="Doughnuts Order Assistant Gateway")

_order_service = OrderService()


def get_order_service() -> OrderService:
    return _order_service


@app.post("/orders", response_model=OrderCreated)
async def create_order(
    body: OrderRequest,
    service: OrderService = Depends(get_order_service),
) -> OrderCreated:
    request_id = await service.create_order(
        flavor=body.flavor,
        table_id=body.table_id,
        user_id=body.user_id,
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
