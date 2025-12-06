from __future__ import annotations

from typing import Dict
from uuid import uuid4

from doughnuts_order_assistant.api.schemas import (
    CompletedEvent,
    ErrorEvent,
    Flavor,
    StatusUpdateEvent,
)
from doughnuts_order_assistant.state_controller.events import publish_event
from doughnuts_order_assistant.state_controller.states import OrderPhase, OrderState


class OrderStateManager:
    """注文IDごとのステートとイベント通知を管理するシンプルなクラス。"""

    def __init__(self) -> None:
        self._orders: Dict[str, OrderState] = {}
        # 単純化のためロックは置かず、単一プロセス・単一ワーカー前提とする。

    async def create_order(self, flavor: Flavor, table_id: str, user_id: str) -> OrderState:
        request_id = str(uuid4())
        state = OrderState(
            request_id=request_id,
            flavor=flavor,
            table_id=table_id,
            user_id=user_id,
            phase=OrderPhase.WAITING,
            message="注文を受け付けました",
            progress=0.0,
        )
        self._orders[request_id] = state

        await publish_event(
            StatusUpdateEvent(
                request_id=request_id,
                stage=state.phase.name,
                progress=state.progress,
                message=state.message,
            )
        )
        return state

    def get_order(self, request_id: str) -> OrderState | None:
        return self._orders.get(request_id)

    async def set_phase(
        self,
        request_id: str,
        phase: OrderPhase,
        message: str,
        progress: float,
    ) -> None:
        state = self._orders.get(request_id)
        if state is None:
            return

        state.phase = phase
        state.message = message
        state.progress = progress

        await publish_event(
            StatusUpdateEvent(
                request_id=request_id,
                stage=phase.name,
                progress=progress,
                message=message,
            )
        )

    async def mark_completed(self, request_id: str) -> None:
        state = self._orders.get(request_id)
        if state is None:
            return

        state.phase = OrderPhase.DONE
        state.progress = 1.0
        state.message = "ドーナッツを箱に詰め終わりました"

        await publish_event(
            CompletedEvent(
                request_id=request_id,
                result={
                    "delivered": True,
                    "flavor": state.flavor,
                },
            )
        )

    async def mark_canceled(self, request_id: str) -> None:
        state = self._orders.get(request_id)
        if state is None:
            return

        state.phase = OrderPhase.CANCELED
        state.message = "注文をキャンセルしました"

        await publish_event(
            ErrorEvent(
                request_id=request_id,
                message="注文がキャンセルされました",
            )
        )

    async def mark_error(self, request_id: str, message: str) -> None:
        state = self._orders.get(request_id)
        if state is not None:
            state.phase = OrderPhase.ERROR
            state.error_message = message

        await publish_event(
            ErrorEvent(
                request_id=request_id,
                message=message,
            )
        )


