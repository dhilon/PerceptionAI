import asyncio
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from app.audio.recorder import LiveMicRecorder
from app.audio.feature_extractor import extract_features
from app.model.emotion_model import EmotionModel
from app.utils.websocket_utils import safe_send
from app.config import FRAME_SIZE
import numpy as np

app = FastAPI()
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

emotion_model = EmotionModel()


async def _audio_ws_impl(ws: WebSocket):
    await ws.accept()
    if not emotion_model.is_ready():
        await safe_send(
            ws,
            {
                "type": "error",
                "message": "Emotion model is not loaded. Train a model or place a valid file at app/model/emotion_model.pkl.",
            },
        )
        return
    recorder = LiveMicRecorder()
    loop = asyncio.get_event_loop()
    for frame in recorder.stream():
        pcm16 = frame.reshape(-1)
        # Extract acoustic/prosody/emotional texture features
        feats = await loop.run_in_executor(None, extract_features, pcm16)
        # Predict emotion
        emo = emotion_model.predict(feats)
        await safe_send(
            ws, {"type": "emotion", "emotion": emo["label"], "proba": emo["proba"]}
        )
        await asyncio.sleep(FRAME_SIZE)


@app.websocket("/ws/audio")
async def audio_ws(ws: WebSocket):
    await _audio_ws_impl(ws)


@app.websocket("/ws/stream")
async def audio_ws_compat(ws: WebSocket):
    await _audio_ws_impl(ws)
