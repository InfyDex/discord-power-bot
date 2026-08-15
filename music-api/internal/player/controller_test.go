package player

import (
	"context"
	"errors"
	"io"
	"log/slog"
	"path/filepath"
	"testing"

	"github.com/rasik/discord-power-bot/music-api/internal/store"
)

type fakeSource struct {
	search    []store.Track
	extract   []store.Track
	cachedURL map[string]store.Track
}

func (f *fakeSource) Search(context.Context, string, int) ([]store.Track, error) {
	if len(f.search) == 0 {
		return nil, errors.New("no results")
	}
	return f.search, nil
}

func (f *fakeSource) Extract(context.Context, string) ([]store.Track, error) { return f.extract, nil }

func (f *fakeSource) LookupCachedURL(url string) (store.Track, bool) {
	t, ok := f.cachedURL[url]
	return t, ok
}

func (f *fakeSource) Related(context.Context, string, map[string]bool) (store.Track, error) {
	return store.Track{}, errors.New("none")
}

func (f *fakeSource) GetAudioFile(_ context.Context, t store.Track) (string, error) {
	return "downloads/" + t.ID + ".mp3", nil
}

func track(id string) store.Track {
	return store.Track{ID: id, Title: "Track " + id, Duration: 100, WebpageURL: "https://yt/" + id}
}

func newTestController(t *testing.T, src *fakeSource) (*Controller, *store.DB) {
	t.Helper()

	db, err := store.Open(filepath.Join(t.TempDir(), "tracks.db"))
	if err != nil {
		t.Fatalf("open store: %v", err)
	}
	t.Cleanup(func() { db.Close() })

	log := slog.New(slog.NewTextHandler(io.Discard, nil))
	return NewController(src, db, log), db
}

// liveBot writes the mirror the Python bridge would write while playing.
func liveBot(t *testing.T, db *store.DB, guildID, status string, current *store.Track, queue []store.Track) {
	t.Helper()

	if err := db.Heartbeat("bot", "test", 1); err != nil {
		t.Fatalf("heartbeat: %v", err)
	}

	entries := make([]store.QueueEntry, 0, len(queue))
	for i, tr := range queue {
		entries = append(entries, store.QueueEntry{Track: tr, Position: i + 1})
	}
	err := db.MirrorGuild(store.GuildState{
		GuildID:        guildID,
		Status:         status,
		Current:        current,
		LoopMode:       "off",
		VolumePercent:  100,
		VoiceChannelID: "voice-1",
	}, entries)
	if err != nil {
		t.Fatalf("mirror: %v", err)
	}
}

func TestSnapshotOfUnknownGuildIsIdle(t *testing.T) {
	c, _ := newTestController(t, &fakeSource{})

	s, err := c.Snapshot("g1")
	if err != nil {
		t.Fatalf("snapshot: %v", err)
	}
	if s.Status != StatusIdle || s.Current != nil || s.QueueLength != 0 {
		t.Fatalf("unexpected snapshot: %+v", s)
	}
	if s.VolumePercent != 100 || s.Loop != string(LoopOff) || s.BotOnline {
		t.Fatalf("unexpected defaults: %+v", s)
	}
}

func TestSnapshotMergesStateAndQueue(t *testing.T) {
	c, db := newTestController(t, &fakeSource{})
	current := track("live")
	liveBot(t, db, "g1", StatusPlaying, &current, []store.Track{track("q1"), track("q2")})

	s, err := c.Snapshot("g1")
	if err != nil {
		t.Fatalf("snapshot: %v", err)
	}
	if s.Status != StatusPlaying || s.Current.ID != "live" {
		t.Fatalf("state not reflected: %+v", s)
	}
	if s.QueueLength != 2 || s.Queue[1].ID != "q2" || s.Queue[1].Position != 2 {
		t.Fatalf("queue not reflected: %+v", s.Queue)
	}
	if !s.BotOnline {
		t.Fatal("bot heartbeat should mark the bot online")
	}
	if s.StreamURL != "/v1/tracks/live/stream" {
		t.Fatalf("stream url = %q", s.StreamURL)
	}

	guilds, err := c.Guilds()
	if err != nil || len(guilds) != 1 || guilds[0].GuildID != "g1" {
		t.Fatalf("guilds = %+v, %v", guilds, err)
	}
}

