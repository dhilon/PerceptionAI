from __future__ import annotations

from typing import Dict, List


POSITIVE_SET = {
    "Happy",
    "Excited",
    "Confident",
    "Satisfied",
    "Delighted",
    "Proud",
    "Relaxed",
    "Grateful",
    "Moved",
    "Calm",
    "Curious",
    "Empathetic",
}

NEGATIVE_SET = {
    "Sad",
    "Angry",
    "Nervous",
    "Scared",
    "Worried",
    "Upset",
    "Frustrated",
    "Depressed",
    "Embarrassed",
    "Disgusted",
    "Sarcastic",
}


def _choose_label_from_av(
    arousal01: float, valence01: float, candidates: List[str]
) -> str:
    """Pick a candidate label consistent with arousal/valence quadrant."""
    hi_a = arousal01 >= 0.6
    lo_a = arousal01 <= 0.4
    hi_v = valence01 >= 0.6
    lo_v = valence01 <= 0.4

    prefer: List[str] = []
    if hi_a and hi_v:
        prefer = ["Excited", "Happy", "Proud", "Confident", "Delighted"]
    elif hi_a and lo_v:
        prefer = ["Angry", "Frustrated", "Sarcastic"]
    elif lo_a and hi_v:
        prefer = ["Calm", "Relaxed", "Grateful", "Empathetic", "Moved"]
    elif lo_a and lo_v:
        prefer = ["Depressed", "Sad", "Worried", "Upset"]
    else:
        # Mid-arousal: steer by valence
        if lo_v:
            prefer = ["Sad", "Upset", "Frustrated", "Depressed"]
        elif hi_v:
            prefer = ["Happy", "Satisfied", "Proud", "Delighted"]
        else:
            prefer = ["Curious", "Surprised", "Calm"]

    for p in prefer:
        if p in candidates:
            return p
    # fallback to first candidate
    return candidates[0] if candidates else "indifferent"


def fuse_emotion(
    prosody_state: Dict | None,
    sentiment_result: Dict,
) -> Dict[str, float | str]:
    """
    Combine prosody arousal/valence (0..1) with text sentiment results to a 24-emotion label.
    sentiment_result: { 'scores': {emo:prob}, 'label': str, 'polarity': [-1,1] }
    Returns: { arousal, valence, label }
    """
    arousal = 0.5
    audio_valence = 0.5
    if prosody_state:
        arousal = float(prosody_state.get("arousal", 0.5))
        audio_valence = float(prosody_state.get("valence", 0.5))

    polarity = float(sentiment_result.get("polarity", 0.0))  # -1..1
    text_valence01 = (polarity + 1.0) / 2.0
    # Blend: text drives valence more; audio refines
    fused_valence01 = 0.65 * text_valence01 + 0.35 * audio_valence

    scores: Dict[str, float] = sentiment_result.get("scores", {}) or {}
    if not scores:
        # fabricate a neutral-ish distribution
        scores = {"Calm": 1.0}

    # rank candidates by model score then pick one consistent with AV
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    candidates = [lab for lab, _ in ranked[:6]]  # consider top-6

    # steer toward positive/negative family based on fused valence
    if fused_valence01 >= 0.55:
        candidates = [c for c in candidates if c in POSITIVE_SET] or candidates
    elif fused_valence01 <= 0.45:
        candidates = [c for c in candidates if c in NEGATIVE_SET] or candidates

    label = _choose_label_from_av(arousal, fused_valence01, candidates)
    return {"arousal": arousal, "valence": fused_valence01, "label": label}
