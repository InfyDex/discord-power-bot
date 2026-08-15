// Package httpx holds the JSON and middleware plumbing shared by the handlers.
package httpx

import (
	"crypto/subtle"
	"encoding/json"
	"errors"
	"io"
	"log/slog"
	"net/http"
	"strconv"
	"strings"
	"time"
)

// ErrorBody is the single error shape every failing endpoint returns.
type ErrorBody struct {
	Error struct {
		Code    string `json:"code"`
		Message string `json:"message"`
	} `json:"error"`
}

func JSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	if v == nil {
		return
	}
	if err := json.NewEncoder(w).Encode(v); err != nil {
		slog.Error("write response", "error", err)
	}
}

func Error(w http.ResponseWriter, status int, code, message string) {
	var body ErrorBody
	body.Error.Code = code
	body.Error.Message = message
	JSON(w, status, body)
}

var ErrBadJSON = errors.New("malformed request body")

// Decode reads a JSON body, rejecting unknown fields so typos surface as
// errors instead of silently defaulting.
func Decode(r *http.Request, dst any) error {
	dec := json.NewDecoder(io.LimitReader(r.Body, 1<<20))
	dec.DisallowUnknownFields()
	if err := dec.Decode(dst); err != nil {
		return err
	}
	return nil
}

// QueryInt reads an integer query parameter, falling back when absent or unparsable.
func QueryInt(r *http.Request, key string, fallback int) int {
	if v := r.URL.Query().Get(key); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
	}
	return fallback
}

// ---------- middleware ----------

type Middleware func(http.Handler) http.Handler

func Chain(h http.Handler, mw ...Middleware) http.Handler {
	for i := len(mw) - 1; i >= 0; i-- {
		h = mw[i](h)
	}
	return h
}

type statusRecorder struct {
	http.ResponseWriter
	status int
}

func (s *statusRecorder) WriteHeader(code int) {
	s.status = code
	s.ResponseWriter.WriteHeader(code)
}

func (s *statusRecorder) Flush() {
	if f, ok := s.ResponseWriter.(http.Flusher); ok {
		f.Flush()
	}
}

func Logger(log *slog.Logger) Middleware {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			start := time.Now()
			rec := &statusRecorder{ResponseWriter: w, status: http.StatusOK}
			next.ServeHTTP(rec, r)

			log.Info("request",
				"method", r.Method,
				"path", r.URL.Path,
				"status", rec.status,
				"duration", time.Since(start).Round(time.Millisecond).String(),
			)
		})
	}
}

func Recover(log *slog.Logger) Middleware {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			defer func() {
				if rec := recover(); rec != nil {
					log.Error("panic serving request", "path", r.URL.Path, "panic", rec)
					Error(w, http.StatusInternalServerError, "internal_error", "internal server error")
				}
			}()
			next.ServeHTTP(w, r)
		})
	}
}

// APIKey gates every route except those in exempt when a key is configured.
func APIKey(key string, exempt ...string) Middleware {
	exemptSet := make(map[string]bool, len(exempt))
	for _, p := range exempt {
		exemptSet[p] = true
	}

	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if key == "" || exemptSet[r.URL.Path] {
				next.ServeHTTP(w, r)
				return
			}

			presented := r.Header.Get("X-API-Key")
			if presented == "" {
				presented = strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer ")
			}
			if subtle.ConstantTimeCompare([]byte(presented), []byte(key)) != 1 {
				Error(w, http.StatusUnauthorized, "unauthorized", "missing or invalid API key")
				return
			}
			next.ServeHTTP(w, r)
		})
	}
}
