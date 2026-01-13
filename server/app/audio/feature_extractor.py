"""Audio feature extraction utilities."""

import opensmile
import numpy as np
from app.config import SAMPLE_RATE

# openSMILE config for prosody + energy + spectral + voice quality
smile = opensmile.Smile(
    feature_set=opensmile.FeatureSet.ComParE_2016,
    feature_level=opensmile.FeatureLevel.Functionals,
)


def extract_features(pcm16: np.ndarray):
    """
    pcm16: numpy array shape (N,)
    returns: dict of 30–60 acoustic features
    """
    pcm_float = pcm16.astype(np.float32) / 32768.0

    df = smile.process_signal(pcm_float, SAMPLE_RATE)
    row = df.iloc[0]

    return row.to_dict()
