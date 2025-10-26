# server/app/analysis.py
from __future__ import annotations
from typing import Optional, Dict

from .nlp.sentiment import (
    analyze_audio,
    NEUTRAL_V,
    NEUTRAL_A,
)  # prosody -> {valence, arousal, label}
from .nlp.fuse import fuse  # (current, state=None) -> {valence, arousal, label, state}


def _titlecase(label: str) -> str:
    return (label or "neutral").strip().capitalize()


def analyze_emotion(
    _text: str,  # kept for signature compatibility; ignored
    prosody_state: Optional[Dict] = None,
    smoothing_state: Optional[
        Dict
    ] = None,  # keep/return this if you want temporal smoothing
) -> Dict:
    """
    Audio-only emotion from prosody:
      prosody_state = {"rms":0..1, "rms_std":0..1, "speech_rate":0..1}
    Returns:
      {
        "label": str,
        "sentiment": float,   # == valence
        "valence": float,     # [-1, 1]
        "arousal": float,     # [0, 1]
        "state": {...}        # (optional) pass back into next call for smoothing
      }
    """
    prosody = prosody_state or {}

    # 1) Estimate VA from audio features only
    current = analyze_audio(prosody)  # {'valence','arousal','label'}

    # 2) Optionally smooth over time (EMA). DO NOT pass prosody here.
    fused = fuse(
        current, state=smoothing_state
    )  # {'valence','arousal','label','state'}

    v = float(fused.get("valence", 0.0))
    a = float(fused.get("arousal", 0.0))

    # 3) Neutral override (also applied inside fuse, but keep for clarity)
    if abs(v) < NEUTRAL_V and a < NEUTRAL_A:
        return {
            "label": "Neutral",
            "sentiment": 0.0,
            "valence": 0.0,
            "arousal": 0.0,
            "state": fused.get("state"),
        }

    label = _titlecase(str(fused.get("label", "neutral")))

    return {
        "label": label,
        "sentiment": round(v, 2),
        "valence": round(v, 2),
        "arousal": round(a, 2),
        "state": fused.get("state"),
    }
