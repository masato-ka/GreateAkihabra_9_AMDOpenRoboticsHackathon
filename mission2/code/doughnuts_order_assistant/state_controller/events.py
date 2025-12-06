from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
from typing import AsyncIterator

from api.schemas import GatewayEvent

logger = logging.getLogger(__name__)

# シンプルに「Chat Backend からの1接続」を想定したイベントキュー。
_event_queue: asyncio.Queue[GatewayEvent] = asyncio.Queue()

# Event socket path for inter-process communication
_EVENT_SOCKET_PATH = "/tmp/doughnut_events.sock"

# Server socket instance (for cleanup)
_event_server_socket: socket.socket | None = None


async def publish_event(event: GatewayEvent) -> None:
    """SSEストリームに流すイベントをキューに積む。

    プロセス内のキューに追加し、可能であればUnixソケット経由で
    他のプロセス（APIサーバー）にも送信する。
    """
    await _event_queue.put(event)
    logger.debug(
        f"[EVENTS] Published event to local queue: {event.type} for {getattr(event, 'request_id', 'N/A')}"
    )

    # Try to send event to API server via Unix socket (non-blocking)
    try:
        await _send_event_to_socket(event)
    except Exception as e:
        # If socket is not available (e.g., API server not running), log but don't fail
        logger.debug(f"[EVENTS] Failed to send event via socket: {e}")


async def _send_event_to_socket(event: GatewayEvent) -> None:
    """Unixソケット経由でイベントを送信する（非ブロッキング）。"""
    if not os.path.exists(_EVENT_SOCKET_PATH):
        logger.debug(
            f"[EVENTS] Socket path {_EVENT_SOCKET_PATH} does not exist, skipping socket send"
        )
        return

    try:
        loop = asyncio.get_event_loop()
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        await loop.sock_connect(client, _EVENT_SOCKET_PATH)

        event_data = json.dumps(event.model_dump(), ensure_ascii=False)
        await loop.sock_sendall(client, event_data.encode() + b"\n")
        client.close()
        logger.debug(
            f"[EVENTS] Sent event via socket: {event.type} for {getattr(event, 'request_id', 'N/A')}"
        )
    except Exception as e:
        # Ignore errors (socket might be closed or server not ready)
        logger.debug(f"[EVENTS] Error sending event via socket: {e}")


async def iter_events() -> AsyncIterator[str]:
    """SSE の data 行を1つずつ返す非同期イテレータ。

    複数クライアント対応はしておらず、基本1接続想定。
    """

    while True:
        event = await _event_queue.get()
        data = event.model_dump()
        yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def start_event_socket_server() -> None:
    """Unixソケットサーバーを起動して、workerプロセスからのイベントを受信する。"""
    global _event_server_socket

    # Remove socket file if it exists
    if os.path.exists(_EVENT_SOCKET_PATH):
        os.unlink(_EVENT_SOCKET_PATH)

    _event_server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    _event_server_socket.bind(_EVENT_SOCKET_PATH)
    _event_server_socket.listen(5)
    _event_server_socket.setblocking(False)
    logger.info(f"[EVENTS] Started event socket server at {_EVENT_SOCKET_PATH}")

    loop = asyncio.get_event_loop()

    async def handle_client(client):
        """クライアントからのイベントを受信してキューに追加する。"""
        try:
            buffer = b""
            while True:
                data = await loop.sock_recv(client, 4096)
                if not data:
                    break
                buffer += data
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if line:
                        try:
                            event_dict = json.loads(line.decode())
                            event = GatewayEvent.model_validate(event_dict)
                            await _event_queue.put(event)
                            logger.info(
                                f"[EVENTS] Received event via socket: {event.type} for {getattr(event, 'request_id', 'N/A')}"
                            )
                        except Exception as e:
                            # Ignore invalid events
                            logger.warning(
                                f"[EVENTS] Failed to parse event from socket: {e}"
                            )
        except Exception as e:
            logger.debug(f"[EVENTS] Error handling client: {e}")
        finally:
            client.close()

    async def accept_loop():
        """接続を受け付けるループ。"""
        logger.info("[EVENTS] Event socket server accepting connections...")
        while True:
            try:
                if _event_server_socket is None:
                    break
                client, _ = await loop.sock_accept(_event_server_socket)
                logger.debug("[EVENTS] Accepted connection from worker process")
                asyncio.create_task(handle_client(client))
            except Exception as e:
                logger.debug(f"[EVENTS] Error accepting connection: {e}")
                break

    # Start accepting connections in background
    asyncio.create_task(accept_loop())


async def stop_event_socket_server() -> None:
    """Unixソケットサーバーを停止する。"""
    global _event_server_socket

    if _event_server_socket is not None:
        try:
            _event_server_socket.close()
        except Exception:
            pass
        _event_server_socket = None

    if os.path.exists(_EVENT_SOCKET_PATH):
        os.unlink(_EVENT_SOCKET_PATH)
