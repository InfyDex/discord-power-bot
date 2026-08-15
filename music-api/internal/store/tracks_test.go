package store

import (
	"errors"
	"path/filepath"
	"testing"
	"time"
)

func openTestDB(t *testing.T) *DB {
	t.Helper()

	db, err := Open(filepath.Join(t.TempDir(), "tracks.db"))
	if err != nil {
		t.Fatalf("open: %v", err)
	}
	t.Cleanup(func() { db.Close() })
	return db
}

func track(id string) Track {
	return Track{
		ID:         id,
		Title:      "Title " + id,
		Duration:   120,
		Thumbnail:  "https://img/" + id,
		WebpageURL: "https://www.youtube.com/watch?v=" + id,
	}
}

func TestUpsertAndGet(t *testing.T) {
	db := openTestDB(t)

	if err := db.Upsert(track("aaa"), "downloads/aaa.mp3"); err != nil {
		t.Fatalf("upsert: %v", err)
	}

	rec, err := db.Get("aaa")
	if err != nil {
		t.Fatalf("get: %v", err)
	}
	if rec.Title != "Title aaa" || rec.FilePath != "downloads/aaa.mp3" || rec.Duration != 120 {
		t.Fatalf("unexpected record: %+v", rec)
	}
	if rec.PlayCount != 0 {
		t.Fatalf("play count should start at 0, got %d", rec.PlayCount)
	}

	// Re-upserting the same id updates rather than duplicating.
	updated := track("aaa")
	updated.Title = "Renamed"
	if err := db.Upsert(updated, "downloads/aaa.opus"); err != nil {
		t.Fatalf("re-upsert: %v", err)
	}

	rec, _ = db.Get("aaa")
	if rec.Title != "Renamed" || rec.FilePath != "downloads/aaa.opus" {
		t.Fatalf("upsert did not update row: %+v", rec)
	}

	n, err := db.Count()
	if err != nil || n != 1 {
		t.Fatalf("count = %d, %v; want 1", n, err)
	}
}

func TestGetMissingReturnsErrNotFound(t *testing.T) {
	db := openTestDB(t)

	if _, err := db.Get("nope"); !errors.Is(err, ErrNotFound) {
		t.Fatalf("err = %v; want ErrNotFound", err)
	}
}

func TestRecordPlay(t *testing.T) {
	db := openTestDB(t)
	_ = db.Upsert(track("bbb"), "downloads/bbb.mp3")

	for range 3 {
		if err := db.RecordPlay("bbb"); err != nil {
			t.Fatalf("record play: %v", err)
		}
	}

	rec, _ := db.Get("bbb")
	if rec.PlayCount != 3 {
		t.Fatalf("play count = %d; want 3", rec.PlayCount)
	}
	if rec.LastPlayedAt == "" {
		t.Fatal("last_played_at should be set after a play")
	}
}

func TestEvictLRUKeepsMostRecentlyPlayed(t *testing.T) {
	db := openTestDB(t)

	for _, id := range []string{"one", "two", "three"} {
		if err := db.Upsert(track(id), "downloads/"+id+".mp3"); err != nil {
			t.Fatalf("upsert %s: %v", id, err)
		}
	}
	// Timestamps have second granularity, so wait out the current second before
	// playing "one": that makes it strictly the most recently touched row, and
	// it must survive a limit of 1 even though it was inserted first.
	time.Sleep(1100 * time.Millisecond)
	if err := db.RecordPlay("one"); err != nil {
		t.Fatalf("record play: %v", err)
	}

	evicted, err := db.EvictLRU(1)
	if err != nil {
		t.Fatalf("evict: %v", err)
	}
	if len(evicted) != 2 {
		t.Fatalf("evicted %d rows; want 2", len(evicted))
	}

	if _, err := db.Get("one"); err != nil {
		t.Fatalf("most recently played track was evicted: %v", err)
	}
	for _, e := range evicted {
		if e.VideoID == "one" {
			t.Fatal("evicted the most recently played track")
		}
		if e.FilePath == "" {
			t.Fatal("evicted entry is missing its file path")
		}
	}

	n, _ := db.Count()
	if n != 1 {
		t.Fatalf("count after eviction = %d; want 1", n)
	}
}

func TestEvictLRUUnderLimitIsNoop(t *testing.T) {
	db := openTestDB(t)
	_ = db.Upsert(track("solo"), "downloads/solo.mp3")

	evicted, err := db.EvictLRU(10)
	if err != nil {
		t.Fatalf("evict: %v", err)
	}
	if len(evicted) != 0 {
		t.Fatalf("evicted %d rows; want 0", len(evicted))
	}
}

func TestAllDownloadedAndDelete(t *testing.T) {
	db := openTestDB(t)
	_ = db.Upsert(track("x1"), "downloads/x1.mp3")
	_ = db.Upsert(track("x2"), "downloads/x2.mp3")

	records, err := db.AllDownloaded()
	if err != nil {
		t.Fatalf("all downloaded: %v", err)
	}
	if len(records) != 2 {
		t.Fatalf("got %d records; want 2", len(records))
	}

	if err := db.Delete("x1"); err != nil {
		t.Fatalf("delete: %v", err)
	}
	records, _ = db.AllDownloaded()
	if len(records) != 1 || records[0].ID != "x2" {
		t.Fatalf("unexpected records after delete: %+v", records)
	}
}
