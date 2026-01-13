"""Model definitions and loading utilities for emotion recognition."""

import joblib
import numpy as np
from app.config import MODEL_PATH


class EmotionModel:
    def __init__(self):
        self.model = None
        self.load_error = None
        try:
            self.model = joblib.load(MODEL_PATH)
        except (FileNotFoundError, EOFError, ValueError) as e:
            self.load_error = f"Failed to load model from {MODEL_PATH}: {e}"
        except Exception as e:
            self.load_error = f"Unexpected error loading model from {MODEL_PATH}: {e}"

    def is_ready(self) -> bool:
        return self.model is not None

    def predict(self, features: dict):
        if not self.is_ready():
            raise RuntimeError(self.load_error or "Model not loaded")
        keys = self.model["feature_order"]
        vec = np.array([features.get(k, 0.0) for k in keys], dtype=float)
        proba = self.model["clf"].predict_proba([vec])[0]
        label = self.model["clf"].classes_[np.argmax(proba)]
        return {"label": label, "proba": proba.tolist()}
