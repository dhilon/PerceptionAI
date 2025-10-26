# server/app/main.py
import json, asyncio, contextlib
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from .fish_audio.client import get_fish_client, FishAudioASRClient
from .analysis import analyze_emotion
from .ws_utils import safe_send_json, safe_close
from .nlp.sentiment import analyze_text
from .nlp.fuse import fuse

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def health():
    return {"ok": True}


@app.get("/routes")
def list_routes():
    out = []
    for r in app.router.routes:
        if isinstance(r, APIRoute):
            out.append({"path": r.path, "methods": list(r.methods)})
        else:
            # WebSocketRoute doesn't subclass APIRoute, so capture path attr
            path = getattr(r, "path", str(r))
            out.append({"path": path, "methods": ["WS"]})
    return out


@app.websocket("/ws/stream")
async def ws_stream(ws: WebSocket):
    await ws.accept()
    fish = get_fish_client()

    # Try to connect to Fish; if it fails, optionally fall back to REST
    try:
        await fish.connect(
            {"language": "en", "punctuate": True, "word_timestamps": True}
        )
    except Exception as e:
        msg = str(e)
        # Optional fallback to REST if realtime blocked (401/402)
        if "HTTP 401" in msg or "HTTP 402" in msg or "Payment" in msg:
            ok = await safe_send_json(
                ws,
                {
                    "type": "debug",
                    "stage": "fallback",
                    "message": "Realtime unavailable; using REST",
                },
            )
            fish = FishAudioASRClient()
            try:
                await fish.connect()
            except Exception as e2:
                await safe_send_json(
                    ws, {"type": "error", "stage": "fish.connect", "message": str(e2)}
                )
                await safe_close(ws, 1011)
                return
        else:
            await safe_send_json(
                ws, {"type": "error", "stage": "fish.connect", "message": msg}
            )
            await safe_close(ws, 1011)
            return

    events_task = asyncio.create_task(pipe_events(fish, ws))

    try:
        while True:
            try:
                msg = await ws.receive()
            except WebSocketDisconnect:
                break

            if msg.get("type") in ("websocket.disconnect", "websocket.close"):
                break

            if msg.get("bytes") is not None:
                await fish.send_audio(msg["bytes"])
                continue

            text = msg.get("text")
            if text:
                try:
                    data = json.loads(text)
                except Exception:
                    if not await safe_send_json(
                        ws,
                        {"type": "error", "stage": "parse", "message": "invalid JSON"},
                    ):
                        break
                    continue

                if data.get("type") == "end":
                    try:
                        await fish.mark_end_of_input()
                    except Exception as e:
                        await safe_send_json(
                            ws,
                            {"type": "error", "stage": "fish.end", "message": str(e)},
                        )
                        await safe_close(ws, 1011)
                        return
                elif data.get("type") == "upload":
                    # Expect base64 PCM16 or raw bytes over WS in future
                    try:
                        b64 = data.get("audio_b64")
                        if not isinstance(b64, str):
                            raise ValueError("missing audio_b64")
                        import base64

                        audio_bytes = base64.b64decode(b64)
                        # Replace internal buffer with uploaded bytes and finalize
                        if hasattr(fish, "load_audio_bytes"):
                            await fish.load_audio_bytes(audio_bytes)
                        else:
                            # fallback: stream once via send_audio
                            await fish.send_audio(audio_bytes)
                        await fish.mark_end_of_input()
                    except Exception as e:
                        await safe_send_json(
                            ws,
                            {"type": "error", "stage": "upload", "message": str(e)},
                        )
                continue

    finally:
        events_task.cancel()
        with contextlib.suppress(Exception):
            await fish.close()
        await safe_close(ws)


async def pipe_events(fish, ws):
    async for ev in fish.events():
        if ev.get("type") == "transcript.final":
            text = ev.get("data", {}).get("text", "")
            text_scores = analyze_text(text)

            # Optional: pass prosody you compute during streaming
            # e.g., prosody = {"rms": avg_rms_0_1, "pitch_var": pv, "speech_rate": sr}
            prosody = {}
            emo = fuse(text_scores, prosody)

            ev.setdefault("data", {})
            ev["data"]["emotion"] = emo

        await ws.send_json(ev)
