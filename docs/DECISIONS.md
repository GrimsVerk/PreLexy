# Decision log

Lightweight ADR-style log: one entry per decision, newest at the bottom. When a
decision is revisited, add a new entry that supersedes the old one — don't rewrite
history.

## 001 — Three user tiers, one engine (2026-07)

**Decision:** Design for three prioritized use cases: (1) fluent English readers
pre-learning literary vocabulary — the v1 target; (2) L2 learning from real media
(e.g., Dutch podcast transcripts); (3) future: programming/library docs.
**Why:** They share the same core loop (extract → drill → schedule). Tier 3 is
design-only for now, but no architectural choice may preclude it.

## 002 — The learning unit is a policy-defined "item", not a word (2026-07)

**Decision:** Ingestion applies a per-language extraction policy that decides what
an item is: lemmas for fluent-English mode, exact surface forms for L2 mode,
methods/functions for future code mode. Downstream code treats items as opaque.
**Why:** A fluent reader conjugates intuitively, so lemmas avoid drilling
`run/ran/running` separately. An L2 beginner should learn only what the source
actually says ("was", not the whole paradigm) to keep learning targeted;
conjugations emerge from input volume. Making this a policy keeps the tiers from
forcing incompatible pipelines.

## 003 — `language` is a namespace that includes programming languages (2026-07)

**Decision:** `python` (or `pandas-docs`, etc.) is just another `language` value on
items and sources.
**Why:** Tier 3 then needs only a new extraction policy and a new embedding
source — zero schema or engine changes.

## 004 — SQLite over JSON saves (2026-07)

**Decision:** One SQLite database file (stdlib `sqlite3`) behind a thin storage
module; no ORM.
**Why:** The model is relational from day 1 — occurrences with context sentences
(~80k tokens for one novel), cached definitions, multiple profiles, and an
append-only review log. JSON handles the profile save alone, but retrofitting the
rest later is the expensive path. SQLite adds no dependency and keeps everything
in one file.

## 005 — Scheduler behind an interface, owning an opaque state blob (2026-07)

**Decision:** A `Scheduler` protocol (`next_items`, `record_review`); per-item
scheduler state is an opaque JSON blob in `item_state.scheduler_state`, with
`due_at` as the only scheduler output core code reads. Default algorithm: SM-2.
**Why:** The scheduler must be swappable without touching other code — the
long-term idea is an RL scheduler personalized per player. "Ebbinghaus curve" is a
concept, not an algorithm; SM-2 is the simple, battle-tested stand-in until then.
The opaque blob means swapping algorithms is config, not a migration.

## 006 — Append-only review log from day 1 (2026-07)

**Decision:** Every answer is recorded as an event (timestamp, exercise, response,
correct, latency) in `review_log`, never overwritten.
**Why:** A future RL/personalized scheduler needs per-review history as training
data; aggregate state can't be un-aggregated later. Recording it now is nearly
free.

## 007 — Offline-first, free-only definition chain (2026-07)

**Decision:** Definition lookup: WordNet (offline) → local `senses` cache → free
keyless API (dictionaryapi.dev), with API results cached so each word is fetched
at most once. The project uses no paid sources or APIs, ever.
**Why:** PreLexy must be entirely free and usable offline. WordNet is weak on
rare/literary words, so the cached fallback matters; Wiktionary extracts
(kaikki.org) are the noted upgrade path and the likely bilingual source for L2
mode.

## 008 — Dictionary-membership as the noise filter (2026-07)

**Decision:** A candidate item must be found in the dictionary chain to be
offered as vocabulary; unknown tokens are quarantined, and deep OCR repair is out
of scope.
**Why:** The committed Dorian Gray scan is imperfect OCR ("|" for "I", etc.).
Membership filtering removes that garbage as a side effect of a check we need
anyway; input text quality remains the user's responsibility, not core scope.

## 009 — wordfreq for rarity ranking; Zipf score stored in item metadata (2026-07)

**Decision:** Candidates are ranked by wordfreq's Zipf frequency scale (rarest
first), computed once at ingest and stored in `items.metadata` as
`{"zipf": …}`. wordfreq is added as a dependency (pip).
**Why:** Modern spaCy models no longer ship lexeme probabilities and WordNet
has no frequency data, so a frequency source is needed. wordfreq is free,
offline (data bundled), and covers Dutch and many other languages — so the
same ranking works for tier 2. Storing the score at ingest keeps later queries
free of the dependency.
