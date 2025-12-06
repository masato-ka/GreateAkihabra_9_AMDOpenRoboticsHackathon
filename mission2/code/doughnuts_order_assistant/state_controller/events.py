from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

from doughnuts_order_assistant.api.schemas import GatewayEvent

# シンプルに「Chat Backend からの1接続」を想定したイベントキュー。
_event_queue: asyncio.Queue[GatewayEvent] = asyncio.Queue()


async def publish_event(event: GatewayEvent) -> None:
    """SSEストリームに流すイベントをキューに積む。"""

    await _event_queue.put(event)


async def iter_events() -> AsyncIterator[str]:
    """SSE の data 行を1つずつ返す非同期イテレータ。

    複数クライアント対応はしておらず、基本1接続想定。
    """

    while True:
        event = await _event_queue.get()
        data = event.model_dump()
        yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
