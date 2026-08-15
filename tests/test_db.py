"""TrackDB sqlite registry tests against a temp database."""
import pytest

from cogs.music_system.db import TrackDB

from conftest import track_dict


@pytest.fixture
def db(tmp_path):
    d = TrackDB(db_path=str(tmp_path / 'tracks.db'))
    yield d
    d.conn.close()


class TestUpsertGet:
    def test_get_missing_returns_none(self, db):
        assert db.get('nope') is None

    def test_upsert_then_get_roundtrip(self, db):
        t = track_dict(1)
        db.upsert(t, '/tmp/a.mp3')
        row = db.get(t['id'])
        assert row == {
            'id': t['id'], 'title': t['title'], 'webpage_url': t['webpage_url'],
            'duration': t['duration'], 'thumbnail': t['thumbnail'], 'file_path': '/tmp/a.mp3',
        }

    def test_upsert_conflict_updates_fields(self, db):
        t = track_dict(1)
        db.upsert(t, '/old.mp3')
        t2 = dict(t, title='New Title')
        db.upsert(t2, '/new.mp3')
        row = db.get(t['id'])
        assert row['title'] == 'New Title'
        assert row['file_path'] == '/new.mp3'
        assert len(db.all_downloaded()) == 1

    def test_upsert_none_duration_and_thumbnail(self, db):
        t = track_dict(1)
        t['duration'] = None
        t['thumbnail'] = None
        db.upsert(t, '/x.mp3')
        row = db.get(t['id'])
        assert row['duration'] == 0
        assert row['thumbnail'] == ''

    def test_delete(self, db):
        t = track_dict(1)
        db.upsert(t, '/x.mp3')
        db.delete(t['id'])
        assert db.get(t['id']) is None

    def test_delete_nonexistent_is_noop(self, db):
        db.delete('ghost')  # must not raise


class TestPlayTracking:
    def test_record_play_increments(self, db):
        t = track_dict(1)
        db.upsert(t, '/x.mp3')
        db.record_play(t['id'])
        db.record_play(t['id'])
        count, last = db.conn.execute(
            'SELECT play_count, last_played_at FROM tracks WHERE video_id = ?', (t['id'],)
        ).fetchone()
        assert count == 2
        assert last is not None

    def test_record_play_unknown_id_is_noop(self, db):
        db.record_play('ghost')  # must not raise


class TestAllDownloaded:
    def test_empty(self, db):
        assert db.all_downloaded() == []

    def test_returns_all_rows(self, db):
        for i in range(3):
            db.upsert(track_dict(i), f'/f{i}.mp3')
        rows = db.all_downloaded()
        assert len(rows) == 3
        assert {r['id'] for r in rows} == {track_dict(i)['id'] for i in range(3)}


class TestEviction:
    def _seed(self, db, n):
        for i in range(n):
            t = track_dict(i)
            db.upsert(t, f'/f{i}.mp3')
            # deterministic recency: bigger i == played more recently
            db.conn.execute(
                "UPDATE tracks SET last_played_at = datetime('2026-01-01', ? || ' minutes') WHERE video_id = ?",
                (str(i), t['id']),
            )
        db.conn.commit()

    def test_no_eviction_under_limit(self, db):
        self._seed(db, 3)
        assert db.evict_lru(5) == []
        assert len(db.all_downloaded()) == 3

    def test_no_eviction_at_exact_limit(self, db):
        self._seed(db, 3)
        assert db.evict_lru(3) == []

    def test_evicts_least_recently_played(self, db):
        self._seed(db, 5)
        evicted = db.evict_lru(3)
        evicted_ids = {v for v, _ in evicted}
        assert evicted_ids == {track_dict(0)['id'], track_dict(1)['id']}
        remaining = {r['id'] for r in db.all_downloaded()}
        assert remaining == {track_dict(i)['id'] for i in (2, 3, 4)}

    def test_evict_returns_file_paths(self, db):
        self._seed(db, 2)
        evicted = db.evict_lru(1)
        assert evicted == [(track_dict(0)['id'], '/f0.mp3')]

    def test_limit_zero_evicts_everything(self, db):
        self._seed(db, 2)
        assert len(db.evict_lru(0)) == 2
        assert db.all_downloaded() == []

    def test_never_played_falls_back_to_download_time(self, db):
        # row without last_played_at must still participate via downloaded_at
        t_old = track_dict(1)
        db.upsert(t_old, '/old.mp3')
        db.conn.execute(
            "UPDATE tracks SET downloaded_at = datetime('2020-01-01') WHERE video_id = ?", (t_old['id'],)
        )
        t_new = track_dict(2)
        db.upsert(t_new, '/new.mp3')
        db.record_play(t_new['id'])
        db.conn.commit()
        evicted = db.evict_lru(1)
        assert [v for v, _ in evicted] == [t_old['id']]
