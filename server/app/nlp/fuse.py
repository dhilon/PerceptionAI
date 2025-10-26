# server/app/nlp/fuse.py
"""
Temporal smoothing for audio-only valence–arousal (VA).

- Uses EMA smoothing with configurable alphas.
- Optional short peak-hold so brief spikes survive smoothing.
- ALWAYS labels via nearest-centroid from sentiment.PROTOTYPES (no coarse fallback).
- Keeps full-precision state; do NOT round before storing state.

Usage:
    state = None
    out = fuse(current_va, state)         # current_va = {"valence": v, "arousal": a}
    state = out["state"]                  # keep for next call
"""

from __future__ import annotations
from typing import Dict, Optional
import time

# If you externalized neutral gates in gain.py, import them; otherwise define here.
try:
    from .gain import NEUTRAL_V, NEUTRAL_A
except Exception:
    NEUTRAL_V, NEUTRAL_A = 0.06, 0.06


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def _ema(prev: float, new: float, alpha: float) -> float:
    # alpha in (0,1]; higher alpha -> faster response
    return alpha * new + (1.0 - alpha) * prev


def fuse(
    current: Dict[str, float],
    state: Optional[Dict[str, float]] = None,
    *,
    alpha_valence: float = 0.75,  # faster by default (was 0.35–0.55 earlier)
    alpha_arousal: float = 0.80,
    peak_hold_ms: int = 600,  # keep recent peaks for ~0.6s
    peak_decay: float = 0.95,  # slight decay while holding (0..1]
    valence_peak_boost: float = 0.00,  # let valence peaks hold a bit too
) -> Dict[str, float | str | Dict[str, float]]:
    """
    Params:
      - alpha_valence / alpha_arousal: EMA smoothing factors.
      - peak_hold_ms: duration to keep the last peak from collapsing immediately.
      - peak_decay: multiplier applied to held arousal peak when taking max(ema, held).
      - valence_peak_boost: similar light hold for valence peaks.

    Returns:
      {
        "valence": float in [-1, 1],
        "arousal": float in [0, 1],
        "label": str,                      # nearest centroid
        "state": { "valence": v_s, "arousal": a_s, "pv":..., "pa":..., "pt":... }
      }
    """
    v_new = float(current.get("valence", 0.0))
    a_new = float(current.get("arousal", 0.0))
    now = time.time()

    # Initialize or recover running state
    if not state:
        v_s = _clamp(v_new, -1.0, 1.0)
        a_s = _clamp(a_new, 0.0, 1.0)
        # track last peaks and their timestamp
        pv, pa, pt = v_new, a_new, now
        state = {"valence": v_s, "arousal": a_s, "pv": pv, "pa": pa, "pt": pt}
    else:
        v_prev = float(state.get("valence", v_new))
        a_prev = float(state.get("arousal", a_new))
        v_s = _ema(v_prev, v_new, alpha_valence)
        a_s = _ema(a_prev, a_new, alpha_arousal)

        # Peak-hold logic
        pv = float(state.get("pv", v_new))
        pa = float(state.get("pa", a_new))
        pt = float(state.get("pt", now))
        hold = max(0.0, peak_hold_ms) / 1000.0

        # Update peaks or expire hold window
        if a_new > pa or (now - pt) > hold:
            pa, pt = a_new, now
        if v_new > pv or (now - pt) > hold:
            pv = v_new  # reuse same timer for simplicity

        # Apply soft peak hold (use max of EMA and slightly-decayed peak)
        a_s = max(a_s, pa * peak_decay)
        # v_s = max(v_s, pv * valence_peak_boost)

        # Clamp
        v_s = _clamp(v_s, -1.0, 1.0)
        a_s = _clamp(a_s, 0.0, 1.0)

        # Persist state
        state.update({"pv": pv, "pa": pa, "pt": pt})

    # Neutral override (use smoothed values)
    if abs(v_s) < NEUTRAL_V and a_s < NEUTRAL_A:
        label = "neutral"
        v_out, a_out = 0.0, 0.0
    else:
        # Always label via nearest centroid in VA space
        from .sentiment import _nearest_label  # uses PROTOTYPES defined there

        label = _nearest_label(v_s, a_s)
        v_out, a_out = v_s, a_s

    # Store final smoothed values back in state (full precision; NO rounding)
    state.update({"valence": v_s, "arousal": a_s})

    return {
        "valence": v_out,
        "arousal": a_out,
        "label": label,
        "state": state,
    }
