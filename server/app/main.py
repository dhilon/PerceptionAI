import json, asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from .fish_audio.client import get_fish_client

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws/stream")
async def ws_stream(ws: WebSocket):
    await ws.accept()
    fish = get_fish_client()

    try:
        await fish.connect(
            {"language": "en", "punctuate": True, "word_timestamps": True}
        )
    except Exception as e:
        await ws.send_json(
            {"type": "error", "stage": "fish.connect", "message": str(e)}
        )
        await ws.close()
        return

    events_task = asyncio.create_task(pipe_events(fish, ws))

    try:
        while True:
            msg = await ws.receive()

            # 1) Handle disconnect cleanly
            if msg.get("type") in ("websocket.disconnect", "websocket.close"):
                break

            # 2) Binary audio frames (PCM16)
            if msg.get("bytes") is not None:
                await fish.send_audio(msg["bytes"])
                continue

            # 3) JSON control messages
            text_payload = msg.get("text")
            if text_payload:
                try:
                    data = json.loads(text_payload)
                except Exception:
                    await ws.send_json(
                        {"type": "error", "stage": "parse", "message": "invalid JSON"}
                    )
                    continue

                t = data.get("type")
                if t == "end":
                    try:
                        await fish.mark_end_of_input()
                    except Exception as e:
                        await ws.send_json(
                            {"type": "error", "stage": "fish.end", "message": str(e)}
                        )
                        await ws.close()
                        return
                # (add other control messages here)
                continue

            # 4) Unknown/empty frame: ignore
            # Some runtimes send keepalives with neither text nor bytes.
            continue

    except WebSocketDisconnect:
        pass
    finally:
        events_task.cancel()
        await fish.close()


async def pipe_events(fish, ws: WebSocket):
    async for ev in fish.events():
        await ws.send_json(ev)
