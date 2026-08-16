"""
Speech-to-text (STT) backends for voice command recognition.

Set STT_BACKEND=local  (default) to use a local Whisper model — free, offline,
  requires `openai-whisper` and ffmpeg; model is downloaded on first use (~150 MB
  for "base", ~1 GB for "large").
Set STT_BACKEND=api and OPENAI_API_KEY=<key> to use the OpenAI Whisper cloud API —
  fast, no local GPU needed, ~$0.006 / minute.

Extra env vars:
  STT_WHISPER_MODEL  — Whisper model size: tiny | base | small | medium | large
                       (default: base).  Ignored for the API backend.
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
import tempfile
import wave
from typing import Protocol, runtime_checkable

logger = logging.getLogger("discord.music.stt")

# Discord voice audio is decoded to PCM with these specs.
_SAMPLE_RATE: int = 48_000
_CHANNELS: int = 2
_SAMPLE_WIDTH: int = 2  # 16-bit little-endian


@runtime_checkable
class STTBackend(Protocol):
    """Minimal interface that every STT backend must satisfy."""

    async def transcribe(self, pcm_bytes: bytes) -> str:
        """
        Convert raw 48 kHz stereo 16-bit PCM audio to a lowercase text string.
        Returns an empty string when nothing intelligible was detected.
        """
        ...


# ---------------------------------------------------------------------------
# Local Whisper
# ---------------------------------------------------------------------------

class WhisperLocalSTT:
    """
    Runs OpenAI Whisper locally in a thread-pool executor so the event loop
    stays responsive during transcription.

    The model is loaded lazily on the first call to ``transcribe``.
    """

    def __init__(self, model_size: str = "base") -> None:
        self._model_size = model_size
        self._model = None
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------

    def _load(self):
        if self._model is not None:
            return self._model
        try:
            import whisper  # type: ignore[import]
        except ImportError as exc:
            raise RuntimeError(
                "openai-whisper is not installed. "
                "Run: pip install openai-whisper"
            ) from exc
        logger.info(
            "Loading Whisper model '%s'… (first load may take a moment).",
            self._model_size,
        )
        self._model = whisper.load_model(self._model_size)
        logger.info("Whisper model '%s' ready.", self._model_size)
        return self._model

    def _transcribe_sync(self, pcm_bytes: bytes) -> str:
        model = self._load()
        # Create temp file name and close handle immediately so wave.open / whisper can write/read on Windows.
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as fh:
            tmp = fh.name
        try:
            with wave.open(tmp, "wb") as wf:
                wf.setnchannels(_CHANNELS)
                wf.setsampwidth(_SAMPLE_WIDTH)
                wf.setframerate(_SAMPLE_RATE)
                wf.writeframes(pcm_bytes)
            result = model.transcribe(tmp, language="en", fp16=False)
            return result["text"].strip().lower()
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    async def transcribe(self, pcm_bytes: bytes) -> str:
        loop = asyncio.get_running_loop()
        async with self._lock:  # one transcription at a time
            return await loop.run_in_executor(None, self._transcribe_sync, pcm_bytes)


# ---------------------------------------------------------------------------
# OpenAI Whisper API
# ---------------------------------------------------------------------------

class WhisperAPISTT:
    """Sends audio to the OpenAI Whisper cloud API for transcription."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import openai  # type: ignore[import]
            except ImportError as exc:
                raise RuntimeError(
                    "openai package not installed. Run: pip install openai"
                ) from exc
            self._client = openai.AsyncOpenAI(api_key=self._api_key)
        return self._client

    async def transcribe(self, pcm_bytes: bytes) -> str:
        client = self._get_client()

        # Convert raw PCM → WAV in memory (API expects a real audio file).
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(_CHANNELS)
            wf.setsampwidth(_SAMPLE_WIDTH)
            wf.setframerate(_SAMPLE_RATE)
            wf.writeframes(pcm_bytes)
        buf.seek(0)
        buf.name = "audio.wav"  # openai SDK uses the name to detect format

        resp = await client.audio.transcriptions.create(
            model="whisper-1",
            file=buf,
            language="en",
        )
        return resp.text.strip().lower()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_stt_backend() -> STTBackend:
    """
    Read STT_BACKEND (and related vars) from env and return the right backend.
    Falls back to local Whisper if the API key is missing when API is requested.
    """
    backend_env = os.getenv("STT_BACKEND", "local").strip().lower()

    if backend_env == "api":
        key = os.getenv("OPENAI_API_KEY", "").strip()
        if key:
            logger.info("STT: using OpenAI Whisper API backend.")
            return WhisperAPISTT(key)
        logger.warning(
            "STT_BACKEND=api but OPENAI_API_KEY is not set — "
            "falling back to local Whisper."
        )

    model_size = os.getenv("STT_WHISPER_MODEL", "base").strip()
    logger.info("STT: using local Whisper (model=%s).", model_size)
    return WhisperLocalSTT(model_size=model_size)
