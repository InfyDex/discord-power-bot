"""
Discord voice-receive sink that transcribes speech and dispatches music commands.

How it works
------------
1. ``MusicCommandSink.write()`` is called by discord.py for every 20-ms Opus
   frame it decodes from the voice channel — one per speaking user.
2. Audio is buffered per-user in memory.
3. A background asyncio task (``_silence_checker``) polls every 400 ms.
   When a user has been silent for ≥ ``SILENCE_S`` seconds **and** their buffer
   is long enough, the buffer is flushed and passed to the STT backend.
4. The transcript is forwarded to ``nlp.parse_command``.
5. If a command is found, ``on_command(user_id, ParsedCommand)`` is awaited.

Usage (inside the Music cog)
-----------------------------
    sink = MusicCommandSink(stt_backend, command_handler, bot.loop)
    voice_client.start_recording(sink, after_callback)
    sink.start()               # begins the silence-checker task
    ...
    voice_client.stop_recording()   # calls sink.cleanup() automatically
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Awaitable, Callable, Optional

import discord
import discord.sinks

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

# ── Type alias ───────────────────────────────────────────────────────────────

CommandCallback = Callable[[int, ParsedCommand], Awaitable[None]]


class MusicCommandSink(discord.sinks.Sink):
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

        # Per-user PCM buffers keyed by user_id (int).
        self._buffers: dict[int, bytearray] = {}
        # Monotonic timestamp of the last audio frame received per user.
        self._last_audio: dict[int, float] = {}
        # Set of user_ids currently being transcribed (prevents double-dispatch).
        self._processing: set[int] = set()
        # Handle to the background silence-checker task.
        self._checker: Optional[asyncio.Task] = None

    # ── discord.py Sink interface ─────────────────────────────────────────────

    def write(self, data, user: Optional[discord.Member]) -> None:  # type: ignore[override]
        """Called (from the audio-receive thread) for every 20 ms audio frame."""
        if user is None:
            return

        # Extract raw PCM bytes — handle different discord.py Sink API shapes.
        if hasattr(data, "file"):
            # discord.py ≥ 2.x: AudioData.file is a BytesIO of decoded PCM.
            pcm = data.file.read()
            data.file.seek(0)
        elif hasattr(data, "data"):
            pcm = bytes(data.data)
        elif isinstance(data, (bytes, bytearray)):
            pcm = bytes(data)
        else:
            return

        if not pcm:
            return

        uid = user.id
        if uid not in self._buffers:
            self._buffers[uid] = bytearray()
        self._buffers[uid].extend(pcm)
        self._last_audio[uid] = time.monotonic()

    def cleanup(self) -> None:
        """Called automatically by discord.py when ``stop_recording()`` fires."""
        if self._checker and not self._checker.done():
            self._checker.cancel()
        self._buffers.clear()
        self._last_audio.clear()
        self._processing.clear()
        logger.info("MusicCommandSink cleaned up.")

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Schedule the background silence-checker coroutine on the event loop."""
        if self._checker is None or self._checker.done():
            self._checker = self._loop.create_task(self._silence_checker())
            logger.info("Voice command listener started (silence=%.1fs).", SILENCE_S)

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

                for uid in list(self._last_audio):
                    if uid in self._processing:
                        continue
                    if now - self._last_audio[uid] < SILENCE_S:
                        continue

                    # User has been silent → grab their buffer.
                    pcm = bytes(self._buffers.pop(uid, b""))
                    del self._last_audio[uid]

                    if len(pcm) < MIN_AUDIO_BYTES:
                        logger.debug(
                            "Audio from user %d too short (%d bytes) — discarding.",
                            uid, len(pcm),
                        )
                        continue

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
            logger.info("[Voice STT] User %d: %r", uid, text)
            if text:
                cmd = parse_command(text)
                if cmd:
                    logger.info(
                        "[Voice] Command detected — %r args=%r", cmd.name, cmd.args
                    )
                    await self.on_command(uid, cmd)
                else:
                    logger.debug("[Voice] No command matched transcript: %r", text)
        except Exception:
            logger.exception("[Voice] Error processing audio for user %d.", uid)
        finally:
            self._processing.discard(uid)
