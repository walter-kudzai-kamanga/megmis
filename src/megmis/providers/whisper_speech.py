"""Whisper STT (faster-whisper) + edge-tts TTS adapter."""

from __future__ import annotations

import asyncio
import io
import logging
import tempfile
from pathlib import Path
from typing import Any

from megmis.common.errors import ProviderError
from megmis.config import get_settings

log = logging.getLogger("megmis.speech.whisper")

# Whisper language codes; sn/nd fall back to multilingual auto + post-hints
_WHISPER_LANG = {"en": "en", "sn": None, "nd": None}

# Edge TTS voices — EN primary; sn/nd use closest available + localized phrase bank upstream
_EDGE_VOICES = {
    "en": "en-ZA-LukeNeural",
    "sn": "en-ZA-LeahNeural",  # no native sn neural yet — localized text still spoken
    "nd": "en-ZA-LukeNeural",
}


class WhisperSpeechProvider:
    """Concrete Gen 3 SpeechProvider using OpenAI Whisper via faster-whisper."""

    name = "whisper"

    def __init__(self) -> None:
        self._model = None
        settings = get_settings()
        self.model_size = settings.whisper_model
        self.device = settings.whisper_device
        self.compute_type = settings.whisper_compute_type

    def _load(self):
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise ProviderError(
                "faster-whisper not installed; pip install -e '.[voice]'",
                retryable=False,
                code="SPEECH_DEP_MISSING",
            ) from exc
        log.info("loading whisper model=%s device=%s", self.model_size, self.device)
        self._model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
        )
        return self._model

    def stt(self, audio_bytes: bytes, lang: str = "en", *, mime: str = "audio/wav") -> dict[str, Any]:
        if not audio_bytes:
            raise ProviderError("empty audio", retryable=False, code="EMPTY_AUDIO")
        model = self._load()
        suffix = ".webm" if "webm" in mime else ".ogg" if "ogg" in mime else ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            path = tmp.name
        try:
            whisper_lang = _WHISPER_LANG.get(lang, "en")
            segments, info = model.transcribe(
                path,
                language=whisper_lang,
                beam_size=3,
                vad_filter=True,
            )
            parts = [s.text.strip() for s in segments if s.text.strip()]
            text = " ".join(parts).strip()
            return {
                "text": text,
                "lang": lang,
                "detected_lang": getattr(info, "language", lang),
                "confidence": float(getattr(info, "language_probability", 0.8) or 0.8),
                "provider": self.name,
                "model": self.model_size,
                "duration_ms": int((getattr(info, "duration", 0) or 0) * 1000),
            }
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(str(exc), retryable=True, code="STT_FAILED") from exc
        finally:
            Path(path).unlink(missing_ok=True)

    def tts(self, text: str, lang: str = "en", voice: str | None = None) -> dict[str, Any]:
        settings = get_settings()
        if settings.tts_provider == "mock":
            from megmis.providers.mock_speech import MockSpeechProvider

            return MockSpeechProvider().tts(text, lang, voice)

        voice_id = voice or _EDGE_VOICES.get(lang, _EDGE_VOICES["en"])
        try:
            import edge_tts
        except ImportError as exc:
            raise ProviderError(
                "edge-tts not installed; pip install -e '.[voice]'",
                retryable=False,
                code="SPEECH_DEP_MISSING",
            ) from exc

        def _synth_sync() -> bytes:
            async def _synth() -> bytes:
                communicate = edge_tts.Communicate(text, voice_id)
                buf = io.BytesIO()
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        buf.write(chunk["data"])
                return buf.getvalue()

            try:
                asyncio.get_running_loop()
            except RuntimeError:
                return asyncio.run(_synth())
            # Inside FastAPI event loop — run a fresh loop in a worker thread
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(lambda: asyncio.run(_synth())).result(timeout=60)

        try:
            audio = _synth_sync()
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(str(exc), retryable=True, code="TTS_FAILED") from exc

        if not audio:
            raise ProviderError("tts produced empty audio", retryable=True, code="TTS_EMPTY")
        return {
            "audio_bytes": audio,
            "mime": "audio/mpeg",
            "lang": lang,
            "provider": "edge-tts",
            "voice": voice_id,
            "text": text,
        }
