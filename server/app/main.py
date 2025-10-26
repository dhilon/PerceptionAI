# server/app/main.py
import json, asyncio, contextlib
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .fish_audio.client import get_fish_client, FishAudioASRClient
from .analysis import analyze_emotion
from .ws_utils import safe_send_json, safe_close
from .audio.prosody import ProsodyTracker

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

tracker = ProsodyTracker(sample_rate=16000, frame_ms=30)


@app.websocket("/ws/stream")
async def ws_stream(ws: WebSocket):
    await ws.accept()
    fish = get_fish_client()
    # Prosody engine per connection to derive voice-only arousal/valence
    try:
        await fish.connect()
        # after await fish.connect(...)
        await safe_send_json(
            ws,
            {"type": "debug", "stage": "stt", "message": f"mode={type(fish).__name__}"},
        )

    except Exception as e:
        msg = str(e)
        if "HTTP 401" in msg or "HTTP 402" in msg or "Payment" in msg:
            await safe_send_json(
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

    events_task = asyncio.create_task(
        pipe_events(fish, ws, get_prosody=lambda: tracker.finalize())
    )

    events_task = asyncio.create_task(
        pipe_events(fish, ws, get_prosody=lambda: tracker.finalize())
    )

    try:
        pending_emotion_only = None

        while True:
            msg = await ws.receive()

            if msg.get("bytes") is not None:
                chunk = msg["bytes"]
                tracker.add_chunk_pcm16(chunk)
                await fish.send_audio(chunk)
                continue

            txt = msg.get("text")
            if txt:
                try:
                    data = json.loads(txt)
                except Exception:
                    await safe_send_json(
                        ws, {"type": "error", "stage": "parse", "message": "bad json"}
                    )
                    continue

                if data.get("type") == "end":
                    # finalize input to STT
                    await fish.mark_end_of_input()

                    # start a timeout task that will fire emotion-only if no transcript arrives
                    async def fire_emotion_only():
                        await asyncio.sleep(6.0)
                        prosody = tracker.finalize()
                        emo = analyze_emotion(ws, prosody_state=prosody)
                        await safe_send_json(
                            ws,
                            {
                                "type": "transcript.final",
                                "data": {
                                    "text": "",
                                    "emotion": emo,
                                    "source": "timeout",
                                },
                            },
                        )
                        tracker.reset()

                    pending_emotion_only = asyncio.create_task(fire_emotion_only())
                    pending_task_ref["t"] = pending_emotion_only

                continue

    except WebSocketDisconnect:
        pass
    finally:
        with contextlib.suppress(Exception):
            await fish.close()
        tracker.reset()
        events_task.cancel()


# keep a small state across finals for smoothing
_va_state = {"valence": 0.0, "arousal": 0.0}  # or None to start empty
_have_state = False

# server/app/pipe.py (or inline in main.py)
pending_task_ref = {"t": None}  # tiny holder; or close over a nonlocal in main


async def pipe_events(fish, ws: WebSocket, get_prosody):
    async for ev in fish.events():
        if ev.get("type") == "transcript.final":
            # cancel timeout if active
            t = pending_task_ref.get("t")
            if t and not t.done():
                t.cancel()
                pending_task_ref["t"] = None

            # attach emotion
            try:
                prosody = get_prosody() or {}
            except Exception:
                prosody = {}
            emo = analyze_emotion("", prosody_state=prosody)

            ev.setdefault("data", {})
            ev["data"]["emotion"] = emo
            ev["data"]["source"] = ev["data"].get("source", "stt")
            await safe_send_json(ws, ev)
            continue

        # forward other events (errors/debug)
        await safe_send_json(ws, ev)
