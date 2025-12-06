from __future__ import annotations

from typing import Dict
from uuid import uuid4

from api.schemas import CompletedEvent, ErrorEvent, Flavor, StatusUpdateEvent

from .events import publish_event
from .states import OrderPhase, OrderState


class OrderStateManager:
    """注文IDごとのステートとイベント通知を管理するシンプルなクラス。"""

    def __init__(self, skip_socket: bool = False) -> None:
        """Initialize OrderStateManager.

        Args:
            skip_socket: Trueの場合、Unixソケット経由でのイベント送信をスキップする
                        （APIサーバー側で使用する場合にTrueを指定）
        """
        self._orders: Dict[str, OrderState] = {}
        self._skip_socket = skip_socket
        # 単純化のためロックは置かず、単一プロセス・単一ワーカー前提とする。

    async def create_order(self, flavor: Flavor) -> OrderState:
        request_id = str(uuid4())
        state = OrderState(
            request_id=request_id,
            flavor=flavor,
            phase=OrderPhase.WAITING,
            message="注文を受け付けました",
            progress=0.0,
        )
        self._orders[request_id] = state

        event = StatusUpdateEvent(
            request_id=request_id,
            stage=state.phase.name,
            progress=state.progress,
            message=state.message,
        )
        await publish_event(event, skip_socket=self._skip_socket)
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
        if state is not None:
            # Update existing state
            state.phase = phase
            state.message = message
            state.progress = progress
        # Even if state doesn't exist (e.g., in worker process),
        # still publish the event so it can be sent via Unix socket
        await publish_event(
            StatusUpdateEvent(
                request_id=request_id,
                stage=phase.name,
                progress=progress,
                message=message,
            ),
            skip_socket=self._skip_socket,
        )

    async def mark_completed(self, request_id: str) -> None:
        state = self._orders.get(request_id)
        if state is not None:
            state.phase = OrderPhase.DONE
            state.progress = 1.0
            state.message = "ドーナッツを箱に詰め終わりました"
            flavor = state.flavor
        else:
            # If state doesn't exist, use a default flavor
            # (This shouldn't happen in normal flow, but handle gracefully)
            flavor = "unknown"

        await publish_event(
            CompletedEvent(
                request_id=request_id,
                result={
                    "delivered": True,
                    "flavor": flavor,
                },
            ),
            skip_socket=self._skip_socket,
        )

    async def mark_canceled(self, request_id: str) -> None:
        state = self._orders.get(request_id)
        if state is not None:
            state.phase = OrderPhase.CANCELED
            state.message = "注文をキャンセルしました"

        # Even if state doesn't exist, still publish the event
        await publish_event(
            ErrorEvent(
                request_id=request_id,
                message="注文がキャンセルされました",
            ),
            skip_socket=self._skip_socket,
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
            ),
            skip_socket=self._skip_socket,
        )
