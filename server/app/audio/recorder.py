import sounddevice as sd
import numpy as np
from app.config import SAMPLE_RATE, FRAME_SIZE


class LiveMicRecorder:
    def __init__(self):
        self.sample_rate = SAMPLE_RATE
        self.frame_samples = int(SAMPLE_RATE * FRAME_SIZE)

    def stream(self):
        """A blocking generator that yields PCM16 frames."""
        with sd.InputStream(
            channels=1,
            samplerate=self.sample_rate,
            dtype="int16",
        ) as stream:
            while True:
                frame, _ = stream.read(self.frame_samples)
                yield frame.copy().astype(np.int16)
