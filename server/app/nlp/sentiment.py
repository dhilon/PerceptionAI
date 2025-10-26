# server/app/nlp/sentiment.py
"""
Audio-only valence–arousal estimation + nearest-emotion labeling.

Inputs (per utterance or rolling window):
  prosody = {
    "rms":        float in [0..1],   # normalized loudness
    "rms_std":    float in [0..1],   # loudness variability within the window
    "speech_rate":float in [0..1],   # optional: relative words/sec (0=slow,1=fast)
  }

Outputs:
  { "valence": [-1..1], "arousal": [0..1], "label": str }
"""

from __future__ import annotations
from typing import Dict, Tuple
import math
from .gain import (
    AROUSAL_GAIN,
    VALENCE_GAIN,
    AROUSAL_CONTRAST,
    VALENCE_CONTRAST,
    NEUTRAL_V,
    NEUTRAL_A,
)

# ---------- thresholds ----------
NEUTRAL_V = 0.05
NEUTRAL_A = 0.05


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


# Prototypes (valence, arousal) roughly from your chart
PROTOTYPES: Dict[str, Tuple[float, float]] = {
    "excited": (0.80, 0.90),
    "happy": (0.85, 0.70),
    "content": (0.65, 0.35),
    "calm": (0.65, 0.20),
    "relaxed": (0.70, 0.25),
    "surprised": (0.40, 0.85),
    "worried": (-0.55, 0.65),
    "afraid": (-0.80, 0.90),
    "angry": (-0.85, 0.85),
    "frustrated": (-0.75, 0.75),
    "sad": (-0.70, 0.30),
    "depressed": (-0.85, 0.25),
    "bored": (-0.55, 0.10),
    "neutral": (0.00, 0.05),
}


def _nearest_label(v: float, a: float) -> str:
    best, best_d = "neutral", float("inf")
    for lbl, (pv, pa) in PROTOTYPES.items():
        d = math.hypot(v - pv, a - pa)
        if d < best_d:
            best, best_d = lbl, d
    return best


def _contrast01(x: float, k: float) -> float:
    # same logistic contrast helper as above, local copy
    x = max(0.0, min(1.0, x))
    y = 1.0 / (1.0 + math.exp(-k * (x - 0.5)))
    y0 = 1.0 / (1.0 + math.exp(-k * (-0.5)))
    y1 = 1.0 / (1.0 + math.exp(-k * (0.5)))
    return max(0.0, min(1.0, (y - y0) / (y1 - y0)))


def analyze_audio(prosody: Dict[str, float]) -> Dict[str, float | str]:
    """
    Higher negative sensitivity using volatility (rms_std), zcr, and crest.
    """
    rms = _clamp(float(prosody.get("rms", 0.0)), 0.0, 1.0)
    var = _clamp(float(prosody.get("rms_std", 0.0)), 0.0, 1.0)
    rate = _clamp(float(prosody.get("speech_rate", 0.0)), 0.0, 1.0)
    zcr = _clamp(float(prosody.get("zcr", 0.0)), 0.0, 1.0)
    crest = _clamp(float(prosody.get("crest", 0.0)), 0.0, 1.0)

    # ---------- AROUSAL ----------
    rms_gamma = rms**0.55
    var_gamma = var**0.85
    zcr_gain = 0.12 * zcr
    base_a = 0.75 * rms_gamma + 0.28 * var_gamma + 0.10 * rate + zcr_gain
    a = _contrast01(base_a, AROUSAL_CONTRAST)
    arousal = max(0.0, min(1.0, a * AROUSAL_GAIN))

    # ---------- VALENCE ----------
    steady = 1.0 - var
    midness = 1.0 - min(1.0, abs(arousal - 0.5) / 0.5)
    hi_energy = max(0.0, arousal - 0.60)
    med_energy = max(0.0, arousal - 0.35) * (1.0 - hi_energy)  # mid band only
    low_energy = max(0.0, 0.22 - arousal)
    quiet = max(0.0, 0.12 - rms)

    # Positive terms (unchanged-ish)
    pos = 0.60 * steady * midness + 0.40 * steady * hi_energy

    # Negative terms (stronger & earlier)
    neg_hi = 1.05 * var * hi_energy + 0.70 * zcr * hi_energy + 0.55 * crest * hi_energy
    neg_med = (
        0.55 * (0.6 * zcr + 0.4 * var) * med_energy
    )  # negative tension already in mid band
    neg_low = 0.50 * quiet * low_energy  # sad/bored for very low
    neg = neg_hi + neg_med + neg_low

    raw_v = pos - 1.20 * neg  # <-- asymmetry: negatives weigh more
    v = math.tanh(1.7 * raw_v)  # more contrast
    v01 = (v + 1.0) * 0.5
    v01 = _contrast01(v01, VALENCE_CONTRAST)
    v = (v01 * 2.0) - 1.0
    v = max(-1.0, min(1.0, v))

    if abs(v) < NEUTRAL_V and arousal < NEUTRAL_A:
        return {"valence": 0.0, "arousal": 0.0, "label": "neutral"}

    label = _nearest_label(v, arousal)
    return {"valence": v, "arousal": arousal, "label": label}
