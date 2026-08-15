package api

import (
	"net/http"
	"strconv"

	"github.com/rasik/discord-power-bot/music-api/internal/httpx"
)

// handleListCommands shows what the API has asked the bot to do. Filter with
// ?guild_id= and ?status=pending|claimed|done|failed.
func (s *Server) handleListCommands(w http.ResponseWriter, r *http.Request) {
	commands, err := s.control.Commands(
		r.URL.Query().Get("guild_id"),
		r.URL.Query().Get("status"),
		httpx.QueryInt(r, "limit", 50),
	)
	if err != nil {
		writeControlErr(w, err)
		return
	}

	httpx.JSON(w, http.StatusOK, map[string]any{
		"count":    len(commands),
		"commands": commands,
	})
}

// handleGetCommand is how a client follows up on a queued control call: poll
// until status is done or failed.
func (s *Server) handleGetCommand(w http.ResponseWriter, r *http.Request) {
	id, err := strconv.ParseInt(r.PathValue("id"), 10, 64)
	if err != nil {
		httpx.Error(w, http.StatusBadRequest, "invalid_id", "command id must be a number")
		return
	}

	cmd, err := s.control.Command(id)
	if err != nil {
		writeControlErr(w, err)
		return
	}
	httpx.JSON(w, http.StatusOK, cmd)
}
