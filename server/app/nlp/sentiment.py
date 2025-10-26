# simple placeholder; swap with your preferred model
from __future__ import annotations

from typing import Dict, List

from textblob import TextBlob

from app.nlp.fuse import POSITIVE_SET, NEGATIVE_SET


# Canonical 24-label space
EMOTIONS: List[str] = [
    "Happy",
    "Sad",
    "Angry",
    "Excited",
    "Calm",
    "Nervous",
    "Confident",
    "Surprised",
    "Satisfied",
    "Delighted",
    "Scared",
    "Worried",
    "Upset",
    "Frustrated",
    "Depressed",
    "Empathetic",
    "Embarrassed",
    "Disgusted",
    "Moved",
    "Proud",
    "Relaxed",
    "Grateful",
    "Curious",
    "Sarcastic",
]


def get_sentiment(text: str) -> float:
    """Backward-compatible polarity in [-1, 1]."""
    text = (text or "").strip()
    if not text:
        return 0.0
    return float(TextBlob(text).sentiment.polarity)


def classify_emotions(text: str) -> Dict[str, object]:
    """
    Polarity-only heuristic across 24 emotions (no lexicon/negators).
    - Distribute positive mass across POS_SET
    - Distribute negative mass across NEG_SET
    - Residual (near-neutral) mass to 'Calm'
    """
    text = (text or "").strip()
    if not text:
        return {
            "scores": {e: 0.0 for e in EMOTIONS},
            "label": "Calm",
            "polarity": 0.0,
        }

    polarity = float(TextBlob(text).sentiment.polarity)

    # Lightweight text signals to capture complex tones (nervousness, surprise, sarcasm)
    lowered = text.lower()
    exclaim = text.count("!")
    qmarks = text.count("?")
    ellipses = lowered.count("...")
    all_caps_tokens = sum(1 for t in text.split() if len(t) >= 2 and t.isupper())
    hedges = sum(
        1
        for w in ["uh", "um", "er", "like", "kinda", "sorta"]
        if f" {w} " in f" {lowered} "
    )
    worry_words = [
        "nervous",
        "anxious",
        "worried",
        "on edge",
        "panic",
        "scared",
        "afraid",
    ]
    nervous_hits = sum(1 for w in worry_words if w in lowered)
    sarcasm_markers = [
        "yeah right",
        "sure",
        "as if",
        "/s",
        "totally",
        "great...",
        "nice...",
    ]
    sarcasm_hits = sum(1 for w in sarcasm_markers if w in lowered)
    surprise_hits = qmarks + (1 if "wow" in lowered or "whoa" in lowered else 0)

    # Estimate text arousal 0..1 from punctuation and emphasis
    ta = 0.0
    ta += min(1.0, exclaim * 0.25)
    ta += min(1.0, qmarks * 0.15)
    ta += min(1.0, all_caps_tokens * 0.15)
    ta += min(1.0, max(0, 0.2 * (len(text) / 140.0)))  # slight scale with length
    text_arousal01 = max(0.0, min(1.0, 0.25 + 0.25 * ta))
    pos_w = max(0.0, polarity)
    neg_w = max(0.0, -polarity)
    neu_w = max(0.0, 1.0 - (pos_w + neg_w))

    # Allocate most neutral mass toward the polarity side so moderate values still pick a side
    side_bonus = 0.8 * neu_w
    indifferent_bonus = 0.2 * neu_w

    scores: Dict[str, float] = {e: 0.0 for e in EMOTIONS}

    if polarity > 0 and POSITIVE_SET:
        side_mass = pos_w + side_bonus
        # Give a lead share to a canonical positive label to avoid dilution
        lead = "Happy"
        lead_share = 0.6 * side_mass
        rest_mass = max(0.0, side_mass - lead_share)
        per_rest = (
            (rest_mass / (len(POSITIVE_SET) - 1)) if len(POSITIVE_SET) > 1 else 0.0
        )
        for e in POSITIVE_SET:
            scores[e] += lead_share if e == lead else per_rest
        scores["Calm"] += indifferent_bonus
    elif polarity < 0 and NEGATIVE_SET:
        side_mass = neg_w + side_bonus
        # Give a lead share to a canonical negative/low-arousal label
        lead = "Depressed" if polarity <= -0.6 else "Sad"
        if lead not in NEGATIVE_SET:
            # fallback if taxonomy changes
            lead = next(iter(NEGATIVE_SET))
        lead_share = 0.6 * side_mass
        rest_mass = max(0.0, side_mass - lead_share)
        per_rest = (
            (rest_mass / (len(NEGATIVE_SET) - 1)) if len(NEGATIVE_SET) > 1 else 0.0
        )
        for e in NEGATIVE_SET:
            scores[e] += lead_share if e == lead else per_rest
        scores["Calm"] += indifferent_bonus
    else:
        # near-zero polarity → neutral
        scores["Calm"] = 1.0

    # Bias toward complex tones based on signals (without full lexicon)
    if nervous_hits + hedges + surprise_hits > 0:
        # Encourage Nervous/Worried/Scared when uncertainty cues present
        bias = 0.15 + 0.05 * (nervous_hits + hedges)
        for lab in ("Nervous", "Worried", "Scared"):
            if lab in scores:
                scores[lab] = min(1.0, scores[lab] + bias)
    if sarcasm_hits > 0:
        scores["Sarcastic"] = min(
            1.0, scores.get("Sarcastic", 0.0) + 0.2 * sarcasm_hits
        )

    # choose best label
    best = max(scores.items(), key=lambda kv: kv[1])[0]
    return {
        "scores": scores,
        "label": best,
        "polarity": polarity,
        "arousal": float(text_arousal01),
        "signals": {
            "nervousHits": int(nervous_hits + hedges),
            "surpriseHits": int(surprise_hits),
            "sarcasmHits": int(sarcasm_hits),
            "exclaim": int(exclaim),
            "qmarks": int(qmarks),
        },
    }
