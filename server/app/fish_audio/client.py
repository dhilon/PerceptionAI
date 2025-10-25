import os, io, wave, asyncio, json, ssl, tempfile
from typing import AsyncIterator, Dict, Optional
import httpx
import websockets

from ..config import Settings

S = Settings()


class FishAudioASRClient:
    """
    Buffers PCM16 audio, writes temporary WAV, calls Fish ASR REST,
    yields one final transcript event.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        asr_url: Optional[str] = None,
        sr: int = 16000,
    ):
        self.api_key = (api_key or S.FISH_API_KEY).strip()
        self.asr_url = (asr_url or S.FISH_ASR_URL).strip()
        self.sr = sr
        self._buf = bytearray()
        self._events: "asyncio.Queue[Dict]" = asyncio.Queue()

    async def connect(self, *_args, **_kwargs):
        # no-op for REST; mimic interface
        pass

    async def send_audio(self, audio_bytes: bytes, **_):
        self._buf.extend(audio_bytes)

    async def mark_end_of_input(
        self, language: str = "en", ignore_timestamps: bool = False
    ):
        # write temp WAV
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            with wave.open(tmp.name, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # PCM16
                wf.setframerate(self.sr)
                wf.writeframes(self._buf)
            fname = tmp.name

        headers = {"Authorization": f"Bearer {self.api_key}"}
        data = {
            "language": language,
            "ignore_timestamps": str(ignore_timestamps).lower(),
        }
        files = {"audio": open(fname, "rb")}

        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(self.asr_url, headers=headers, data=data, files=files)
            r.raise_for_status()
            resp = r.json()

        # push a final transcript event
        await self._events.put(
            {
                "type": "transcript.final",
                "data": {
                    "text": resp.get("text", ""),
                    "segments": resp.get("segments", []),
                    "duration": resp.get("duration"),
                },
            }
        )

    async def events(self) -> AsyncIterator[Dict]:
        while True:
            ev = await self._events.get()
            yield ev

    async def close(self):
        self._buf.clear()


class FishAudioRealtimeWSClient:
    """
    Optional: realtime WS path (use when your auth/URL are confirmed).
    """

    def __init__(self, api_key: Optional[str] = None, ws_url: Optional[str] = None):
        self.api_key = (api_key or S.FISH_API_KEY).strip()
        self.ws_url = (ws_url or S.FISH_REALTIME_WS).strip()
        self._ws = None
        self._events: "asyncio.Queue[Dict]" = asyncio.Queue()

    async def connect(self, session_params: Optional[Dict] = None):
        ssl_ctx = ssl.create_default_context()
        headers = {"Authorization": f"Bearer {self.api_key}"}
        self._ws = await websockets.connect(
            self.ws_url,
            ssl=ssl_ctx,
            additional_headers=headers,  # if this 401s, try X-API-Key or subprotocols
            ping_interval=20,
            ping_timeout=20,
        )
        init_msg = {
            "type": "session.init",
            "data": session_params
            or {"language": "en", "punctuate": True, "word_timestamps": True},
        }
        await self._ws.send(json.dumps(init_msg))
        asyncio.create_task(self._receiver())

    async def _receiver(self):
        try:
            async for raw in self._ws:
                try:
                    ev = json.loads(raw)
                except Exception:
                    ev = {"type": "error", "data": {"message": "bad_json"}}
                await self._events.put(ev)
        except Exception as e:
            await self._events.put({"type": "error", "data": {"message": str(e)}})

    async def send_audio(
        self, audio_bytes: bytes, encoding: str = "pcm16", sample_rate: int = 16000
    ):
        payload = {
            "type": "audio.chunk",
            "data": {
                "encoding": encoding,
                "sample_rate": sample_rate,
                "audio": audio_bytes.decode("latin1"),
            },
        }
        await self._ws.send(json.dumps(payload))

    async def mark_end_of_input(self):
        await self._ws.send(json.dumps({"type": "audio.end"}))

    async def events(self) -> AsyncIterator[Dict]:
        while True:
            yield await self._events.get()

    async def close(self):
        if self._ws:
            await self._ws.close()


def get_fish_client():
    if S.FISH_MODE.lower() == "asr_rest":
        return FishAudioASRClient()
    if S.FISH_MODE.lower() == "realtime_ws":
        return FishAudioRealtimeWSClient()

    # mock mode for dev without calling Fish
    class _Mock:
        def __init__(self):
            self._q = asyncio.Queue()

        async def connect(self, *_, **__):
            asyncio.create_task(self._feed())

        async def _feed(self):
            for t in ["hello", "this is mock", "ending"]:
                await asyncio.sleep(0.8)
                await self._q.put(
                    {"type": "transcript.partial", "data": {"text": t, "segments": []}}
                )
            await self._q.put(
                {"type": "transcript.final", "data": {"text": "ending", "segments": []}}
            )

        async def send_audio(self, *_):
            pass

        async def mark_end_of_input(self, *_):
            pass

        async def events(self):
            while True:
                yield await self._q.get()

        async def close(self):
            pass

    return _Mock()