func TestPlayResolvesAndQueuesCommand(t *testing.T) {
	c, db := newTestController(t, &fakeSource{search: []store.Track{track("s1")}})

	d, err := c.Play(context.Background(), "g1", PlayRequest{
		Query:          "a song",
		VoiceChannelID: "voice-9",
		RequestedBy:    "rasik",
	})
	if err != nil {
		t.Fatalf("play: %v", err)
	}
	if len(d.Tracks) != 1 || d.Tracks[0].ID != "s1" {
		t.Fatalf("resolved tracks = %+v", d.Tracks)
	}
	if d.Command.Action != store.ActionPlay || d.Command.Status != store.CommandPending {
		t.Fatalf("command = %+v", d.Command)
	}
	if d.BotOnline {
		t.Fatal("bot should read as offline without a heartbeat")
	}

	// The command carries the resolved tracks, so the bot skips re-resolution.
	tracks, ok := d.Command.Payload["tracks"].([]any)
	if !ok || len(tracks) != 1 {
		t.Fatalf("payload = %+v", d.Command.Payload)
	}
	if d.Command.Payload["voice_channel_id"] != "voice-9" || d.Command.Payload["requested_by"] != "rasik" {
		t.Fatalf("payload = %+v", d.Command.Payload)
	}

	stored, err := db.GetCommand(d.Command.ID)
	if err != nil || stored.GuildID != "g1" {
		t.Fatalf("stored command = %+v, %v", stored, err)
	}
}

func TestPlayNeedsAVoiceChannelSomewhere(t *testing.T) {
	c, db := newTestController(t, &fakeSource{search: []store.Track{track("s1")}})

	if _, err := c.Play(context.Background(), "g1", PlayRequest{Query: "a song"}); !errors.Is(err, ErrNoVoiceChannel) {
		t.Fatalf("err = %v; want ErrNoVoiceChannel", err)
	}

	// Once the bot is connected, its own channel is enough.
	current := track("live")
	liveBot(t, db, "g1", StatusPlaying, &current, nil)

	if _, err := c.Play(context.Background(), "g1", PlayRequest{Query: "a song"}); err != nil {
		t.Fatalf("play with connected bot: %v", err)
	}
}

func TestResolvePrefersCachedURL(t *testing.T) {
	url := "https://www.youtube.com/watch?v=cached00001"
	src := &fakeSource{cachedURL: map[string]store.Track{url: track("cached00001")}}
	c, _ := newTestController(t, src)

	tracks, err := c.Resolve(context.Background(), url)
	if err != nil || len(tracks) != 1 || tracks[0].ID != "cached00001" {
		t.Fatalf("tracks = %+v, %v", tracks, err)
	}

	if _, err := c.Resolve(context.Background(), "   "); !errors.Is(err, ErrNoResults) {
		t.Fatalf("blank query err = %v; want ErrNoResults", err)
	}
}

func TestControlsRejectImpossibleStates(t *testing.T) {
	c, _ := newTestController(t, &fakeSource{})

	if _, err := c.Skip("g1"); !errors.Is(err, ErrNothingPlaying) {
		t.Errorf("skip = %v", err)
	}
	if _, err := c.Pause("g1"); !errors.Is(err, ErrNothingPlaying) {
		t.Errorf("pause = %v", err)
	}
	if _, err := c.Resume("g1"); !errors.Is(err, ErrNotPaused) {
		t.Errorf("resume = %v", err)
	}
	if _, err := c.ClearQueue("g1"); !errors.Is(err, ErrEmptyQueue) {
		t.Errorf("clear = %v", err)
	}
	if _, err := c.Shuffle("g1"); !errors.Is(err, ErrQueueTooShort) {
		t.Errorf("shuffle = %v", err)
	}
	if _, _, err := c.Mix("g1", "voice-1"); !errors.Is(err, ErrNoCached) {
		t.Errorf("mix = %v", err)
	}
	if _, _, err := c.RemoveAt("g1", 1); !errors.Is(err, ErrInvalidPos) {
		t.Errorf("remove = %v", err)
	}
}

