# server/app/fuse.py
"""
Fuse text-based valence/arousal with optional prosody features from audio.

Inputs:
  text_scores: dict from sentiment.analyze_text(...)
  prosody: {
      "rms": float in [0..1]         # loudness (normalized)
      "pitch_var": float in [0..1]   # pitch variability
      "speech_rate": float in [0..1] # words/sec normalized
  }  # each is optional

Output:
  { valence, arousal, label }
"""

from __future__ import annotations
from typing import Dict, Optional
import math

NEUTRAL_V = 0.10
NEUTRAL_A = 0.10

# weights: valence mainly text; arousal from both
W_TEXT_VAL = 0.9
W_AUDIO_VAL = 0.1
W_TEXT_ARO = 0.5
W_AUDIO_ARO = 0.5


def _nz(x: Optional[float], default=0.0) -> float:
    return float(x) if x is not None else default


def _normalize_valence(v: float) -> float:
    return max(-1.0, min(1.0, v))


def _normalize_arousal(a: float) -> float:
    return max(0.0, min(1.0, a))


def _label_from_quadrant(v: float, a: float) -> str:
    # simple quadrant mapping, refined around chart semantics
    if abs(v) < NEUTRAL_V and a < NEUTRAL_A:
        return "neutral"
    if v >= 0 and a >= 0.6:
        return "excited" if v > 0.6 else "happy"
    if v >= 0 and a < 0.4:
        return "calm" if v >= 0.6 else "content"
    if v < 0 and a >= 0.6:
        return "angry"  # includes afraid/frustrated cluster
    if v < 0 and a < 0.4:
        return "sad"
    return "neutral"


def fuse(text_scores: Dict, prosody: Optional[Dict] = None) -> Dict[str, float | str]:
    prosody = prosody or {}
    v_text = float(text_scores.get("valence", 0.0))
    a_text = float(text_scores.get("arousal", 0.0))

    # Map audio features → arousal proxy in [0..1]
    rms = _nz(prosody.get("rms"))  # louder → higher arousal
    pitch_var = _nz(prosody.get("pitch_var"))  # more variation → higher arousal
    speech_rt = _nz(prosody.get("speech_rate"))  # faster → higher arousal

    # Combine audio features (bounded)
    a_audio = max(0.0, min(1.0, 0.50 * rms + 0.30 * pitch_var + 0.20 * speech_rt))

    # Valence slightly nudged by prosody (anger tends to be louder/variable, but keep small)
    v_audio = (
        0.20 * (rms + pitch_var) - 0.10 * speech_rt
    )  # tiny effect; could be learned

    # Fuse
    v = _normalize_valence(W_TEXT_VAL * v_text + W_AUDIO_VAL * v_audio)
    a = _normalize_arousal(W_TEXT_ARO * a_text + W_AUDIO_ARO * a_audio)

    # Neutral rule
    if abs(v) < NEUTRAL_V and a < NEUTRAL_A:
        return {"valence": 0.0, "arousal": 0.0, "label": "neutral"}

    label = _label_from_quadrant(v, a)
    return {"valence": v, "arousal": a, "label": label}
