def fuse_scores(prosody_state: dict, sentiment: float | None) -> dict:
    """
    Combine prosody-derived arousal/valence with text sentiment for a simple tone score.
    """
    arousal = prosody_state.get("arousal", 0.5)
    audio_valence = prosody_state.get("valence", 0.5)
    if sentiment is None:
        sentiment = 0.0
    fused_valence = 0.6 * sentiment + 0.4 * (
        audio_valence * 2 - 1
    )  # audio_valence (0..1) -> (-1..1)
    label = label_from_av(arousal, (fused_valence + 1) / 2)
    return {"arousal": arousal, "valence": (fused_valence + 1) / 2, "label": label}


def label_from_av(arousal: float, valence01: float) -> str:
    if arousal > 0.7 and valence01 > 0.6:
        return "excited"
    if arousal < 0.3 and valence01 > 0.6:
        return "calm"
    if arousal > 0.7 and valence01 < 0.4:
        return "frustrated"
    if arousal < 0.3 and valence01 < 0.4:
        return "sad"
    return "neutral"
