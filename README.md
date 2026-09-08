# BOT

A personal assistant bot I talk to on **Telegram**. It pulls together the information that actually
matters to me — from a fixed registry of sites and from my own email — runs everything through a
self-evaluating refine loop, and delivers scheduled briefings. It runs unattended on a VPS and fires
each task at a set time of day (news with breakfast, markets midday, a wrap-up in the evening).

## Goals

- **One channel: Telegram.** I send commands and receive briefings there. Email and Instagram are secondary.
- **Email triage.** The bot has read access to my mailbox and filters, groups, and summarizes it the way I ask
  ("show me anything from recruiters this week", "every morning summarize unread mail, skip newsletters").
- **Signal over noise.** Every answer and brief goes through a self-evaluating refine loop: draft → score its
  own output against eval-style criteria → revise → repeat. When the loop ends, only the highest-scoring draft is sent.
- **Hosted LLMs, free tiers first.** Call APIs (OpenRouter, Groq, Gemini …) in a fallback chain. Only drop to a
  local Ollama model when every hosted provider is rate-limited.
- **Locked scraping registry.** No open-web crawling. The bot works from a fixed list of sites, searches each
  one's own search bar for a title/keywords, and files results under categories / subcategories.
- **Scheduled briefings.** Each task fires at a specific time of day, cron-style, on the VPS.
- **Python only.** FastAPI service, PostgreSQL + pgvector for storage and semantic search.

## High-level architecture

```
┌─────────────┐     ┌──────────────┐     ┌────────────────────────────┐
│  Channels   │────▶│   Core /     │────▶│  LLM layer                 │
│ Telegram    │     │   Router     │     │  provider chain:           │
│  (primary)  │◀────│              │◀────│   Groq → Gemini →          │
│ Email       │     └──────┬───────┘     │   OpenRouter → … → Ollama  │
│ Instagram   │            │             │  ┌──────────────────────┐  │
└─────────────┘            │             │  │ refine loop:         │  │
                           ▼             │  │ draft → self-eval →  │  │
        ┌──────────────────┴──────────┐  │  │ revise → repeat →    │  │
        │  Data sources               │  │  │ pick best-scoring    │  │
        │  • scraping (locked site    │  │  └──────────────────────┘  │
        │    registry, Playwright)    │  └────────────────────────────┘
        │  • email (IMAP read+filter) │
        │  • connectors: weather,     │
        │    finance, RSS feeds       │
        └──────────────┬──────────────┘
                       ▼
        ┌──────────────────────────────┐
        │  PostgreSQL + pgvector        │
        │  items, embeddings, emails,   │
        │  messages, briefs, traces     │
        └──────────────┬───────────────┘
                       ▲
              ┌────────┴───────┐
              │  Scheduler     │  cron: breakfast news, email digest, …
              └────────────────┘
```

- **Channels** — Telegram is primary (commands + briefings). Email is both a data source and a delivery target. Instagram is optional later.
- **Core / Router** — normalizes incoming messages, decides intent (question / command / email-filter request), calls data sources + LLM, formats the reply.
- **LLM layer** — a provider chain of hosted free-tier APIs with a local Ollama fallback, wrapped in the refine loop.
- **Data sources** — the locked scraping registry, the email reader/filter, and API connectors (weather, finance, RSS).
- **Storage** — PostgreSQL with the pgvector extension for embeddings / semantic search and dedup.
- **Scheduler** — system cron triggers briefing jobs at configured local times and pushes results to Telegram (or email).

## Channels

| Channel | Role | Library |
| --- | --- | --- |
| **Telegram** | Primary. I send commands, get briefings and answers. | `python-telegram-bot` (or `aiogram`), webhook into FastAPI |
| **Email** | Data source: read + filter my mailbox. Also a delivery target for briefings. | IMAP via `aioimaplib` / `imaplib`; SMTP for sending; Gmail API optional |
| **Instagram** | DM poller — reads new direct messages and answers through the same router. | `instagrapi` (optional extra) |

### Instagram DM poller

- Instagram has no webhook for personal accounts, so `python -m bot.channels.instagram poll [--loop]`
  polls the DM inbox (systemd unit `bot-instagram.service` runs it continuously on the VPS).
