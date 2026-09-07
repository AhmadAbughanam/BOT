# BOT

A personal assistant bot that reaches me on the channel I already use (WhatsApp, Instagram DM, or email),
pulls together the information that actually matters to me from across the web and APIs, and uses an LLM to
answer in the clearest possible way. It runs unattended on a VPS and delivers scheduled briefings at set
times of day (news with breakfast, market/weather midday, a wrap-up in the evening, etc.).

## Goals

- **One channel, my choice.** Talk to the bot the same way I talk to a person: WhatsApp, Instagram, or email.
- **Signal over noise.** Aggregate from many sources, then let the LLM summarize and rank what's important to me.
- **Scheduled briefings.** Each task fires at a specific time of day, cron-style, on the VPS.
- **On-demand answers.** Ask a question any time and get an LLM answer grounded in freshly scraped / fetched data.
- **Open source first.** Prefer self-hostable, free components; keep paid APIs optional and swappable.

## High-level architecture

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐
│  Channels   │────▶│   Core /     │────▶│  LLM layer    │
│ WhatsApp    │     │   Router     │     │  (answer,     │
│ Instagram   │◀────│              │◀────│   summarize)  │
│ Email       │     └──────┬───────┘     └───────────────┘
└─────────────┘            │
                           ▼
                  ┌────────────────────┐
                  │  Data connectors   │
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
- **LLM layer** — answering, summarization, ranking. Provider-agnostic behind one interface.
- **Scheduler** — triggers briefing jobs at configured local times and pushes results to the active channel.
- **Storage** — conversation history, source cache, user preferences (what "matters to me").

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
- [ ] Summarize + rank pipeline for the morning brief.
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
