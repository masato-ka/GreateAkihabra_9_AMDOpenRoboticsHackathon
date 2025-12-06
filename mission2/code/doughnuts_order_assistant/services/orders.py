from __future__ import annotations

import asyncio

from api.schemas import Flavor
from robot_controller.donut_robot_adapter import LerobotDonutRobotAdapter
from state_controller.machine import OrderStateManager


class OrderService:
    """Bridges API requests to robot execution and state updates."""

    def __init__(
        self,
        state_manager: OrderStateManager | None = None,
        robot_adapter: LerobotDonutRobotAdapter | None = None,
    ) -> None:
        self._state_manager = state_manager or OrderStateManager()
        self._robot_adapter = robot_adapter or LerobotDonutRobotAdapter(
            self._state_manager
        )

    @property
    def state_manager(self) -> OrderStateManager:
        return self._state_manager

    async def create_order(self, flavor: Flavor) -> str:
        """Create an order and start robot execution in background."""

        state = await self._state_manager.create_order(flavor=flavor)

        # Run robot task in background
        asyncio.create_task(self._robot_adapter.run_order(state.request_id, flavor))
        return state.request_id

    async def cancel_order(self, request_id: str) -> bool:
        """Cancel an order and notify the robot adapter."""

        state = self._state_manager.get_order(request_id)
        if state is None:
            return False

        await self._robot_adapter.cancel_order(request_id)
        return True
