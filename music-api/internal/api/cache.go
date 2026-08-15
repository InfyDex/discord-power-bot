package api

import (
	"errors"
	"mime"
	"net/http"
	"os"
	"path/filepath"
	"strings"

	"github.com/rasik/discord-power-bot/music-api/internal/httpx"
	"github.com/rasik/discord-power-bot/music-api/internal/store"
)

// handleListCache lists every downloaded track — the pool !mix draws from.
func (s *Server) handleListCache(w http.ResponseWriter, r *http.Request) {
	records, err := s.db.AllDownloaded()
	if err != nil {
		httpx.Error(w, http.StatusInternalServerError, "storage_error", err.Error())
		return
	}

	onDiskOnly := r.URL.Query().Get("on_disk") == "true"
	out := make([]store.Record, 0, len(records))
	for _, rec := range records {
		if onDiskOnly {
			if _, err := os.Stat(rec.FilePath); err != nil {
				continue
			}
		}
		out = append(out, rec)
	}

	httpx.JSON(w, http.StatusOK, map[string]any{
		"count":  len(out),
		"limit":  s.cfg.CacheLimit,
		"tracks": out,
	})
}

func (s *Server) handleGetCachedTrack(w http.ResponseWriter, r *http.Request) {
	rec, err := s.db.Get(r.PathValue("videoID"))
	if errors.Is(err, store.ErrNotFound) {
		httpx.Error(w, http.StatusNotFound, "not_cached", "track is not in the download cache")
		return
	}
	if err != nil {
		httpx.Error(w, http.StatusInternalServerError, "storage_error", err.Error())
		return
	}

	_, statErr := os.Stat(rec.FilePath)
	httpx.JSON(w, http.StatusOK, map[string]any{
		"track":      rec,
		"on_disk":    statErr == nil,
		"stream_url": "/v1/tracks/" + rec.ID + "/stream",
	})
}

type cacheRequest struct {
	Query string `json:"query"`
}

// handleCacheTrack downloads a track up front so a later play starts instantly.
func (s *Server) handleCacheTrack(w http.ResponseWriter, r *http.Request) {
	var req cacheRequest
	if err := httpx.Decode(r, &req); err != nil || strings.TrimSpace(req.Query) == "" {
		httpx.Error(w, http.StatusBadRequest, "bad_request", "body must be {\"query\": \"song name or URL\"}")
		return
	}

	tracks, err := s.control.Resolve(r.Context(), req.Query)
	if err != nil {
		writeControlErr(w, err)
		return
	}

	type result struct {
		Track store.Track `json:"track"`
		Path  string      `json:"file_path,omitempty"`
		Error string      `json:"error,omitempty"`
	}

	results := make([]result, 0, len(tracks))
	for _, t := range tracks {
		path, err := s.yt.GetAudioFile(r.Context(), t)
		res := result{Track: t, Path: path}
		if err != nil {
			res.Error = err.Error()
		}
		results = append(results, res)
	}

	httpx.JSON(w, http.StatusOK, map[string]any{
		"count":   len(results),
		"results": results,
	})
}

// handleDeleteCachedTrack removes the registry row and the file on disk.
func (s *Server) handleDeleteCachedTrack(w http.ResponseWriter, r *http.Request) {
	videoID := r.PathValue("videoID")

	rec, err := s.db.Get(videoID)
	if errors.Is(err, store.ErrNotFound) {
		httpx.Error(w, http.StatusNotFound, "not_cached", "track is not in the download cache")
		return
	}
	if err != nil {
		httpx.Error(w, http.StatusInternalServerError, "storage_error", err.Error())
		return
	}

	fileRemoved := true
	if err := os.Remove(rec.FilePath); err != nil && !os.IsNotExist(err) {
		s.log.Warn("could not delete cached file", "path", rec.FilePath, "error", err)
		fileRemoved = false
	}
	if err := s.db.Delete(videoID); err != nil {
		httpx.Error(w, http.StatusInternalServerError, "storage_error", err.Error())
		return
	}

	httpx.JSON(w, http.StatusOK, map[string]any{
		"deleted":      videoID,
		"file_removed": fileRemoved,
	})
}

// handleTrackStream serves a cached track's audio by video id.
func (s *Server) handleTrackStream(w http.ResponseWriter, r *http.Request) {
	rec, err := s.db.Get(r.PathValue("videoID"))
	if errors.Is(err, store.ErrNotFound) {
		httpx.Error(w, http.StatusNotFound, "not_cached", "track is not in the download cache")
		return
	}
	if err != nil {
		httpx.Error(w, http.StatusInternalServerError, "storage_error", err.Error())
		return
	}
	s.serveAudio(w, r, rec.FilePath)
}

// serveAudio streams a local audio file with range support, so clients can seek.
func (s *Server) serveAudio(w http.ResponseWriter, r *http.Request, path string) {
	f, err := os.Open(path)
	if err != nil {
		s.log.Warn("cached file missing on disk", "path", path, "error", err)
		httpx.Error(w, http.StatusNotFound, "file_missing", "audio file is no longer on disk")
		return
	}
	defer f.Close()

	info, err := f.Stat()
	if err != nil {
		httpx.Error(w, http.StatusInternalServerError, "io_error", err.Error())
		return
	}

	if ctype := mime.TypeByExtension(filepath.Ext(path)); ctype != "" {
		w.Header().Set("Content-Type", ctype)
	} else {
		w.Header().Set("Content-Type", "application/octet-stream")
	}
	w.Header().Set("Accept-Ranges", "bytes")

	http.ServeContent(w, r, filepath.Base(path), info.ModTime(), f)
}
