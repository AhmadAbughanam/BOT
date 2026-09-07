# BOT

A personal assistant bot that reaches me on the channel I already use (WhatsApp, Instagram DM, or email),
pulls together the information that actually matters to me from across the web and APIs, and uses an LLM to
answer in the clearest possible way. It runs unattended on a VPS and delivers scheduled briefings at set
times of day (news with breakfast, market/weather midday, a wrap-up in the evening, etc.).

## Goals

- **One channel, my choice.** Talk to the bot the same way I talk to a person: WhatsApp, Instagram, or email.
- **Signal over noise.** Aggregate from many sources, then run a self-evaluating refine loop: the agent
  drafts an answer, scores its own output against explicit criteria (eval-style), revises, and repeats.
  When the loop ends, only the highest-scoring draft is sent.
- **Scheduled briefings.** Each task fires at a specific time of day, cron-style, on the VPS.
- **On-demand answers.** Ask a question any time and get an LLM answer grounded in freshly scraped / fetched data.
- **Open source first.** Prefer self-hostable, free components; keep paid APIs optional and swappable.

## High-level architecture

```
┌─────────────┐     ┌──────────────┐     ┌────────────────────────────┐
│  Channels   │────▶│   Core /     │────▶│  LLM layer                 │
│ WhatsApp    │     │   Router     │     │  ┌──────────────────────┐  │
│ Instagram   │◀────│              │◀────│  │ refine loop:         │  │
│ Email       │     └──────┬───────┘     │  │ draft → self-eval →  │  │
└─────────────┘            │             │  │ revise → repeat →    │  │
                           ▼             │  │ pick best-scoring    │  │
                  ┌────────────────────┐ │  └──────────────────────┘  │
                  │  Data connectors   │ └────────────────────────────┘
                  │  news / weather /  │
                  │  finance / custom  │
                  │  scrapers / APIs   │
                  └────────────────────┘
                           ▲
                  ┌────────┴───────┐
                  │  Scheduler     │  (cron: breakfast news, etc.)
                  └────────────────┘
```

- **Channels** — adapters that receive messages and send replies. One is active at a time to start.
- **Core / Router** — normalizes incoming messages, decides intent (question vs. command), calls connectors + LLM, formats the reply.
- **Data connectors** — pluggable modules for news, weather, finance, calendar, and site-specific scrapers.
- **LLM layer** — answering and summarization behind a provider-agnostic interface, wrapped in the **refine loop** below.
- **Scheduler** — triggers briefing jobs at configured local times and pushes results to the active channel.
- **Storage** — conversation history, source cache, user preferences (what "matters to me"), and per-run loop traces (drafts + scores) for debugging.

## Refine loop (self-evaluation)

Every answer and every scheduled brief goes through the same loop instead of being sent on the first pass:

1. **Draft.** The agent produces a candidate answer from the connector data.
2. **Self-eval.** The agent scores its own draft against explicit criteria — the same criteria we'd
   write in an eval set: factual grounding in the sources, relevance to my stated interests, no filler,
   correct dates/numbers, right length for the channel. Output is a numeric score plus concrete critique.
3. **Revise.** The agent rewrites the draft to address its own critique.
4. **Repeat** steps 2–3 until either the score clears a threshold or a max iteration count is hit.
5. **Send best.** Once the loop ends, the highest-scoring draft across all iterations is what gets sent —
   not necessarily the last one.

Config knobs (in `config/schedule.yaml` per task, plus a global default):

| Knob | Meaning |
| --- | --- |
| `loop.max_iterations` | Hard cap on draft→revise cycles (e.g. 3) |
| `loop.score_threshold` | Stop early once a draft scores at/above this |
| `loop.criteria` | The checklist the self-eval scores against |
| `loop.judge_model` | Optional separate/stronger model for the scoring step |
| `loop.keep_traces` | Persist every draft + score for later inspection |

