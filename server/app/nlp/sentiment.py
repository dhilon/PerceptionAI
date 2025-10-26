# server/app/sentiment.py
"""
Text → (valence, arousal, label) aligned to the standard valence–arousal chart.

valence  ∈ [-1.0, 1.0]  (unpleasant → pleasant)
arousal  ∈ [ 0.0, 1.0 ] (low → high)

Neutral rule: if abs(valence) < NEUTRAL_V and arousal < NEUTRAL_A → label 'neutral'
"""

from __future__ import annotations
import math
import re
from typing import Dict, Tuple, List, Optional

# Optional dependency: textblob for polarity (valence). Falls back if missing.
try:
    from textblob import TextBlob  # polarity ∈ [-1, 1]
except Exception:  # pragma: no cover
    TextBlob = None  # type: ignore

# ---------------------------
# Tunables
# ---------------------------
NEUTRAL_V = 0.10  # |valence| below this → near neutral
NEUTRAL_A = 0.10  # arousal below this → near neutral
POLARITY_WEIGHT = 0.55  # how much TextBlob polarity affects valence
LEXICON_WEIGHT = 0.45  # how much our lexicon affects valence/arousal
INTENSITY_WEIGHT = 0.30  # extra arousal from punctuation/intensifiers (capped)
MAX_BONUS_AROUSAL = 0.35

# ---------------------------
# Lexicon (from your chart + list)
# Values are (valence [-1..1], arousal [0..1])
# ---------------------------
LEXICON: Dict[str, Tuple[float, float]] = {
    # high arousal, positive valence
    "astonished": (0.6, 0.95),
    "excited": (0.8, 0.90),
    "aroused": (0.6, 0.85),
    "delighted": (0.85, 0.75),
    "glad": (0.75, 0.60),
    "pleased": (0.75, 0.55),
    "happy": (0.85, 0.70),
    "satisfied": (0.70, 0.45),
    "content": (0.65, 0.35),
    # low arousal, positive valence
    "serene": (0.75, 0.20),
    "calm": (0.65, 0.20),
    "relaxed": (0.70, 0.25),
    # low arousal, negative valence
    "tired": (-0.40, 0.15),
    "sleepy": (-0.20, 0.10),
    "droopy": (-0.45, 0.10),
    "bored": (-0.55, 0.10),
    "gloomy": (-0.65, 0.20),
    "depressed": (-0.85, 0.25),
    "miserable": (-0.90, 0.35),
    "sad": (-0.70, 0.30),
    # high arousal, negative valence
    "afraid": (-0.80, 0.90),
    "alarmed": (-0.75, 0.90),
    "angry": (-0.85, 0.85),
    "frustrated": (-0.75, 0.75),
    "annoyed": (-0.55, 0.65),
    "distressed": (-0.80, 0.65),
    # extra labels from your long list
    "worried": (-0.55, 0.65),
    "upset": (-0.60, 0.60),
    "scared": (-0.80, 0.85),
    "embarrassed": (-0.50, 0.55),
    "nervous": (-0.35, 0.70),
    "confident": (0.55, 0.60),
    "surprised": (0.40, 0.85),
    "satisfied": (0.70, 0.45),
    "delighted": (0.85, 0.75),
    "calm": (0.65, 0.20),
    "relaxed": (0.70, 0.25),
    "depressed": (-0.85, 0.25),
    "frustrated": (-0.75, 0.75),
    "disgusted": (-0.85, 0.80),
    "moved": (0.45, 0.55),
    "proud": (0.70, 0.60),
    "grateful": (0.75, 0.45),
    "curious": (0.25, 0.55),
    "sarcastic": (-0.20, 0.45),  # tricky; leave moderate arousal
}

LEXICON["thrilled"] = (0.9, 0.9)
LEXICON["anxious"] = (-0.6, 0.8)

# Prototype centroids to map (valence, arousal) → a discrete label
PROTOTYPES: Dict[str, Tuple[float, float]] = {
    "happy": (0.85, 0.70),
    "excited": (0.80, 0.90),
    "calm": (0.65, 0.20),
    "content": (0.65, 0.35),
    "relaxed": (0.70, 0.25),
    "sad": (-0.70, 0.30),
    "depressed": (-0.85, 0.25),
    "angry": (-0.85, 0.85),
    "frustrated": (-0.75, 0.75),
    "afraid": (-0.80, 0.90),
    "surprised": (0.40, 0.85),
    "worried": (-0.55, 0.65),
    "proud": (0.70, 0.60),
    "grateful": (0.75, 0.45),
    "neutral": (0.00, 0.05),
}

