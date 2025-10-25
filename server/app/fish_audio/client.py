import os
import asyncio
import json
import websockets
from typing import AsyncIterator, Dict, Optional, Union

FISH_REALTIME_WS = os.getenv(
    "FISH_REALTIME_WS", "wss://api.fish.audio/v1/realtime"
)  # TODO: set real URL
FISH_API_KEY = os.getenv("FISH_API_KEY", "")


class FishAudioClient:
    """
    Minimal streaming STT client for fish.audio.

    Contract:
    - call `connect(session_params)` to open WS
    - call `send_audio(frame_bytes)` repeatedly (16kHz mono PCM or Opus per fish.audio spec)
    - await `events()` to receive partial/final transcripts with word times
    - call `close()`
    """

    def __init__(self, api_key: Optional[str] = None, ws_url: Optional[str] = None):
        self.api_key = api_key or FISH_API_KEY
        self.ws_url = ws_url or FISH_REALTIME_WS
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._events_queue: "asyncio.Queue[Dict]" = asyncio.Queue()
        self._receiver_task: Optional[asyncio.Task] = None

    async def connect(self, session_params: Optional[Dict] = None):
        headers = [("Authorization", f"Bearer {self.api_key}")]
        self._ws = await websockets.connect(
            self.ws_url, extra_headers=headers, ping_interval=20, ping_timeout=20
        )
        # Initialize session (language, diarization, word_timestamps, etc.)
        init_msg = {
            "type": "session.init",
            "data": session_params
            or {
                "language": "en",
                "punctuate": True,
                "word_timestamps": True,
                "diarization": False,
            },
        }
        await self._ws.send(json.dumps(init_msg))
        self._receiver_task = asyncio.create_task(self._receiver())

    async def _receiver(self):
        assert self._ws
        try:
            async for raw in self._ws:
                try:
                    event = json.loads(raw)
                except Exception:
                    event = {
                        "type": "error",
                        "data": {"message": "bad_json", "raw": raw},
                    }
                await self._events_queue.put(event)
        except Exception as e:
            await self._events_queue.put({"type": "error", "data": {"message": str(e)}})

    async def send_audio(
        self, audio_bytes: bytes, encoding: str = "pcm16", sample_rate: int = 16000
    ):
        """
        Push a raw audio frame. If fish.audio expects Opus, encode before calling this.
        """
        assert self._ws
        payload = {
            "type": "audio.chunk",
            "data": {
                "encoding": encoding,
                "sample_rate": sample_rate,
                "audio": audio_bytes.decode(
                    "latin1"
                ),  # or base64 if API requires; swap accordingly
            },
        }
        await self._ws.send(json.dumps(payload))

    async def mark_end_of_input(self):
        assert self._ws
        await self._ws.send(json.dumps({"type": "audio.end"}))

    async def events(self) -> AsyncIterator[Dict]:
        while True:
            ev = await self._events_queue.get()
            yield ev

    async def close(self):
        if self._receiver_task:
            self._receiver_task.cancel()
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
        self._ws = None
