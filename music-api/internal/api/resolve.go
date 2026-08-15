package api

import (
	"net/http"
	"strings"

	"github.com/rasik/discord-power-bot/music-api/internal/httpx"
	"github.com/rasik/discord-power-bot/music-api/internal/store"
)

// handleSearch backs the bot's /search picker: candidates, nothing queued.
func (s *Server) handleSearch(w http.ResponseWriter, r *http.Request) {
	query := strings.TrimSpace(r.URL.Query().Get("q"))
	if query == "" {
		httpx.Error(w, http.StatusBadRequest, "missing_query", "query parameter q is required")
		return
	}

	limit := httpx.QueryInt(r, "limit", 5)
	if limit < 1 || limit > 25 {
		httpx.Error(w, http.StatusBadRequest, "invalid_limit", "limit must be between 1 and 25")
		return
	}

	tracks, err := s.control.Search(r.Context(), query, limit)
	if err != nil {
		writeControlErr(w, err)
		return
	}

	httpx.JSON(w, http.StatusOK, map[string]any{
		"query":   query,
		"count":   len(tracks),
		"results": tracks,
	})
}

type resolveRequest struct {
	Query string `json:"query"`
}

// handleResolve turns a query or URL into tracks without queueing them.
func (s *Server) handleResolve(w http.ResponseWriter, r *http.Request) {
	var req resolveRequest
	if err := httpx.Decode(r, &req); err != nil {
		httpx.Error(w, http.StatusBadRequest, "bad_request", "body must be {\"query\": \"...\"}")
		return
	}
	if strings.TrimSpace(req.Query) == "" {
		httpx.Error(w, http.StatusBadRequest, "missing_query", "query is required")
		return
	}

	tracks, err := s.control.Resolve(r.Context(), req.Query)
	if err != nil {
		writeControlErr(w, err)
		return
	}

	httpx.JSON(w, http.StatusOK, map[string]any{
		"query":  req.Query,
		"count":  len(tracks),
		"tracks": tracks,
	})
}

// cachedOnly reports which of the given tracks are already downloaded.
func (s *Server) cachedOnly(tracks []store.Track) []string {
	var ids []string
	for _, t := range tracks {
		if _, err := s.db.Get(t.ID); err == nil {
			ids = append(ids, t.ID)
		}
	}
	return ids
}
