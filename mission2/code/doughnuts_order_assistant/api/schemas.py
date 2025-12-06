from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


Flavor = Literal["chocolate", "strawberry"]


class OrderRequest(BaseModel):
    """POST /orders のリクエストボディ。"""

    flavor: Flavor
    table_id: str = Field(..., description="テーブルIDなどの識別子")
    user_id: str = Field(..., description="チャット側のユーザーID")


class OrderCreated(BaseModel):
    """POST /orders のレスポンス。"""

    request_id: str


class CancelResponse(BaseModel):
    canceled: bool


class EventType(str, Enum):
    STATUS_UPDATE = "status_update"
    COMPLETED = "completed"
    ERROR = "error"


class StatusUpdateEvent(BaseModel):
    type: Literal[EventType.STATUS_UPDATE] = EventType.STATUS_UPDATE
    request_id: str
    stage: str
    progress: float = Field(ge=0.0, le=1.0)
    message: str


class CompletedEvent(BaseModel):
    type: Literal[EventType.COMPLETED] = EventType.COMPLETED
    request_id: str
    result: dict


class ErrorEvent(BaseModel):
    type: Literal[EventType.ERROR] = EventType.ERROR
    request_id: Optional[str] = None
    message: str


GatewayEvent = StatusUpdateEvent | CompletedEvent | ErrorEvent


