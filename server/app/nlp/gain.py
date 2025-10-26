# server/app/nlp/gain.py
import os


def _f(name, default):
    try:
        return float(os.getenv(name, default))
    except Exception:
        return float(default)


# Overall gains (turn these up first)
AROUSAL_GAIN = _f("VA_AROUSAL_GAIN", 1.35)  # 1.0 = baseline, 1.35 = hotter
VALENCE_GAIN = _f("VA_VALENCE_GAIN", 1.60)  # multiplier inside tanh

# Extra contrast (push mids toward extremes)
AROUSAL_CONTRAST = _f("VA_AROUSAL_CONTRAST", 1.25)  # >1 increases contrast
VALENCE_CONTRAST = _f("VA_VALENCE_CONTRAST", 1.25)

# Make neutral rarer (optional)
NEUTRAL_V = _f("VA_NEUTRAL_V", 0.06)  # was 0.10
NEUTRAL_A = _f("VA_NEUTRAL_A", 0.06)  # was 0.10

SAD_WEIGHT = _f("VA_SAD_WEIGHT", 0.85)