- Each new inbound message runs through `route()` exactly like a Telegram message; the reply is sent
  back in the same thread, trimmed to 1000 chars.
- A per-thread cursor in `channel_cursors` tracks the last processed message id so restarts don't
  re-answer. Allowlist via `INSTAGRAM_ALLOWED_USER_IDS`; `instagrapi` session is cached to
  `INSTAGRAM_SESSION_PATH`.

### Email access & filtering

- **Read access** to my mailbox over IMAP (app password, or OAuth for Gmail). Read-first: the bot never
  deletes or sends without an explicit confirmation step.
- The bot can: list / search messages, apply filters I describe in natural language, group by sender or
  topic, summarize threads, extract action items, flag important senders, and draft (not auto-send) replies.
- Natural-language filters compile to an **IMAP search query** for the cheap first pass, then an **LLM
  post-filter** for the fuzzy part ("skip newsletters", "only things that need a reply").
- Example request: *"Every morning, summarize unread mail from the last 24h, group by sender, skip
  newsletters and receipts, and list anything that looks like it needs a reply."*
- Only message **metadata + generated summaries** are cached in Postgres; full bodies are fetched on demand.

## LLM layer — hosted first, local fallback

An ordered **provider chain**. Each request tries providers top to bottom until one succeeds inside its
free-tier limits; on `429` / quota / auth errors it falls through to the next. Local Ollama is last and is
only reached when every hosted provider is exhausted.

| Priority | Provider | Notes |
| --- | --- | --- |
| 1 | **Groq** | Free tier, very fast; Llama / Qwen / GPT-OSS models. ("grock" = Groq; xAI's Grok API has no real free tier, so it's skipped.) |
| 2 | **Google Gemini** | Free tier (Gemini Flash), generous daily quota |
| 3 | **OpenRouter** | Free models via the `:free` suffix; rotates upstream providers |
| 4 | **Cerebras / others** | Optional extra free tiers, easy to add as more adapters |
| 5 *(fallback)* | **Local Ollama** | Only when all hosted providers are rate-limited. Smaller model (e.g. `llama3.1:8b` / `qwen2.5:7b`), slower, no quota |

- One `LLMProvider` interface; each provider is a thin adapter (chat, embeddings where supported).
- Config lives in `.env` + `config/schedule.yaml`: `llm.chain` is the ordered list, each entry has an API
  key ref, model id, and rpm / rpd caps.
- A local `llm_usage` table tracks per-provider request/token counts so the chain can **pre-empt** a limit
  rather than wait for a `429`.
- The refine loop's **judge step** can pin a specific (stronger) provider regardless of chain order.
- Embeddings: prefer a hosted free embedding endpoint (Gemini / OpenRouter); fall back to a local Ollama
  embedding model. Vectors are stored in pgvector.

## Refine loop (self-evaluation)

Every answer and every scheduled brief goes through the same loop instead of being sent on the first pass:

1. **Draft.** The agent produces a candidate answer from the source data.
2. **Self-eval.** The agent scores its own draft against explicit criteria — the same criteria we'd write
   in an eval set: factual grounding in the sources, relevance to my stated interests, no filler, correct
   dates / numbers, right length for the channel. Output is a numeric score plus concrete critique.
3. **Revise.** The agent rewrites the draft to address its own critique.
4. **Repeat** steps 2–3 until either the score clears a threshold or a max iteration count is hit.
5. **Send best.** Once the loop ends, the highest-scoring draft across all iterations is what gets sent —
   not necessarily the last one.

Config knobs (in `config/schedule.yaml`, per task, plus a global default):

| Knob | Meaning |
| --- | --- |
| `loop.max_iterations` | Hard cap on draft→revise cycles (e.g. 3) |
| `loop.score_threshold` | Stop early once a draft scores at/above this |
| `loop.criteria` | The checklist the self-eval scores against |
| `loop.judge_model` | Optional separate/stronger provider+model for the scoring step |
| `loop.keep_traces` | Persist every draft + score to `loop_traces` for later inspection |

Notes: the scoring step can use a second model as an LLM-judge to reduce the "grades its own homework"
bias; all drafts and scores are logged so the loop's behaviour can itself be evaluated offline.

## Scraping — locked site registry

The bot does **not** crawl the open web. It works from a fixed registry of sites in `config/sites.yaml`.
For a given query/title it:

