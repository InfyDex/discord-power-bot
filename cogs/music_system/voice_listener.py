"""
Discord voice-receive sink that transcribes speech and dispatches music commands.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Awaitable, Callable, Optional

import discord

# Support both py-cord (discord.sinks.Sink) and discord-ext-voice-receive (voice_recv.AudioSink)
_BaseSink = object
try:
    import discord.sinks
    _BaseSink = discord.sinks.Sink
except (ImportError, AttributeError):
    pass

try:
    import discord.ext.voice_recv as voice_recv
    _VRBase = voice_recv.AudioSink
except (ImportError, AttributeError):
    _VRBase = object

# Create combined base class for type compatibility
class _CombinedBaseSink(_BaseSink, _VRBase):  # type: ignore[misc]
    pass

from .nlp import ParsedCommand, parse_command
from .stt import STTBackend

logger = logging.getLogger("discord.music.voice_listener")

# ── Tuneable constants ───────────────────────────────────────────────────────

# Seconds of silence after which buffered audio is sent to the STT engine.
SILENCE_S: float = 1.2

# How often (seconds) the background task polls for silence.
CHECK_INTERVAL_S: float = 0.4

# Minimum PCM buffer size worth transcribing.
# 48 000 Hz × 2 ch × 2 bytes/sample × 0.5 s = 96 000 bytes
MIN_AUDIO_BYTES: int = 48_000 * 2 * 2 // 2  # 0.5 s

# Maximum PCM buffer size per user before flushing/truncating (~50 seconds of audio).
# Prevents memory leak/OOM if user never stops speaking.
MAX_BUFFER_BYTES: int = 48_000 * 2 * 2 * 50  # ~9.6 MB (~50 s)

# ── Type alias ───────────────────────────────────────────────────────────────

CommandCallback = Callable[[int, ParsedCommand], Awaitable[None]]


class MusicCommandSink(_CombinedBaseSink):
    """
    Custom Sink that buffers decoded PCM audio per-user, detects silence,
    transcribes the utterance, and dispatches music commands.
    """

    def __init__(
        self,
        stt: STTBackend,
        on_command: CommandCallback,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        super().__init__()
        self.stt = stt
        self.on_command = on_command
        self._loop = loop
        self._lock = threading.Lock()

        # Per-user PCM buffers keyed by user_id (int).
        self._buffers: dict[int, bytearray] = {}
        # Monotonic timestamp of the last audio frame received per user.
        self._last_audio: dict[int, float] = {}
        # Set of user_ids currently being transcribed (prevents double-dispatch).
        self._processing: set[int] = set()
        # Handle to the background silence-checker task.
        self._checker: Optional[asyncio.Task] = None
        logger.info("MusicCommandSink initialized.")

    def wants_opus(self) -> bool:
        """discord-ext-voice-receive interface: request decoded PCM (not Opus)."""
        return False

    # ── discord.py / py-cord / voice_recv Sink interface ─────────────────────

    def write(self, a=None, b=None) -> None:  # type: ignore[override]
        """Called (from audio-receive thread) for every 20 ms audio frame.
        
        Handles both write(data, user) [py-cord] and write(user, data) [voice_recv].
        """
        user = None
        data = None

        if isinstance(a, (discord.Member, discord.User)):
            user, data = a, b
        elif isinstance(b, (discord.Member, discord.User)):
            user, data = b, a
        elif hasattr(a, "pcm") or hasattr(a, "file") or hasattr(a, "data") or isinstance(a, (bytes, bytearray)):
            data, user = a, b
        else:
            user, data = b, a

        if user is None or data is None:
            return

        # Extract raw PCM bytes across various audio data formats
        pcm: Optional[bytes] = None
        if hasattr(data, "pcm") and data.pcm:
            pcm = bytes(data.pcm)
        elif hasattr(data, "file"):
            pcm = data.file.read()
            data.file.seek(0)
        elif hasattr(data, "data"):
            pcm = bytes(data.data)
        elif isinstance(data, (bytes, bytearray)):
            pcm = bytes(data)

        if not pcm:
            return

        uid = user.id
        with self._lock:
            if uid not in self._buffers:
                self._buffers[uid] = bytearray()
                logger.info("🎙️ [Voice Listener] Receiving audio packet from user %s (ID: %d)", getattr(user, 'display_name', user), uid)
            
            buf = self._buffers[uid]
            buf.extend(pcm)
            self._last_audio[uid] = time.monotonic()

            # Bound buffer size to prevent memory leaks from constant noise
            if len(buf) > MAX_BUFFER_BYTES:
                keep_bytes = 48_000 * 2 * 2 * 10
                self._buffers[uid] = bytearray(buf[-keep_bytes:])

    def cleanup(self) -> None:
        """Called automatically when recording/listening stops."""
        if self._checker and not self._checker.done():
            self._checker.cancel()
        with self._lock:
            self._buffers.clear()
            self._last_audio.clear()
            self._processing.clear()
        logger.info("MusicCommandSink cleaned up.")

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Schedule the background silence-checker coroutine on the event loop."""
        if self._checker is None or self._checker.done():
            self._checker = self._loop.create_task(self._silence_checker())
            logger.info("Voice command listener background loop started (silence threshold=%.1fs).", SILENCE_S)

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _silence_checker(self) -> None:
        """
        Runs every CHECK_INTERVAL_S seconds.
        Flushes each user's buffer when they've been silent long enough.
        """
        while True:
            try:
                await asyncio.sleep(CHECK_INTERVAL_S)
                now = time.monotonic()

                users_to_flush: list[tuple[int, bytes]] = []

                with self._lock:
                    for uid in list(self._last_audio):
                        if uid in self._processing:
                            continue
                        if now - self._last_audio[uid] < SILENCE_S:
                            continue

                        # User has been silent → grab their buffer.
                        pcm = bytes(self._buffers.pop(uid, b""))
                        del self._last_audio[uid]
                        users_to_flush.append((uid, pcm))

                for uid, pcm in users_to_flush:
                    if len(pcm) < MIN_AUDIO_BYTES:
                        logger.debug(
                            "🎙️ Audio from user %d too short (%d bytes) — discarding.",
                            uid, len(pcm),
                        )
                        continue

                    logger.info(
                        "🎙️ User %d was silent for ≥%.1fs — sending %d bytes of PCM to STT engine...",
                        uid, SILENCE_S, len(pcm)
                    )
                    with self._lock:
                        self._processing.add(uid)
                    self._loop.create_task(self._process(uid, pcm))

            except asyncio.CancelledError:
                logger.info("Voice silence checker stopped.")
                break
            except Exception:
                logger.exception("Unexpected error in voice silence checker.")

    async def _process(self, uid: int, pcm: bytes) -> None:
        """Transcribe a PCM buffer and dispatch any recognised command."""
        try:
            text = await self.stt.transcribe(pcm)
            logger.info("🎙️ [Voice STT Result] User %d said: %r", uid, text)
            if text:
                cmd = parse_command(text)
                if cmd:
                    logger.info(
                        "🎙️ [Voice Command Matched] User %d → command=%r args=%r",
                        uid, cmd.name, cmd.args
                    )
                    await self.on_command(uid, cmd)
                else:
                    logger.info("🎙️ [Voice Command No Match] Transcript did not match any music command: %r", text)
        except Exception:
            logger.exception("🎙️ [Voice Error] Error processing audio for user %d.", uid)
        finally:
            with self._lock:
                self._processing.discard(uid)


