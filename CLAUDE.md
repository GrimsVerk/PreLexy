# PreLexy — Claude Code guide

Terminal vocabulary game: ingest real texts → extract the rare words →
multiple-choice practice with spaced repetition. Python 3.11, conda
(`environment.yml`) for the owner's environment and uv/`pyproject.toml` for
CI and tooling, no build step. `docs/DESIGN.md` is the authoritative
architecture reference; `docs/DECISIONS.md` is the numbered log of design
choices and owner rulings.

## Commands

- Tests (must pass before every commit): `python -m pytest`
- Full CI gate, as CI runs it: `uv run ruff check .` · `uv run ruff format
  --check .` · `uv run mypy` · `uv run pytest` (the project is clean under
  `mypy --strict`; `pyproject.toml` holds the settings)
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
- **Rolling context capture (owner ruling, DECISIONS 021):** whenever
  something surfaces in chat that a future session or a different agent
  would need, write it into the repo in the same work unit — chat is not
  storage. Route it to the file where it belongs; only create a new file
  if nothing fits, and give it an obvious purpose statement at the top.
  Routing: owner rulings & design choices → `docs/DECISIONS.md` · work
  items & ideas → `docs/BACKLOG.md` · standing operational facts →
  `docs/JOURNAL.md` Field notes · what-was-verified-where →
  `docs/VERIFICATION.md` · architecture → `docs/DESIGN.md` · session
  events & friction → `docs/JOURNAL.md` Log · user-facing behaviour →
  README/ROADMAP · working rules for agents → this file.
- Use AskUserQuestion only when truly blocked. Otherwise state what you
  need in plain chat and continue on best judgment; the owner reads chat.
- Real-model verification happens on the owner's machine: ask for
  `prelexy --debug` transcripts rather than claiming something verified,
  and keep `docs/VERIFICATION.md` up to date whenever a state changes.

## Unattended sessions

- Work the "Approved" items in `docs/BACKLOG.md` top to bottom, and keep
  going until the list is done. Do not stop and wait unless truly blocked
  on something only the owner can provide.
- **Stuck rule:** after 3–5 failed attempts at the same problem, stop
  attacking it. Log everything tried (and why it failed) in
  `docs/JOURNAL.md`, then move on to the next goal. If the stuck thing
  gates *all* other goals, build the simplest possible stand-in so the
  rest can proceed, mark it clearly (journal entry + code comment), and
  leave the real fix for the owner.
- **Friction log:** record every permission prompt, denial, or classifier
  block in the session's journal entry — this is the data for tuning the
  guardrails later.
- Every working session appends a dated entry to `docs/JOURNAL.md`:
  commits made, discoveries, friction, hand-off notes.
- Prefer separate commands over long `&&` chains: separate commands match
  the permission allowlist; chains fall through to the classifier.