1. Selects the sites whose category matches the request.
2. Opens each site and **uses that site's own on-page search bar** (driven by Playwright) to search the
   title / keywords — or hits the site's search URL directly when a template is known.
3. Extracts the top results: title, URL, published date, snippet.
4. Runs the batch through the refine loop for summarization and ranking.
5. Saves them to Postgres tagged with **category / subcategory**, plus an embedding in pgvector for
   semantic search and dedup.

### Category design

Two levels: a top-level `category` and a `subcategory`. Each registry entry is filed under exactly one pair.

| Category | Subcategories |
| --- | --- |
| `news` | `world`, `mena`, `politics`, `economy` |
| `tech` | `ai`, `software`, `hardware`, `startups` |
| `markets` | `equities`, `crypto`, `commodities`, `macro` |
| `science` | `ai-research`, `space`, `health`, `climate` |
| `learning` | `tutorials`, `docs`, `courses` |
| `personal` | `jobs`, `realestate`, `deals` |

The list is config, not code — add categories/subcategories in `config/sites.yaml` and the DB `sources`
table mirrors it on startup.

### Site registry entry

```yaml
sites:
  - id: hn
    name: Hacker News
    base_url: https://news.ycombinator.com
    category: tech
    subcategory: software
    search:
      mode: url_template               # url_template | search_bar
      url_template: "https://hn.algolia.com/?q={query}&sort=byPopularity"
      result_selector: "a.Story_link"

  - id: reuters
    name: Reuters
    base_url: https://www.reuters.com
    category: news
    subcategory: world
    search:
      mode: search_bar
      open_search_selector: "button[aria-label='Open search bar']"
      input_selector: "input[name='query']"
      submit_key: "Enter"
      result_selector: "a[data-testid='TitleLink']"
```

- `mode: search_bar` → Playwright clicks the search control, types the query, submits, scrapes results.
- `mode: url_template` → skip the UI and request the site's search URL directly (preferred when it exists).
- `result_selector` → CSS selector for result links on the results page.
- Politeness: per-site rate limit, response cache, and respect for each site's `robots.txt` / ToS.

## Data model (PostgreSQL + pgvector)

| Table | Purpose |
| --- | --- |
| `sources` | The site registry, mirrored from `config/sites.yaml` (id, name, base_url, category, subcategory, search config). |
| `items` | Collected entries: title, url, published_at, raw_text, summary, category, subcategory, source_id, fetched_at. |
| `item_embeddings` | `vector` column (pgvector) for semantic search and dedup against `items`. |
| `emails` | Metadata + generated summary of processed mail (message_id, from, subject, date, labels, summary). No full bodies. |
| `messages` | Telegram conversation history for context. |
| `briefs` | Generated briefings and which `items` / `emails` they cited. |
| `loop_traces` | Refine-loop drafts + scores per run (when `loop.keep_traces`). |
| `llm_usage` | Per-provider request / token counters for limit tracking. |

SQLAlchemy 2.x models; Alembic migrations; the pgvector extension enabled via the first migration.

## Project structure

```
BOT/
├── README.md
├── pyproject.toml
├── .env.example                 # documented config keys, no secrets
├── docker-compose.yml           # postgres + pgvector for local dev
├── config/
│   ├── schedule.example.yaml    # task -> time-of-day + per-task loop knobs
│   └── sites.example.yaml       # locked scraping registry
├── src/bot/
│   ├── main.py                  # FastAPI app: Telegram webhook, health, admin
│   ├── core/                    # router, intent detection, reply formatting
│   ├── channels/               # telegram/, email/, instagram/
│   ├── llm/                     # provider chain + adapters: groq, gemini, openrouter, ollama
│   ├── refine/                  # draft / self-eval / revise loop + criteria
│   ├── connectors/             # weather/, finance/, feeds/
│   ├── scraping/               # playwright runner, site registry, result extractors
│   ├── storage/                # SQLAlchemy models, pgvector helpers
│   └── scheduler/             # cron job definitions + `python -m bot.scheduler` runner
├── alembic/                     # DB migrations
├── tests/
└── deploy/                      # systemd units / docker-compose / cron snippets
```

## Tech choices