INTENSIFIERS = {
    "very",
    "really",
    "extremely",
    "super",
    "so",
    "incredibly",
    "absolutely",
    "totally",
}
NEGATORS = {"not", "never", "no", "hardly", "barely", "scarcely"}

WORD_RE = re.compile(r"[A-Za-z']+")


def _normalize_valence(v: float) -> float:
    return max(-1.0, min(1.0, v))


def _normalize_arousal(a: float) -> float:
    return max(0.0, min(1.0, a))


def _polarity(text: str) -> float:
    if TextBlob is None:
        return 0.0
    try:
        return float(TextBlob(text).sentiment.polarity)  # [-1..1]
    except Exception:
        return 0.0


def _intensity_bonus(text: str) -> float:
    # + arousal for !!!, ALL CAPS tokens, many exclamation marks, intensifiers
    exclam = text.count("!")
    exclam_bonus = min(exclam / 6.0, 1.0) * 0.25  # ≤ 0.25

    caps_tokens = sum(1 for w in WORD_RE.findall(text) if len(w) >= 3 and w.isupper())
    caps_bonus = min(caps_tokens / 6.0, 1.0) * 0.20  # ≤ 0.20

    words = [w.lower() for w in WORD_RE.findall(text)]
    intens = sum(1 for w in words if w in INTENSIFIERS)
    intens_bonus = min(intens / 3.0, 1.0) * 0.25  # ≤ 0.25

    bonus = exclam_bonus + caps_bonus + intens_bonus
    return min(bonus, MAX_BONUS_AROUSAL)


def _lexicon_scores(text: str) -> Tuple[Optional[float], Optional[float]]:
    words = [w.lower() for w in WORD_RE.findall(text)]
    vals: List[float] = []
    aros: List[float] = []

    flip = 1.0
    for i, w in enumerate(words):
        # Simple negation scope (last 3 words flips sentiment)
        if w in NEGATORS:
            flip = -1.0
            continue
        if w in LEXICON:
            v, a = LEXICON[w]
            vals.append(flip * v)
            aros.append(a)
            flip = 1.0  # reset after application
        else:
            flip = 1.0

    if not vals and not aros:
        return None, None
    v = sum(vals) / len(vals) if vals else None
    a = sum(aros) / len(aros) if aros else None
    return v, a


def _closest_label(v: float, a: float) -> str:
    best, best_d = "neutral", float("inf")
    for label, (pv, pa) in PROTOTYPES.items():
        d = math.hypot(v - pv, a - pa)
        if d < best_d:
            best, best_d = label, d
    return best


def analyze_text(text: str) -> Dict[str, float | str]:
    """
    Returns:
      {
        "valence": float ∈ [-1, 1],
        "arousal": float ∈ [0, 1],
        "label":   str
      }
    """
    text = (text or "").strip()
    if not text:
        return {"valence": 0.0, "arousal": 0.0, "label": "neutral"}

    # 1) Polarity (valence)
    pol = _polarity(text)

    # 2) Lexicon match
    lex_v, lex_a = _lexicon_scores(text)

    # 3) Intensity → arousal bonus
    ar_bonus = _intensity_bonus(text)

    # 4) Blend
    if lex_v is None:
        v = pol
    else:
        v = POLARITY_WEIGHT * pol + LEXICON_WEIGHT * lex_v

    if lex_a is None:
        a = 0.35 + ar_bonus  # base mid arousal + intensity if no lexicon
    else:
        a = (1 - INTENSITY_WEIGHT) * lex_a + INTENSITY_WEIGHT * (lex_a + ar_bonus)

    v = _normalize_valence(v)
    a = _normalize_arousal(a)

    # 5) Neutral rule
    if abs(v) < NEUTRAL_V and a < NEUTRAL_A:
        return {"valence": 0.0, "arousal": 0.0, "label": "neutral"}

    label = _closest_label(v, a)
    return {"valence": v, "arousal": a, "label": label}
