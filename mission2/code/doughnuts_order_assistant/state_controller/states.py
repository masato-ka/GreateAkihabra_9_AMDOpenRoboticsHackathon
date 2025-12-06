from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from api.schemas import Flavor


class OrderPhase(Enum):
    """ドーナッツ注文のライフサイクルを表す簡易ステート。"""

    WAITING = auto()
    PUTTING_DONUT = auto()
    CLOSING_LID = auto()
    DONE = auto()
    CANCELED = auto()
    ERROR = auto()


@dataclass
class OrderState:
    """1つの注文（request_id）に対応する状態。"""

    request_id: str
    flavor: Flavor
    table_id: str
    user_id: str
    phase: OrderPhase = OrderPhase.WAITING
    message: str = ""
    progress: float = 0.0
    error_message: Optional[str] = None
    # 追加メタ情報が必要になったらここに足す
    metadata: dict = field(default_factory=dict)
