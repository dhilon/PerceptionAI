# server/app/analysis.py
from .nlp.sentiment import classify_emotions
from .nlp.fuse import fuse_emotion


def analyze_emotion(text: str, prosody_state: dict | None = None):
    text = (text or "").strip()
    if not text:
        return {"label": "Calm", "sentiment": 0.0}

    cls = classify_emotions(text)  # { scores, label, polarity }
    fused = fuse_emotion(prosody_state or {"arousal": 0.5, "valence": 0.5}, cls)
    polarity = float(cls["polarity"])  # -1..1

    # Intensity qualifiers based on magnitude (squeezed: extremes start ~0.5)
    mag = abs(polarity)
    if mag >= 0.5:
        qualifier = "Very"
    elif mag >= 0.2 and mag < 0.4:
        qualifier = "Slightly"
    else:
        qualifier = ""

    base_label = str(fused["label"]).strip()
    out_label = f"{qualifier} {base_label}".strip() if qualifier else base_label

    return {
        "label": out_label,
        "sentiment": float(round(polarity, 2)),
        "valence": float(round(fused.get("valence", 0.5), 2)),
        "arousal": float(round(fused.get("arousal", 0.5), 2)),
    }
