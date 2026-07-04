"""Per-guild playback state: queue, loop mode, volume, autoplay history."""
import enum
import random
from dataclasses import dataclass, field
from typing import Optional


class LoopMode(enum.Enum):
    OFF = 'off'
    TRACK = 'track'
    QUEUE = 'queue'


@dataclass
class Track:
    id: str
    title: str
    duration: int
    thumbnail: str
    webpage_url: str

    @classmethod
    def from_dict(cls, data: dict) -> 'Track':
        return cls(
            id=data['id'],
            title=data['title'],
            duration=data.get('duration') or 0,
            thumbnail=data.get('thumbnail', ''),
            webpage_url=data['webpage_url'],
        )


@dataclass
class GuildPlayer:
    """Owns one guild's queue and playback settings. Lives for the guild's lifetime,
    not just one voice session, so loop/volume/autoplay prefs persist across !stop/!play.
    """
    guild_id: int
    voice_client: Optional[object] = None
    queue: list = field(default_factory=list)
    history: list = field(default_factory=list)  # played video ids, for autoplay dedup
    current: Optional[Track] = None
    loop_mode: LoopMode = LoopMode.OFF
    autoplay: bool = False
    volume: float = 1.0  # 0.0-2.0, applied via discord.PCMVolumeTransformer

    def add(self, track: Track):
        self.queue.append(track)

    def shuffle(self):
        random.shuffle(self.queue)

    def next_track(self) -> Optional[Track]:
        """Pop the next track per loop mode. Does not touch autoplay — caller handles that
        when this returns None and self.current is still set.
        """
        if self.loop_mode == LoopMode.TRACK and self.current:
            return self.current

        if self.loop_mode == LoopMode.QUEUE and self.current:
            self.queue.append(self.current)

        if not self.queue:
            return None
        return self.queue.pop(0)

    def record_played(self, track: Track):
        self.current = track
        self.history.append(track.id)
        if len(self.history) > 200:
            self.history.pop(0)
