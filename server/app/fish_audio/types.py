from typing import TypedDict, List, Literal, Optional

EventType = Literal["transcript.partial", "transcript.final", "error", "session.ready"]


class Word(TypedDict):
    start_ms: int
    end_ms: int
    text: str
    confidence: float


class TranscriptData(TypedDict):
    text: str
    words: List[Word]


class FishEvent(TypedDict):
    type: EventType
    data: TranscriptData | dict
