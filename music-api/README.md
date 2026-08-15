# Music API

HTTP API for the Discord bot's music system. It is not a second player — it is
the bot's other face. Both processes run on the same machine against **one
sqlite database**, so a song queued over HTTP plays in the voice channel, and a
song queued with `!play` in Discord shows up in `GET /queue`.

Standalone Go module; the bot keeps working with the API stopped, and vice versa.

## How the two halves fit together

The bot owns the Discord gateway and the voice connection, so it does the
playing. The API resolves queries, manages the download cache, and drives the
bot. They meet in `downloads/tracks.db`:

| Table | Written by | Read by | Holds |
|---|---|---|---|
| `guild_state` | bot | API | status, current track, position, loop, volume, autoplay, voice channel |
| `guild_queue` | bot | API | the live queue, in order |
| `commands` | API | bot | play/skip/pause/… to execute, with result or error |
| `workers` | both | both | heartbeats — is the bot up? |
| `download_locks` | both | both | one yt-dlp run per video, across processes |
| `tracks` | both | both | the download cache (unchanged from before) |

Ownership is strict, so neither side overwrites the other.

```
   HTTP client                Discord user
        │                          │
        ▼                          ▼
   ┌─────────┐   commands    ┌───────────┐
   │  API    │ ────────────► │    bot    │ ──► voice channel
   │ (Go)    │ ◄──────────── │ (Python)  │
   └─────────┘  state+queue  └───────────┘
        └────────► downloads/tracks.db ◄────────┘
```

A control call answers **202** with a command id; the bot claims it within a
second, executes it, and writes back `done` or `failed`. Poll
`GET /v1/commands/{id}` for the outcome, or just re-read the player. When the
bot is offline the response carries `"bot_online": false` and a warning, and the
command waits in the queue until the bot returns.

### Bot-side pieces

Living in the bot package because they need the live player:

- `cogs/music_system/shared_db.py` — the shared schema and accessors
- `cogs/music_system/bridge.py` — heartbeat, command executor, state mirror
- `cogs/music_system/cog.py` — starts the bridge, mirrors after every change
- `cogs/music_system/player.py` — playback clock, so position can be reported
- `cogs/music_system/youtube.py` — takes the shared download lock

## Quickstart

Run both against the same database — that is the whole point:

```bash
# terminal 1: the bot, from the repo root
.venv/Scripts/python bot.py

# terminal 2: the API
cd music-api
go build ./cmd/server
DOWNLOAD_DIR=../downloads PORT=8080 ./server
```

```bash
curl localhost:8080/v1/system/workers          # is the bot alive?
curl localhost:8080/v1/system/diagnostics      # yt-dlp / ffmpeg / cookies

# queue a song into a voice channel
curl -X POST localhost:8080/v1/guilds/<guildID>/play \
  -H 'Content-Type: application/json' \
  -d '{"query":"never gonna give you up","voice_channel_id":"<voiceChannelID>"}'

curl localhost:8080/v1/guilds/<guildID>/player # what the bot is really doing
```

`voice_channel_id` is needed only when the bot is not already connected in that
guild; once it is in a channel, the API uses that one.

Requires `yt-dlp` (PATH, `YTDLP_PATH`, the sibling `.venv`, or `python -m yt_dlp`)
and `ffmpeg` — the same dependencies the bot has.

## Endpoints

### System

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness (open, no API key) |
| GET | `/v1/system/info` | uptime, guilds, queued tracks, pending commands, cache size, `bot_online` |
| GET | `/v1/system/workers` | heartbeats for `api` and `bot` |
| GET | `/v1/system/diagnostics` | the bot's `!testmusic` |

### Resolution (answered by the API itself)

| Method | Path | Bot equivalent |
|---|---|---|
| GET | `/v1/search?q=&limit=` | `/search` |
| POST | `/v1/resolve` `{"query":"..."}` | resolve without queueing |

### Guild player — reads are mirrors, writes are commands