| Concern | Choice |
| --- | --- |
| Language | Python 3.12 |
| Web framework | FastAPI + Uvicorn |
| Telegram | `python-telegram-bot` (or `aiogram`), webhook |
| Email | IMAP via `aioimaplib` / `imaplib`; SMTP for sending; Gmail API optional |
| LLM (hosted) | Groq, Google Gemini, OpenRouter — free tiers, in a fallback chain |
| LLM (fallback) | Local Ollama (`llama3.1:8b` / `qwen2.5:7b`) — only when hosted limits are hit |
| Scraping | Playwright (Python) + `selectolax` / BeautifulSoup + `trafilatura` for article extraction |
| Feeds | `feedparser` for RSS/Atom |
| Database | PostgreSQL 16 |
| Vector store | `pgvector` extension (no separate vector DB) |
| ORM / migrations | SQLAlchemy 2.x + Alembic |
| Scheduling | system `cron` on the VPS calling `python -m bot.scheduler run <task>`; APScheduler optional in-process |
| Process mgmt | `systemd` unit for the API, or Docker Compose |
| Secrets | git-ignored `.env`; `sops` / `age` optional |

## Scheduled tasks (example)

Configured in `config/schedule.yaml` (local VPS time). Each task runs through the refine loop and is
delivered to Telegram unless it names another channel.

| Time | Task | Output |
| --- | --- | --- |
| 07:00 | Email digest | Unread mail from the last 24h, grouped by sender, newsletters skipped, replies-needed flagged |
| 07:30 | Morning news brief | Top items from the `news` + `tech` registry, refine-loop summarized and ranked |
| 08:00 | Weather + agenda | Today's forecast (weather connector) |
| 13:00 | Markets / watchlist | Movers from the `markets` registry + finance connector, one-line "why" each |
| 21:00 | Daily wrap | What I asked about today, flagged follow-ups, anything new in `personal` |

## Roadmap

**Phase 1 — foundation** (branch `phase-1-foundation`)

- [x] FastAPI skeleton + Telegram webhook echo.
- [x] PostgreSQL + pgvector via docker-compose; SQLAlchemy models + first Alembic migration.

**Phase 2 — LLM layer + refine loop** (branch `phase-2-llm-refine`)

- [x] LLM provider chain: Groq → Gemini → OpenRouter adapters, `llm_usage` tracking, Ollama fallback.
- [x] Refine loop: draft → self-eval/score → revise → pick best, with config knobs and `loop_traces`.
- [x] Telegram handler answers free text via the chain + refine loop (`/start`, `/help` commands).

**Phase 3 — router + email** (branch `phase-3-router-email`)

- [x] Core router + intent detection (command / email / question) dispatching to canned replies, the email digest, or the refine loop.
- [x] Email reader: read-only IMAP, natural-language → IMAP search + LLM post-filter, digest summary, headers persisted into `emails`.

**Phase 4 — scraping** (branch `phase-4-scraping`)

- [x] Locked site registry loader (`config/sites.yaml`), `mirror_to_db` into `sources`, category/subcategory filtering.
- [x] Playwright runner with `url_template` and `search_bar` modes (lazy import; injectable for tests), result extractors + URL dedup.
- [x] `ScrapingService.collect` persists new `items` tagged with category/subcategory/source; `python -m bot.scraping` CLI.
- [x] New `search` intent — Telegram "latest on X" scrapes the registry and answers via the refine loop grounded in the results.

**Phase 5 — scheduler + connectors** (branch `phase-5-scheduler-connectors`)

- [x] Connectors: `weather` (Open-Meteo, keyless), `finance` (Stooq + CoinGecko, keyless), `feeds` (RSS via feedparser) — each with an injectable HTTP getter.
- [x] Scheduler: `run_task` dispatches by `source` (email / scraping / connector / core-recap), persists a `Brief`, delivers to `TELEGRAM_DEFAULT_CHAT_ID`.
- [x] `python -m bot.scheduler` CLI — `list`, `run <task> [--no-deliver]`, `crontab` (renders one cron line per timed task).

**Phase 6 — embeddings + semantic dedup** (branch `phase-6-embeddings`)

