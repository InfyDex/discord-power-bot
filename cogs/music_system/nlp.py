"""
Natural-language command parser for voice transcripts and chat messages.

Supported commands (examples of what users can say/type):
  skip           — "bot skip", "skip the song", "skip this"
  pause          — "bot pause", "pause"
  resume         — "bot resume", "resume", "unpause", "continue"
  stop           — "bot stop", "stop the music", "disconnect", "leave", "bye"
  nowplaying     — "what's playing", "now playing", "what song is this"
  volume <pct>   — "bot volume 80", "set volume to 50"
  shuffle        — "bot shuffle", "shuffle the queue"
  loop           — "bot loop", "repeat"
  play <query>   — "bot play lofi music", "play something relaxing"
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedCommand:
    """The result of parsing a natural-language utterance."""

    name: str  # command identifier, e.g. "skip", "play"
    args: str  # extra arguments, e.g. the search query for "play"


# ---------------------------------------------------------------------------
# Matching rules
# Each entry: (compiled regex, command name).
# Patterns are tried IN ORDER — put more specific ones before catch-alls.
# ---------------------------------------------------------------------------
_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bskip\b(?:\s+(?:this|the)?\s*song)?", re.I), "skip"),
    (re.compile(r"\bpause\b", re.I), "pause"),
    (re.compile(r"\b(?:resume|unpause|continue\s+(?:the\s+)?music)\b", re.I), "resume"),
    (re.compile(r"\b(?:stop|disconnect|leave|bye|quit)\b", re.I), "stop"),
    (re.compile(
        r"\b(?:now\s*playing|what(?:'s|s)?\s+playing|what\s+song|current\s+song|what\s+is\s+this)\b",
        re.I,
    ), "nowplaying"),
    (re.compile(r"\bvolume\s+(\d{1,3})\b", re.I), "volume"),
    (re.compile(r"\bshuffle\b", re.I), "shuffle"),
    (re.compile(r"\b(?:loop|repeat)\b", re.I), "loop"),
    # "play" must be LAST — it greedily captures the rest as the query.
    (re.compile(r"\bplay\s+(.+)", re.I), "play"),
]


def _wake_word() -> str:
    return os.getenv("VOICE_WAKE_WORD", "friday").strip().lower()


def strip_wake_word(text: str) -> str:
    """Remove the leading wake word (e.g. 'bot') and punctuation from *text*."""
    wake = re.escape(_wake_word())
    return re.sub(rf"^{wake}[\s,!.]+", "", text.strip(), flags=re.I).strip()


def has_wake_word(text: str) -> bool:
    """Return True if *text* begins with the configured wake word."""
    wake = re.escape(_wake_word())
    return bool(re.match(rf"^{wake}(?:\s|,|!|\.)", text.strip(), re.I))


def parse_command(text: str) -> ParsedCommand | None:
    """
    Parse a raw string (voice transcript **or** chat message) into a
    :class:`ParsedCommand`.

    Strips the wake word before matching, so both ``"bot skip"`` and plain
    ``"skip"`` (when the wake word has already been checked by the caller) work.

    Returns ``None`` when no music command is recognised.
    """
    clean = strip_wake_word(text)
    if not clean:
        return None

    for pattern, cmd_name in _RULES:
        m = pattern.search(clean)
        if m:
            args = ""
            if cmd_name in ("play", "volume") and m.lastindex:
                args = m.group(1).strip()
            return ParsedCommand(name=cmd_name, args=args)

    return None
