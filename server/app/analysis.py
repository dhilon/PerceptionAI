# server/app/analysis.py
from __future__ import annotations
from typing import Optional, Dict

# Use the valence–arousal analyzers
from .nlp.sentiment import analyze_text  # returns {valence, arousal, label}
from .nlp.fuse import fuse  # returns {valence, arousal, label}

# Neutral threshold (as requested)
NEUTRAL_VALENCE = 0.10
NEUTRAL_AROUSAL = 0.10


def _titlecase(label: str) -> str:
    # Keep your UI style (e.g., "Calm", "Very Angry", etc.)
    return (label or "neutral").strip().capitalize()


def analyze_emotion(text: str, prosody_state: Optional[Dict] = None) -> Dict:
    """
    Turns text (+ optional prosody) into a fused emotion with valence/arousal.
    Neutral when |valence| < 0.10 and arousal < 0.10.
    Returns:
      {
        "label": "Calm" | "Happy" | "Neutral" | ... (title-cased),
        "sentiment": float  # == valence, rounded to 2
        "valence": float    # [-1, 1]
        "arousal": float    # [0, 1]
      }
    """
    text = (text or "").strip()
    if not text:
        return {"label": "Neutral", "sentiment": 0.0, "valence": 0.0, "arousal": 0.0}

    # 1) Text → (valence, arousal, label)
    text_scores = analyze_text(text)  # {"valence": v, "arousal": a, "label": str}

    # 2) Fuse with optional prosody (rms/pitch/speech_rate), if provided
    fused = fuse(text_scores, prosody_state or {})

    v = float(fused.get("valence", 0.0))
    a = float(fused.get("arousal", 0.0))

    # 3) Neutral override (your rule)
    if abs(v) < NEUTRAL_VALENCE and a < NEUTRAL_AROUSAL:
        return {"label": "Neutral", "sentiment": 0.0, "valence": 0.0, "arousal": 0.0}

    # 4) Qualifier by magnitude of valence (keeps your UX idea)
    mag = abs(v)
    if mag >= 0.50:
        qualifier = "Very "
    elif 0.20 <= mag < 0.40:
        qualifier = "Slightly "
    else:
        qualifier = ""

    base_label = _titlecase(str(fused.get("label", "neutral")))
    label = f"{qualifier}{base_label}".strip()

    return {
        "label": label,
        "sentiment": round(v, 2),  # expose valence as "sentiment"
        "valence": round(v, 2),
        "arousal": round(a, 2),
    }
