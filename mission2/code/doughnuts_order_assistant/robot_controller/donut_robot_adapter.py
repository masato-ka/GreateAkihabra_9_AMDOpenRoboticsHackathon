from __future__ import annotations

import asyncio
import logging

from state_controller.machine import OrderStateManager
from state_controller.states import OrderPhase

logger = logging.getLogger(__name__)


class SimulationDonutRobotAdapter:
    """実機がなくても動作確認できるようにするためのシミュレーション用アダプタ。

    - 箱にドーナツを詰める
    - 蓋を閉める
    という2ステップのみを時間経過で進める。
    """

    def __init__(self, state_manager: OrderStateManager) -> None:
        self._state_manager = state_manager

    async def run_order(self, request_id: str) -> None:
        """注文フローをシミュレーションで進める。"""

        logger.info("[SimulationDonutRobotAdapter] start order %s", request_id)

        # ドーナツを箱に詰める
        await self._state_manager.set_phase(
            request_id,
            OrderPhase.PUTTING_DONUT,
            "箱にドーナツを入れています",
            progress=0.5,
        )
        await asyncio.sleep(2.0)

        # 蓋を閉める
        await self._state_manager.set_phase(
            request_id,
            OrderPhase.CLOSING_LID,
            "箱の蓋を閉めています",
            progress=0.9,
        )
        await asyncio.sleep(2.0)

        # 完了
        await self._state_manager.mark_completed(request_id)
        logger.info("[SimulationDonutRobotAdapter] completed order %s", request_id)

    async def cancel_order(self, request_id: str) -> None:
        logger.info("[SimulationDonutRobotAdapter] cancel order %s", request_id)
        await self._state_manager.mark_canceled(request_id)


class LerobotDonutRobotAdapter(SimulationDonutRobotAdapter):
    """将来的に `vla_controller_rtc.py` と直結させるための拡張ポイント。

    現時点では SimulationDonutRobotAdapter と同じ挙動だが、
    実機制御を行う場合はこのクラスを拡張して利用する想定。
    """

    # ここで vla_controller_rtc.py を呼び出すロジックを実装していく。
    # ひとまずはシミュレーションと同じ挙動にしておく。
    pass
