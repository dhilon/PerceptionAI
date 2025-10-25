import numpy as np
import collections
from typing import Tuple, Dict


class ProsodyEngine:
    def __init__(self, sr=16000, window_ms=1000, hop_ms=500):
        self.sr = sr
        self.window = int(sr * window_ms / 1000)
        self.hop = int(sr * hop_ms / 1000)
        self._buf = bytearray()
        self._last_text_words = collections.deque(maxlen=128)
        self._last_seconds_text = 5.0

    def push_audio(self, pcm16: bytes):
        self._buf.extend(pcm16)

    def _bytes_to_np(self, b: bytes) -> np.ndarray:
        return np.frombuffer(b, dtype=np.int16).astype(np.float32) / 32768.0

    def compute_frame(self) -> Tuple[float, float, Dict]:
        if len(self._buf) < self.window * 2:
            return 0.5, 0.5, {"ready": False}
        # windowed slice
        wav = self._bytes_to_np(self._buf[: self.window * 2])
        # slide buffer
        del self._buf[: self.hop * 2]

        # energy
        rms = np.sqrt(np.mean(wav**2) + 1e-9)
        energy_db = 20 * np.log10(rms + 1e-9)

        # naïve pitch via autocorr (bounded 70–350 Hz)
        f0 = self._estimate_pitch(wav)

        # pretend speech rate (words/sec) comes from recent text (hook later)
        wps = 2.0  # stub, wire to recent transcript count / seconds

        # map to arousal/valence heuristics (0..1)
        arousal = (
            _sigmoid(0.15 * (energy_db + 20))
            * _sigmoid(0.03 * (f0 - 120))
            * _sigmoid(0.7 * (wps - 1))
        )
        valence = 0.5 + 0.5 * np.tanh(0.01 * (f0 - 120))  # weak proxy

        stats = {
            "pitch_hz": float(f0),
            "energy_db": float(energy_db),
            "speech_rate_wps": float(wps),
        }
        return float(arousal), float(valence), stats

    def current_state(self) -> Dict:
        # return latest derived state if you cache it; simple stub for now
        return {"arousal": 0.5, "valence": 0.5}

    def _estimate_pitch(self, wav: np.ndarray) -> float:
        # ultra-simple ACF pitch for demo (not robust, good enough for hack)
        sr = self.sr
        min_f, max_f = 70, 350
        min_lag, max_lag = int(sr / max_f), int(sr / min_f)
        corr = np.correlate(wav, wav, mode="full")[len(wav) - 1 :]
        lag = np.argmax(corr[min_lag:max_lag]) + min_lag
        if lag <= 0:
            return 0.0
        return sr / lag


def _sigmoid(x: float) -> float:
    return 1 / (1 + np.exp(-x))
