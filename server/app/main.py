import os
import json
import asyncio
import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from .config import Settings
from .fish_audio.client import FishAudioClient
from .audio.prosody import ProsodyEngine
from .nlp.sentiment import get_sentiment
from .nlp.fuse import fuse_scores

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

settings = Settings()
prosody = ProsodyEngine(sr=16000)


@app.websocket("/ws/stream")
async def ws_stream(ws: WebSocket):
    await ws.accept()
    fish = FishAudioClient()
    await fish.connect({"language": "en", "punctuate": True, "word_timestamps": True})

    async def pump_fish_events():
        async for ev in fish.events():
            et = ev.get("type")
            if et in ("transcript.partial", "transcript.final"):
                text = ev["data"].get("text", "")
                words = ev["data"].get("words", [])
                sentiment = (
                    get_sentiment(text) if et == "transcript.final" and text else None
                )
                fused = fuse_scores(prosody.current_state(), sentiment)
                await ws.send_json(
                    {
                        "type": et,
                        "text": text,
                        "words": words,
                        "sentiment": sentiment,
                        "fused": fused,
                    }
                )
            else:
                await ws.send_json(ev)

    fish_task = asyncio.create_task(pump_fish_events())

    try:
        while True:
            # Expect binary PCM16 frames or JSON control messages
            message = await ws.receive()
            if "bytes" in message and message["bytes"] is not None:
                chunk = message["bytes"]
                prosody.push_audio(chunk)
                # send to fish (base64 if required by API — update client accordingly)
                await fish.send_audio(chunk)
                # also emit prosody frame to UI
                arousal, valence, stats = prosody.compute_frame()
                await ws.send_json(
                    {
                        "type": "prosody.frame",
                        "arousal": arousal,
                        "valence": valence,
                        "stats": stats,
                    }
                )
            else:
                data = json.loads(message["text"])
                if data.get("type") == "end":
                    await fish.mark_end_of_input()
                # handle other client controls here (mute, mark, etc.)
    except WebSocketDisconnect:
        pass
    finally:
        fish_task.cancel()
        await fish.close()