Notes: the scoring step can use a second model as an LLM-judge to reduce the "grades its own homework"
bias; all drafts and scores are logged so the loop's behaviour can itself be evaluated offline.

## Candidate open-source / tooling choices

Nothing here is locked in yet — this is the shortlist to evaluate.

| Concern | Options to evaluate |
| --- | --- |
| Language / runtime | Python (async) or Node.js |
| WhatsApp | WhatsApp Cloud API (official), or `whatsapp-web.js` / Baileys (unofficial) |
| Instagram | Instagram Graph API (Messaging), or `instagrapi` for read-heavy tasks |
| Email | IMAP/SMTP via standard libs, or a service like a self-hosted Postfix + fetch loop |
| LLM | Local via Ollama (Llama 3.x, Qwen, Mistral); hosted (Claude, OpenAI) as optional backends |
| Orchestration | LangChain / LlamaIndex, or a thin custom layer |
| Scraping | `httpx` + `selectolax`/`BeautifulSoup`, Playwright for JS-heavy sites, `trafilatura` for article extraction |
| Feeds | `feedparser` for RSS/Atom |
| Scheduling | system `cron` on the VPS, or APScheduler / `node-cron` in-process |
| Vector store (optional) | Chroma, Qdrant, or SQLite + `sqlite-vec` |
| Process mgmt on VPS | `systemd` units, or Docker Compose + `pm2` |
| Secrets | `.env` (git-ignored), or `sops` / `age` for encrypted config |

## Planned project structure

```
BOT/
├── README.md
├── .gitignore
├── .env.example            # documented config keys, no secrets
├── config/
│   └── schedule.example.yaml   # task -> time-of-day mappings
├── src/
│   ├── core/               # router, intent, reply formatting
│   ├── channels/           # whatsapp/, instagram/, email/
│   ├── connectors/         # news/, weather/, finance/, scrapers/
│   ├── llm/                # provider interface + implementations
│   ├── refine/             # draft/self-eval/revise loop + scoring criteria
│   ├── scheduler/          # job definitions + runner
│   └── storage/            # db models, cache
├── tests/
└── deploy/                 # systemd units / docker-compose / cron snippets
```

## Scheduled tasks (example)

Configured in `config/schedule.yaml` (local VPS time):

| Time | Task | Output |
| --- | --- | --- |
| 07:30 | Morning news brief | Top headlines in my topics, LLM-summarized, ranked |
| 08:00 | Weather + calendar | Today's forecast and agenda |
| 13:00 | Markets / watchlist | Movers and one-line "why" |
| 21:00 | Daily wrap | What I asked about today + anything I flagged for follow-up |

## Roadmap

- [ ] Pick language + one channel to build first (leaning: email or WhatsApp).
- [ ] Core router with a stubbed LLM and one connector (RSS news).
- [ ] LLM provider interface + local Ollama backend.
- [ ] Refine loop: draft → self-eval/score → revise → pick best, with config knobs and trace logging.
- [ ] Summarize pipeline for the morning brief, run through the refine loop.
- [ ] Scheduler wired to the active channel.
- [ ] Add weather + finance connectors.
- [ ] Persistence for history and preferences.
- [ ] Playwright-based scraper for a couple of specific sites.
- [ ] VPS deploy: systemd/Docker, log rotation, restart-on-failure.
- [ ] Second channel adapter.

## Development

```bash
# clone, then:
cp .env.example .env        # fill in keys
# (setup steps depend on chosen runtime — TBD)
```

## Deployment (target)

- Runs on a personal VPS, always-on.
- Briefing jobs via `cron` or an in-process scheduler.
- Restart-on-failure via `systemd` or the container runtime.
- Config and secrets via a git-ignored `.env`; never committed.

## Notes

- Unofficial channel libraries (WhatsApp Web, `instagrapi`) can break or risk account limits — treat official APIs as the preferred path where feasible.
- Respect target sites' terms and rate limits when scraping; cache aggressively.
- This README is the working spec and will change as decisions get made.
