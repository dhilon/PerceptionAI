# simple placeholder; swap with your preferred model
from textblob import TextBlob


def get_sentiment(text: str) -> float:
    if not text.strip():
        return 0.0
    return float(TextBlob(text).sentiment.polarity)  # -1..1
