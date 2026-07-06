# PreLexy — Claude Code guide

Terminal vocabulary game: ingest real texts → extract the rare words →
multiple-choice practice with spaced repetition. Python 3.11, conda
(`environment.yml`), no build step. `docs/DESIGN.md` is the authoritative
architecture reference; `docs/DECISIONS.md` is the numbered log of design
choices and owner rulings.

## Commands

- Tests (must pass before every commit): `python -m pytest`
- Run: `python -m prelexy [--debug] {ingest,words,question,play,say,clean}`
- Sandbox first run: `pip install click nltk spacy wordfreq pytest`
  (the conda env is not available there). NLTK data and PyPI download fine;
  **spaCy models cannot be downloaded** (GitHub releases are blocked) — the
  one model-dependent test skips, and anything needing real vectors is
  verified on the owner's machine instead.

## Architecture map

- `prelexy/store.py` — ALL SQL lives here; nothing else touches the DB
- `prelexy/textproc.py` — extraction pipeline (spaCy); per-language item policy
- `prelexy/definitions.py` — gloss chain: senses cache → WordNet → free API (cached)
- `prelexy/mcq.py` — question building; distractor band on gloss-vs-gloss similarity
- `prelexy/similarity.py` — SimilarityProvider seam (swappable embeddings)
- `prelexy/scheduler.py` — Scheduler seam; SM-2 default; opaque `scheduler_state` blob
- `prelexy/session.py`, `cli.py`, `config.py`, `speech.py`, `clean.py`, `debug.py`

## Hard rules

1. Work on branch `claude` and push there. **NEVER push to or merge into
   main** unless the owner explicitly says so in the current conversation.
2. When working autonomously, implement **only** items in the "Approved"
   section of `docs/BACKLOG.md`. New ideas are described in chat and added
   to BACKLOG "Proposed" — never coded straight away.
3. Owner rulings recorded in `docs/DECISIONS.md` are never silently
   reversed. If one seems wrong, argue the case in chat and wait.
4. Entirely free and offline-first: no paid services ever; free APIs only
   as a cached fallback; no new dependencies without asking.
5. Keep the seams: scheduler and similarity stay swappable behind their
   protocols; rarity must never influence distractor selection (ruling
   013); no change may preclude tier 2 (Dutch from media) or tier 3
   (programming docs, custom embeddings).

## Conventions

- One conceptually contained commit per unit of work, pushed after each.
- Docs move with code: update README / ROADMAP / docs/DESIGN.md in the same
  commit, and add a docs/DECISIONS.md entry (newest at the bottom) for
  every design choice or owner ruling.
- Tests accompany code. The suite never touches the network (see the
  `no_network` autouse fixtures); model-dependent tests skip gracefully.
- Diagnostics go through `prelexy/debug.py` — add a channel, don't invent a
  new mechanism.
- Use AskUserQuestion only when truly blocked. Otherwise state what you
  need in plain chat and continue on best judgment; the owner reads chat.
- Real-model verification happens on the owner's machine: ask for
  `prelexy --debug` transcripts rather than claiming something verified.
