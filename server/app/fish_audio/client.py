import os, ssl, json, asyncio, base64, tempfile, wave
from typing import AsyncIterator, Dict, Optional
import httpx
import websockets

from ..config import Settings

S = Settings()


# --------------------
# REST (kept for fallback/testing)
# --------------------
class FishAudioASRClient:
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
        pass

    async def send_audio(self, audio_bytes: bytes, **_):
        self._buf.extend(audio_bytes)

    async def load_audio_bytes(self, audio_bytes: bytes):
        # Replace existing buffer with new audio bytes (for one-shot uploads)
        self._buf = bytearray(audio_bytes)

    async def mark_end_of_input(
        self, language: str = "en", ignore_timestamps: bool = False
    ):
        import os

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            with wave.open(tmp.name, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
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
            r = await client.post(
                S.FISH_ASR_URL, headers=headers, data=data, files=files
            )
            r.raise_for_status()
            resp = r.json()

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
            yield await self._events.get()

    async def close(self):
        self._buf.clear()


# --------------------
# Realtime WS
# --------------------
class FishAudioRealtimeWSClient:
    """
    Connects to Fish Audio realtime WS, sends JSON-framed base64 PCM16 chunks,
    and yields server events (partial + final).
    """

    def __init__(self, api_key: Optional[str] = None, ws_url: Optional[str] = None):
        self.api_key = (api_key or S.FISH_API_KEY).strip()
        self.ws_url = (ws_url or S.FISH_REALTIME_WS).strip()
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._events: "asyncio.Queue[Dict]" = asyncio.Queue()
        self._sr = 16000

    async def connect(self, session_params: Optional[Dict] = None):
        ssl_ctx = ssl.create_default_context()
        params = session_params or {
            "language": "en",
            "punctuate": True,
            "word_timestamps": True,
        }

        # try a few common auth shapes:
        attempts = [
            dict(
                additional_headers={"Authorization": f"Bearer {self.api_key}"},
                subprotocols=None,
            ),
            dict(additional_headers={"X-API-Key": self.api_key}, subprotocols=None),
            dict(additional_headers=None, subprotocols=[f"bearer,{self.api_key}"]),
            dict(
                additional_headers={"Authorization": f"Bearer {self.api_key}"},
                subprotocols=["fish.realtime.v1"],
            ),
        ]

        last_err = None
        for cfg in attempts:
            try:
                kw = dict(ssl=ssl_ctx, ping_interval=20, ping_timeout=20)
                if cfg["additional_headers"] is not None:
                    kw["additional_headers"] = cfg["additional_headers"]
                if cfg["subprotocols"] is not None:
                    kw["subprotocols"] = cfg["subprotocols"]

                self._ws = await websockets.connect(self.ws_url, **kw)

                # send a session init (common pattern)
                init = {"type": "session.init", "data": params}
                await self._ws.send(json.dumps(init))

                # start receiver
                asyncio.create_task(self._receiver())
                return
            except Exception as e:
                last_err = e
        raise RuntimeError(
            f"fish realtime connect failed: {type(last_err).__name__}: {last_err}"
        )

    async def _receiver(self):
        try:
            async for raw in self._ws:
                try:
                    ev = (
                        json.loads(raw)
                        if isinstance(raw, str)
                        else {"type": "binary", "len": len(raw)}
                    )
                except Exception:
                    ev = {"type": "error", "data": {"message": "bad_json"}}
                await self._events.put(ev)
        except Exception as e:
            await self._events.put({"type": "error", "data": {"message": str(e)}})

    def _b64(self, chunk: bytes) -> str:
        return base64.b64encode(chunk).decode("ascii")

    async def send_audio(
        self, audio_bytes: bytes, encoding: str = "pcm16", sample_rate: int = 16000
    ):
        """
        Default: JSON-framed base64 chunk (widely accepted by realtime APIs).
        If Fish expects a different envelope, tweak the 'payload' shape.
        """
        self._sr = sample_rate
        payload = {
            "type": "audio.chunk",
            "data": {
                "encoding": encoding,
                "sample_rate": sample_rate,
                "audio": self._b64(audio_bytes),
            },
        }
        await self._ws.send(json.dumps(payload))

    async def load_audio_bytes(
        self, audio_bytes: bytes, encoding: str = "pcm16", sample_rate: int = 16000
    ):
        # For realtime, treat as a single chunk upload
        await self.send_audio(audio_bytes, encoding=encoding, sample_rate=sample_rate)

    async def mark_end_of_input(self):
        await self._ws.send(json.dumps({"type": "audio.end"}))

    async def events(self) -> AsyncIterator[Dict]:
        while True:
            yield await self._events.get()

    async def close(self):
        if self._ws:
            await self._ws.close()


# --------------------
# Factory
# --------------------
def get_fish_client():
    mode = (S.FISH_MODE or "asr_rest").lower()
    if mode == "realtime_ws":
        return FishAudioRealtimeWSClient()
    if mode == "asr_rest":
        return FishAudioASRClient()

    # simple mock for local dev
    class _Mock:
        def __init__(self):
            self._q = asyncio.Queue()

        async def connect(self, *_a, **_k):
            asyncio.create_task(self._feed())

        async def _feed(self):
            for t in ["hello", "this is mock", "ending"]:
                await asyncio.sleep(0.7)
                await self._q.put({"type": "transcript.partial", "data": {"text": t}})
            await self._q.put({"type": "transcript.final", "data": {"text": "ending"}})

        async def send_audio(self, *_):
            pass

        async def load_audio_bytes(self, *_):
            pass

        async def mark_end_of_input(self):
            pass

        async def events(self):
            while True:
                yield await self._q.get()

        async def close(self):
            pass

    return _Mock()