func TestControlsAgainstLiveBotProduceCommands(t *testing.T) {
	c, db := newTestController(t, &fakeSource{})
	current := track("live")
	liveBot(t, db, "g1", StatusPlaying, &current, []store.Track{track("q1"), track("q2")})

	checks := []struct {
		name   string
		run    func() (Dispatch, error)
		action string
	}{
		{"skip", func() (Dispatch, error) { return c.Skip("g1") }, store.ActionSkip},
		{"pause", func() (Dispatch, error) { return c.Pause("g1") }, store.ActionPause},
		{"stop", func() (Dispatch, error) { return c.Stop("g1") }, store.ActionStop},
		{"clear", func() (Dispatch, error) { return c.ClearQueue("g1") }, store.ActionClear},
		{"shuffle", func() (Dispatch, error) { return c.Shuffle("g1") }, store.ActionShuffle},
		{"loop", func() (Dispatch, error) { return c.SetLoop("g1", LoopQueue) }, store.ActionLoop},
		{"volume", func() (Dispatch, error) { return c.SetVolume("g1", 50) }, store.ActionVolume},
		{"autoplay", func() (Dispatch, error) { return c.SetAutoplay("g1", nil) }, store.ActionAutoplay},
	}

	for _, check := range checks {
		d, err := check.run()
		if err != nil {
			t.Fatalf("%s: %v", check.name, err)
		}
		if d.Command.Action != check.action {
			t.Errorf("%s queued action %q; want %q", check.name, d.Command.Action, check.action)
		}
		if !d.BotOnline {
			t.Errorf("%s reported the bot offline", check.name)
		}
	}

	// Pause is rejected once the mirror says the player is already paused.
	liveBot(t, db, "g1", StatusPaused, &current, nil)
	if _, err := c.Pause("g1"); !errors.Is(err, ErrAlreadyPaused) {
		t.Errorf("pause when paused = %v", err)
	}
	if _, err := c.Resume("g1"); err != nil {
		t.Errorf("resume when paused = %v", err)
	}
}

func TestRemoveAtNamesTheTargetTrack(t *testing.T) {
	c, db := newTestController(t, &fakeSource{})
	current := track("live")
	liveBot(t, db, "g1", StatusPlaying, &current, []store.Track{track("q1"), track("q2")})

	d, target, err := c.RemoveAt("g1", 2)
	if err != nil {
		t.Fatalf("remove: %v", err)
	}
	if target.ID != "q2" {
		t.Fatalf("target = %+v", target)
	}
	if d.Command.Payload["video_id"] != "q2" || d.Command.Payload["position"] != float64(2) {
		t.Fatalf("payload = %+v", d.Command.Payload)
	}
}

func TestAutoplayExplicitVersusToggle(t *testing.T) {
	c, _ := newTestController(t, &fakeSource{})

	enabled := true
	d, err := c.SetAutoplay("g1", &enabled)
	if err != nil {
		t.Fatalf("set autoplay: %v", err)
	}
	if d.Command.Payload["enabled"] != true {
		t.Fatalf("payload = %+v", d.Command.Payload)
	}

	d, err = c.SetAutoplay("g1", nil)
	if err != nil {
		t.Fatalf("toggle autoplay: %v", err)
	}
	if d.Command.Payload["toggle"] != true {
		t.Fatalf("payload = %+v", d.Command.Payload)
	}
}

func TestMixCountsCachedTracks(t *testing.T) {
	c, db := newTestController(t, &fakeSource{})
	for _, id := range []string{"c1", "c2"} {
		if err := db.Upsert(track(id), "downloads/"+id+".mp3"); err != nil {
			t.Fatalf("upsert: %v", err)
		}
	}

	d, count, err := c.Mix("g1", "voice-1")
	if err != nil {
		t.Fatalf("mix: %v", err)
	}
	if count != 2 || d.Command.Action != store.ActionMix {
		t.Fatalf("count = %d command = %+v", count, d.Command)
	}
	if d.Command.Payload["voice_channel_id"] != "voice-1" {
		t.Fatalf("payload = %+v", d.Command.Payload)
	}
}

func TestCommandInspection(t *testing.T) {
	c, db := newTestController(t, &fakeSource{})
	current := track("live")
	liveBot(t, db, "g1", StatusPlaying, &current, nil)

	d, err := c.Skip("g1")
	if err != nil {
		t.Fatalf("skip: %v", err)
	}

	got, err := c.Command(d.Command.ID)
	if err != nil || got.Action != store.ActionSkip {
		t.Fatalf("command = %+v, %v", got, err)
	}

	list, err := c.Commands("g1", store.CommandPending, 10)
	if err != nil || len(list) != 1 {
		t.Fatalf("commands = %+v, %v", list, err)
	}

	if _, err := c.Command(4242); !errors.Is(err, store.ErrNotFound) {
		t.Fatalf("missing command err = %v; want ErrNotFound", err)
	}
}

func TestCurrentFileNeedsCachedAudio(t *testing.T) {
	c, db := newTestController(t, &fakeSource{})
	current := track("live")
	liveBot(t, db, "g1", StatusPlaying, &current, nil)

	if _, ok := c.CurrentFile("g1"); ok {
		t.Fatal("no cache row yet, so there should be no file")
	}

	if err := db.Upsert(current, "downloads/live.mp3"); err != nil {
		t.Fatalf("upsert: %v", err)
	}
	path, ok := c.CurrentFile("g1")
	if !ok || path != "downloads/live.mp3" {
		t.Fatalf("current file = %q, %v", path, ok)
	}
}
