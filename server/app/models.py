import os
from peewee import *
from datetime import datetime

db = PostgresqlDatabase(
    os.getenv("PG_DB", "empathai"),
    user=os.getenv("PG_USER", "postgres"),
    password=os.getenv("PG_PASS", "postgres"),
    host=os.getenv("PG_HOST", "127.0.0.1"),
    port=int(os.getenv("PG_PORT", "5432")),
)


class Base(Model):
    class Meta:
        database = db


class Session(Base):
    id = AutoField()
    created_at = DateTimeField(default=datetime.utcnow)
    title = CharField(null=True)
    participant = CharField(null=True)


class Utterance(Base):
    id = AutoField()
    session = ForeignKeyField(Session, backref="utterances")
    start_ms = IntegerField()
    end_ms = IntegerField()
    text = TextField()
    sentiment = FloatField(null=True)


class FrameEmotion(Base):
    id = AutoField()
    session = ForeignKeyField(Session, backref="frames")
    t_ms = IntegerField()
    pitch_hz = FloatField(null=True)
    energy_db = FloatField(null=True)
    speech_rate_wps = FloatField(null=True)
    arousal = FloatField(null=True)
    valence = FloatField(null=True)
    label = CharField(null=True)
