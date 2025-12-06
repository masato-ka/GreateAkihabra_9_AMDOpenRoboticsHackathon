from __future__ import annotations

from api.schemas import Flavor
from robot_controller.worker import (
    WorkerCommand,
    WorkerCommandType,
    send_command_to_worker_async,
)
from state_controller.machine import OrderStateManager


class OrderService:
    """Bridges API requests to robot execution and state updates."""

    def __init__(
        self,
        state_manager: OrderStateManager | None = None,
    ) -> None:
        self._state_manager = state_manager or OrderStateManager()

    @property
    def state_manager(self) -> OrderStateManager:
        return self._state_manager

    async def create_order(self, flavor: Flavor | str) -> str:
        """Create an order and start robot execution via worker."""

        flavor_str = flavor.value if hasattr(flavor, "value") else str(flavor)
        state = await self._state_manager.create_order(flavor=flavor)

        # Send command to worker
        cmd = WorkerCommand(
            type=WorkerCommandType.START_ORDER,
            request_id=state.request_id,
            flavor=flavor_str,
        )
        result = await send_command_to_worker_async(cmd)
        if result.get("status") != "ok":
            await self._state_manager.mark_error(
                state.request_id, f"Failed to start order: {result.get('message')}"
            )

        return state.request_id

    async def cancel_order(self, request_id: str) -> bool:
        """Cancel an order via worker."""

        state = self._state_manager.get_order(request_id)
        if state is None:
            return False

        cmd = WorkerCommand(
            type=WorkerCommandType.CANCEL_ORDER,
            request_id=request_id,
        )
        result = await send_command_to_worker_async(cmd)
        return result.get("status") == "ok"