| Method | Path | Bot equivalent |
|---|---|---|
| GET | `/v1/guilds` | every guild the bot has a player for |
| GET | `/v1/guilds/{guildID}/player` | full live state |
| GET | `/v1/guilds/{guildID}/queue` | `/queue` |
| GET | `/v1/guilds/{guildID}/nowplaying` | `/nowplaying` |
| GET | `/v1/guilds/{guildID}/stream` | audio of the current track |
| POST | `/v1/guilds/{guildID}/play` `{"query":…,"voice_channel_id":…}` | `!play` / `/play` |
| POST | `/v1/guilds/{guildID}/skip` | `!skip` / `/skip` |
| POST | `/v1/guilds/{guildID}/pause` | `/pause` |
| POST | `/v1/guilds/{guildID}/resume` | `/resume` |
| POST | `/v1/guilds/{guildID}/stop` | `/stop` |
| POST | `/v1/guilds/{guildID}/shuffle` | `/shuffle` |
| POST | `/v1/guilds/{guildID}/mix` | `!mix` |
| DELETE | `/v1/guilds/{guildID}/queue` | `!clear` / `/clear` |
| DELETE | `/v1/guilds/{guildID}/queue/{position}` | `!remove` |
| PUT | `/v1/guilds/{guildID}/loop` `{"mode":"off\|track\|queue"}` | `/loop` |
| PUT | `/v1/guilds/{guildID}/volume` `{"percent":0-200}` | `/volume` |
| PUT | `/v1/guilds/{guildID}/autoplay` `{"enabled":true}` | `/autoplay` |
| POST | `/v1/guilds/{guildID}/autoplay/toggle` | `/autoplay` (toggle) |

`guildID` is the Discord guild id — the bot must be in that guild.

### Commands

| Method | Path | Purpose |
|---|---|---|
| GET | `/v1/commands?guild_id=&status=&limit=` | what the API asked the bot to do |
| GET | `/v1/commands/{id}` | one command's outcome |

Finished commands are purged after 24 hours.

### Download cache

| Method | Path | Purpose |
|---|---|---|
| GET | `/v1/cache/tracks?on_disk=true` | list cached tracks (the `!mix` pool) |
| POST | `/v1/cache/tracks` `{"query":"..."}` | download up front |
| GET | `/v1/cache/tracks/{videoID}` | one cache entry |
| DELETE | `/v1/cache/tracks/{videoID}` | drop row + file |
| GET | `/v1/tracks/{videoID}/stream` | stream cached audio (range requests supported) |

## Behaviour notes

- **The API resolves, the bot plays.** `POST /play` runs yt-dlp itself and
  ships the resolved tracks inside the command, so the bot queues them without
  repeating the lookup — and the HTTP response already names what was queued.
- A URL already in the cache skips extraction; a playlist URL is expanded in
  full.
- Downloads are deduplicated within a process and across processes: whoever
  loses the `download_locks` race waits for the winner's file instead of running
  a second yt-dlp onto the same path.
- The cache stays LRU-trimmed to `CACHE_LIMIT`, oldest played first — the same
  rule the bot applies, on the same table.
- Control calls are validated against the mirror first, so `pause` on an idle
  player fails immediately (409) instead of queueing a doomed command.

## Errors

Every failure is `{"error":{"code":"...","message":"..."}}`.

| Status | Codes |
|---|---|
| 400 | `bad_request`, `missing_query`, `invalid_limit`, `invalid_mode`, `invalid_volume`, `invalid_position`, `invalid_id` |
| 401 | `unauthorized` |
| 404 | `not_found`, `no_results`, `nothing_playing`, `not_cached`, `file_missing` |
| 409 | `nothing_playing`, `not_paused`, `already_paused`, `queue_empty`, `queue_too_short`, `no_cached_tracks`, `no_voice_channel` |
| 502 | `upstream_error` (yt-dlp failed) |

## Configuration

See `.env.example`. The one setting that matters most is the database: point
`DOWNLOAD_DIR` (or `DB_PATH`) at the bot's `downloads/`, or the two processes
will not see each other. Others: `PORT`/`ADDR`, `API_KEY`, `CACHE_LIMIT`,
`YTDLP_PATH`, and the cookie variables (`YOUTUBE_COOKIES_B64` >
`YOUTUBE_COOKIES_FILE` > `cookies.txt` > `COOKIES_FROM_BROWSER`) — same
precedence as the bot.

## Layout

```
cmd/server        entrypoint, heartbeat, command purge, graceful shutdown
internal/api      routes and handlers
internal/player   controller: reads the mirror, queues commands
internal/youtube  yt-dlp wrapper, cookies, cross-process download lock
internal/store    sqlite: download registry + shared control plane
internal/httpx    JSON, auth, logging, recovery
internal/config   environment loading
```

## Tests

```bash
go test ./...                      # API side
.venv/Scripts/python -m pytest -q  # bot side, from the repo root
```

The Go suite covers the store (cache, LRU eviction, mirrors, commands, locks),
the controller (state merge, validation, command payloads) and the HTTP layer
(routing, auth, streaming). The Python suite covers the bridge: mirroring,
command claim/execute/report for every action, and the download lock. Neither
suite touches the network — yt-dlp is faked. `go test -race` needs
`CGO_ENABLED=1` and a C toolchain.
