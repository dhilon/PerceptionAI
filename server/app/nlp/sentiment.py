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

    # choose best label
    best = max(scores.items(), key=lambda kv: kv[1])[0]
    return {"scores": scores, "label": best, "polarity": polarity}
