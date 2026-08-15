"""GuildPlayer / Track / LoopMode unit tests."""
from cogs.music_system.player import GuildPlayer, LoopMode, Track

from conftest import make_track


def make_player(**kw):
    return GuildPlayer(guild_id=1, **kw)


class TestTrack:
    def test_from_dict_full(self):
        t = Track.from_dict({
            'id': 'abc', 'title': 'T', 'duration': 10,
            'thumbnail': 'thumb', 'webpage_url': 'url',
        })
        assert (t.id, t.title, t.duration, t.thumbnail, t.webpage_url) == ('abc', 'T', 10, 'thumb', 'url')

    def test_from_dict_none_duration_becomes_zero(self):
        t = Track.from_dict({'id': 'a', 'title': 'T', 'duration': None, 'webpage_url': 'u'})
        assert t.duration == 0

    def test_from_dict_missing_optional_fields(self):
        t = Track.from_dict({'id': 'a', 'title': 'T', 'webpage_url': 'u'})
        assert t.duration == 0
        assert t.thumbnail == ''


class TestQueueBasics:
    def test_add_appends_in_order(self):
        p = make_player()
        t1, t2 = make_track(1), make_track(2)
        p.add(t1)
        p.add(t2)
        assert p.queue == [t1, t2]

    def test_next_track_pops_fifo(self):
        p = make_player()
        t1, t2 = make_track(1), make_track(2)
        p.queue = [t1, t2]
        assert p.next_track() is t1
        assert p.queue == [t2]

    def test_next_track_empty_queue_returns_none(self):
        p = make_player()
        assert p.next_track() is None

    def test_shuffle_preserves_membership(self):
        p = make_player()
        tracks = [make_track(i) for i in range(10)]
        p.queue = list(tracks)
        p.shuffle()
        assert sorted(t.id for t in p.queue) == sorted(t.id for t in tracks)


class TestLoopModes:
    def test_loop_off_does_not_requeue_current(self):
        p = make_player()
        p.current = make_track(1)
        p.queue = [make_track(2)]
        nxt = p.next_track()
        assert nxt.id == make_track(2).id
        assert p.queue == []

    def test_loop_track_returns_current_forever(self):
        p = make_player(loop_mode=LoopMode.TRACK)
        cur = make_track(1)
        p.current = cur
        p.queue = [make_track(2)]
        assert p.next_track() is cur
        assert p.next_track() is cur
        assert len(p.queue) == 1  # queue untouched

    def test_loop_track_without_current_falls_through_to_queue(self):
        p = make_player(loop_mode=LoopMode.TRACK)
        t = make_track(1)
        p.queue = [t]
        assert p.next_track() is t

    def test_loop_queue_reappends_current(self):
        p = make_player(loop_mode=LoopMode.QUEUE)
        cur, nxt = make_track(1), make_track(2)
        p.current = cur
        p.queue = [nxt]
        assert p.next_track() is nxt
        assert p.queue == [cur]

    def test_loop_queue_single_track_cycles(self):
        p = make_player(loop_mode=LoopMode.QUEUE)
        t = make_track(1)
        p.current = t
        assert p.next_track() is t  # re-appended then popped

    def test_loop_queue_empty_no_current(self):
        p = make_player(loop_mode=LoopMode.QUEUE)
        assert p.next_track() is None


class TestHistory:
    def test_record_played_sets_current_and_history(self):
        p = make_player()
        t = make_track(1)
        p.record_played(t)
        assert p.current is t
        assert p.history == [t.id]

    def test_history_capped_at_200(self):
        p = make_player()
        for i in range(250):
            p.record_played(make_track(i))
        assert len(p.history) == 200
        assert p.history[0] == make_track(50).id  # oldest 50 dropped
        assert p.history[-1] == make_track(249).id


class TestDefaults:
    def test_defaults(self):
        p = make_player()
        assert p.loop_mode is LoopMode.OFF
        assert p.autoplay is False
        assert p.volume == 1.0
        assert p.queue == [] and p.history == [] and p.current is None
