"""
Chat Backend 側から Donut Gateway の REST / SSE を利用するための
ごく小さな同期クライアント例。

依存は標準ライブラリのみ（urllib / json）にしてあるので、
どんなバックエンド実装でも参考にしやすいはず。
"""

from __future__ import annotations

import json
from typing import Dict, Iterator
from urllib import request


def create_order(
    base_url: str,
    *,
    flavor: str,
) -> Dict:
    """POST /orders を叩いて注文を作成する。

    戻り値の例:
        {"request_id": "..."}
    """

    payload = {
        "flavor": flavor,
    }
    req = request.Request(
        f"{base_url.rstrip('/')}/orders",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body)


def cancel_order(base_url: str, request_id: str) -> Dict:
    """POST /orders/{id}/cancel を叩いてキャンセルする。"""

    req = request.Request(
        f"{base_url.rstrip('/')}/orders/{request_id}/cancel",
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body)


def sse_events(base_url: str) -> Iterator[Dict]:
    """GET /events に接続し、SSEの data 行を順次パースしてyieldする。

    例:
        for event in sse_events("http://localhost:8000"):
            handle_event(event)
    """

    req = request.Request(f"{base_url.rstrip('/')}/events", method="GET")
    with request.urlopen(req) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8").strip()
            if not line.startswith("data: "):
                continue
            data_str = line[len("data: ") :]
            try:
                yield json.loads(data_str)
            except json.JSONDecodeError:
                # ログなどで拾いたければ適宜拡張する
                continue


