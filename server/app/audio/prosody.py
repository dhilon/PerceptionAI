# server/app/prosody.py
import struct, math
from typing import Dict, List


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


class ProsodyTracker:
    """
    PCM16 mono tracker with adaptive RMS normalization + ZCR + crest factor.

    Outputs (normalized 0..1 unless stated):
      - rms:      average loudness
      - rms_std:  loudness variability across frames
      - speech_rate: voiced frame density proxy
      - zcr:      zero-crossing rate (harsh/noisy timbre indicator)
      - crest:    crest factor proxy (peak/RMS; high when shouty/punchy)
      - nf, pk:   internal noise floor & speech peak (debug)
    """

    def __init__(self, sample_rate: int = 16000, frame_ms: int = 30):
        self.sr = sample_rate
        self.frame = int(sample_rate * frame_ms / 1000)
        self._rms_series: List[float] = []
        self._zcr_series: List[float] = []
        self._crest_series: List[float] = []
        self._samples_total = 0
        self._voiced_frames = 0
        self._residual: List[float] = []

        # Adaptive calibration
        self.noise_floor = 0.008
        self.speech_peak = 0.20
        self._ema_nf_alpha = 0.05
        self._ema_pk_alpha = 0.05

    def add_chunk_pcm16(self, chunk: bytes):
        n = len(chunk) // 2
        if n <= 0:
            return
        samples = struct.unpack("<" + "h" * n, chunk)
        self._samples_total += n
        for s in samples:
            self._residual.append(s / 32768.0)
        while len(self._residual) >= self.frame:
            frame = self._residual[: self.frame]
            del self._residual[: self.frame]
            self._push_frame(frame)

    def _push_frame(self, f: List[float]):
        # RMS
        sq = 0.0
        peak = 0.0
        zc = 0
        prev = f[0]
        for x in f:
            sq += x * x
            ax = abs(x)
            if ax > peak:
                peak = ax
            # zero crossings
            if (x >= 0 and prev < 0) or (x < 0 and prev >= 0):
                zc += 1
            prev = x
        N = len(f)
        rms = math.sqrt(sq / N)
        # Crest factor proxy: cap to avoid inf when rms≈0
        crest = peak / max(rms, 1e-6)
        # Normalize CF to ~0..1 by mapping [1..10+] → [0..1]
        crest_norm = _clamp((crest - 1.0) / 9.0, 0.0, 1.0)

        # ZCR normalized: crossings per sample scaled to ~0..1
        # Max ZCR ~ 0.5 crossings per sample (alt sign each sample), so scale ~ /0.5
        zcr_norm = _clamp((zc / N) / 0.5, 0.0, 1.0)

        self._rms_series.append(rms)
        self._zcr_series.append(zcr_norm)
        self._crest_series.append(crest_norm)

        voiced = rms > (self.noise_floor * 1.6)
        if voiced:
            self._voiced_frames += 1
            self.speech_peak = (
                1 - self._ema_pk_alpha
            ) * self.speech_peak + self._ema_pk_alpha * max(self.speech_peak, rms)
        else:
            self.noise_floor = (
                1 - self._ema_nf_alpha
            ) * self.noise_floor + self._ema_nf_alpha * rms

    def finalize(self) -> Dict[str, float]:
        if not self._rms_series:
            return {
                "rms": 0.0,
                "rms_std": 0.0,
                "speech_rate": 0.0,
                "zcr": 0.0,
                "crest": 0.0,
            }

        avg = sum(self._rms_series) / len(self._rms_series)
        mean = avg
        var = sum((r - mean) ** 2 for r in self._rms_series) / len(self._rms_series)
        std = math.sqrt(var)

        # Adaptive normalization for loudness
        lo = max(0.001, self.noise_floor)
        hi = max(lo + 0.02, min(0.9, self.speech_peak * 1.2))
        rng = max(1e-6, hi - lo)

        def norm(x: float) -> float:
            return _clamp((x - lo) / rng, 0.0, 1.0)

        rms_norm = norm(avg)
        rmsstd_norm = _clamp(std / (rng * 0.9), 0.0, 1.0)

        voiced_frac = self._voiced_frames / max(1, len(self._rms_series))
        speech_rate = _clamp((voiced_frac - 0.2) / 0.6, 0.0, 1.0)

        # Aggregate zcr & crest across frames
        zcr = _clamp(sum(self._zcr_series) / len(self._zcr_series), 0.0, 1.0)
        crest = _clamp(sum(self._crest_series) / len(self._crest_series), 0.0, 1.0)

        return {
            "rms": rms_norm,
            "rms_std": rmsstd_norm,
            "speech_rate": speech_rate,
            "zcr": zcr,
            "crest": crest,
            "nf": round(self.noise_floor, 5),
            "pk": round(self.speech_peak, 5),
        }

    def reset(self):
        self._rms_series.clear()
        self._zcr_series.clear()
        self._crest_series.clear()
        self._samples_total = 0
        self._voiced_frames = 0
        self._residual.clear()
