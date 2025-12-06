from __future__ import annotations

import asyncio

from api.schemas import Flavor
from robot_controller.donut_robot_adapter import SimulationDonutRobotAdapter
from state_controller.machine import OrderStateManager


class OrderService:
    """注文作成・キャンセルとロボット動作の橋渡しを行うサービス。"""

    def __init__(
        self,
        state_manager: OrderStateManager | None = None,
        robot_adapter: SimulationDonutRobotAdapter | None = None,
    ) -> None:
        self._state_manager = state_manager or OrderStateManager()
        self._robot_adapter = robot_adapter or SimulationDonutRobotAdapter(
            self._state_manager
        )

    @property
    def state_manager(self) -> OrderStateManager:
        return self._state_manager

    async def create_order(self, flavor: Flavor) -> str:
        """注文を作成し、ロボット動作をバックグラウンドで開始する。"""

        state = await self._state_manager.create_order(flavor=flavor)

        # ロボット動作はバックグラウンドタスクとして実行
        asyncio.create_task(self._robot_adapter.run_order(state.request_id))
        return state.request_id

    async def cancel_order(self, request_id: str) -> bool:
        """注文をキャンセルし、ロボットにも停止を伝える。"""

        state = self._state_manager.get_order(request_id)
        if state is None:
            return False

        await self._robot_adapter.cancel_order(request_id)
        return True
