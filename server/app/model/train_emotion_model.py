"""Training script and helpers for the emotion recognition model."""

"""
Example training file.
Assumes you have a CSV:

audio_sample.wav, label

You can extend this however you want.
"""

import glob, numpy as np, pandas as pd, joblib
import soundfile as sf
from sklearn.ensemble import RandomForestClassifier

from app.audio.feature_extractor import extract_features
from app.config import MODEL_PATH


def load_dataset():
    rows = []
    for wav in glob.glob("dataset/*.wav"):
        label = wav.split("/")[-1].split("_")[0]  # e.g. happy_01.wav
        pcm, sr = sf.read(wav)
        pcm16 = (pcm * 32767).astype(np.int16)

        feats = extract_features(pcm16)
        feats["label"] = label
        rows.append(feats)

    return pd.DataFrame(rows)


def train():
    df = load_dataset()

    feature_cols = [c for c in df.columns if c != "label"]
    X = df[feature_cols].values
    y = df["label"].values

    clf = RandomForestClassifier(n_estimators=200)
    clf.fit(X, y)

    joblib.dump(
        {
            "clf": clf,
            "feature_order": feature_cols,
        },
        MODEL_PATH,
    )

    print("Model saved →", MODEL_PATH)


if __name__ == "__main__":
    train()
