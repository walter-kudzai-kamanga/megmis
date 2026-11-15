"""Mock speech provider for unit tests and offline Gen 3 demos."""

from __future__ import annotations

import io
import wave
from typing import Any


def _silent_wav(duration_s: float = 0.4, rate: int = 16000) -> bytes:
    n = int(rate * duration_s)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * n)
    return buf.getvalue()


class MockSpeechProvider:
    name = "mock-speech"

    def stt(self, audio_bytes: bytes, lang: str = "en", *, mime: str = "audio/wav") -> dict[str, Any]:
        # Deterministic stub — NOT Mutare-only. Interactive demos use Bulawayo→Gweru.
        samples = {
            "en": "Fastest route from Bulawayo to Gweru",
            "sn": "Nzira kubva kuHarare kuenda kuBulawayo",
            "nd": "Indlela ukusuka eHarare ukuya eBulawayo",
        }
        return {
            "text": samples.get(lang, samples["en"]),
            "lang": lang,
            "confidence": 0.91,
            "provider": self.name,
            "duration_ms": max(200, len(audio_bytes) // 32),
        }

    def tts(self, text: str, lang: str = "en", voice: str | None = None) -> dict[str, Any]:
        return {
            "audio_bytes": _silent_wav(0.5 + min(2.0, len(text) / 80)),
            "mime": "audio/wav",
            "lang": lang,
            "provider": self.name,
            "voice": voice or f"mock-{lang}",
            "text": text,
        }