- [x] `embed` on the Gemini / Ollama / OpenAI-compatible providers; `EmbeddingChain` reads `llm.embeddings` and falls through like the chat chain.
- [x] pgvector helpers (`storage/vectors.py`): cosine, nearest-neighbour, `has_semantic_duplicate`, `embed_and_store`, `backfill_embeddings`; HNSW cosine index (migration `0002`).
- [x] `ScrapingService` embeds new `items` and drops near-duplicates (cosine ≤ `SEMANTIC_DEDUP_THRESHOLD`) against stored + in-batch vectors; best-effort, falls back to URL dedup. `python -m bot.scraping --embed-backfill`.

**Phase 7 — VPS deploy** (branch `phase-7-vps-deploy`)

- [x] `deploy/`: `bot-api` systemd unit (restart-on-failure), `bot-task@` oneshot, nginx + certbot config scoped to `/telegram/webhook`, cron file, logrotate, `deploy.sh` update script, runbook.
- [x] `Dockerfile` (Playwright base) + `docker compose --profile full` runs the API container.
- [x] File logging (`LOG_FILE`), `APP_ENV`, `/` version endpoint; `configure_logging()` shared by the app and both CLIs.

**Phase 8 — Instagram** (branch `phase-8-instagram`)

- [x] `instagrapi` DM client (lazy import, optional `bot[instagram]` extra) + `poll_once()` that runs new
      inbound messages through `route()` and replies in-thread.
- [x] `channel_cursors` table (migration `0003`) tracks the last processed message id per thread; allowlist + session caching.
- [x] `python -m bot.channels.instagram poll [--loop]` CLI and `bot-instagram.service` systemd unit.

All roadmap items are built; further work is enhancements (email body fetch / reply drafting, `loop.judge_model`, more sites/connectors).

## Development

```bash
pip install -e ".[dev]"                 # or: uv sync
playwright install chromium             # browser for the scraping runner
cp .env.example .env                    # fill in TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET, DATABASE_URL
docker compose up -d db                 # PostgreSQL + pgvector
alembic upgrade head                    # create the schema (enables the vector extension)
python -m bot.scraping --mirror         # sync config/sites.yaml into the sources table
uvicorn bot.main:app --app-dir src --reload

pytest                                  # unit tests (no DB or browser needed)

# register the webhook once the API is reachable over HTTPS:
python scripts/set_telegram_webhook.py https://your-host/telegram/webhook
```

In local dev, expose the API with a tunnel (e.g. `cloudflared tunnel --url http://localhost:8000`)
and point `set_telegram_webhook.py` at the tunnel URL.

## Deployment

Full runbook in [`deploy/README.md`](deploy/README.md). In short, on a VPS with the repo at `/srv/bot`:

- **API**: `deploy/systemd/bot-api.service` runs `uvicorn` on `127.0.0.1:8000` with `Restart=on-failure`.
- **nginx + TLS**: `deploy/nginx/bot.conf` proxies only `/telegram/webhook` and `/health`; `certbot --nginx` for the cert.
- **Briefings**: `deploy/cron/bot.cron` (regenerate with `python -m bot.scheduler crontab …`) → `crontab -u bot`.
- **Logs**: set `LOG_FILE=/srv/bot/logs/bot.log`; `deploy/logrotate/bot` rotates it weekly.
- **Updates**: `deploy/deploy.sh` — pull, reinstall, `alembic upgrade head`, re-mirror the registry, restart.
- **Container route**: `docker compose --profile full up -d` builds the API from `Dockerfile` alongside Postgres.
- Config and secrets in a git-ignored `.env`; never committed.

## Notes

- Free-tier limits and model names change often — keep `llm.chain` and the per-provider caps in config, not code.
- `loop.judge_model` is parsed but not yet wired — the refine loop currently scores with the same provider chain.
- The email reader currently works from message headers only (from / subject / date / message-id); body fetch and reply drafting are a later step.
- The Telegram webhook needs a public HTTPS endpoint; in dev use a tunnel (e.g. cloudflared) or long polling.
- Scraping is limited to the locked registry; respect each site's `robots.txt` and terms, cache aggressively,
  and rate-limit per site.
- Email is read-first: the bot never sends, moves, or deletes a message without an explicit confirmation.
- Embeddings and semantic dedup are best-effort — if no embedding provider is reachable, scraping falls back to plain URL dedup and stores items unembedded (run `--embed-backfill` later).
- This README is the working spec and will change as decisions get made.
