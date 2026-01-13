"""WebSocket helper utilities."""

from fastapi import WebSocket
import json


async def safe_send(ws: WebSocket, obj):
    try:
        await ws.send_text(json.dumps(obj))
    except:
        pass
