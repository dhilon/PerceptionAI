# server/app/ws_utils.py
from contextlib import suppress
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect


async def safe_send_json(ws: WebSocket, payload) -> bool:
    try:
        await ws.send_json(payload)
        return True
    except WebSocketDisconnect:
        return False


async def safe_close(ws: WebSocket, code: int = 1000):
    with suppress(Exception):
        await ws.close(code=code)
