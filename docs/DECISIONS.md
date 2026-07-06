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

## 010 — Distractors: similarity ceiling, not a band; offline glosses only (2026-07)

**Decision:** Distractor selection uses only an upper similarity bound
(near-synonym exclusion); plausibility comes from matching POS and picking
pool words closest in rarity to the target. Distractor glosses are resolved
through the offline chain only (`allow_api=False`), and a question may have
fewer than four options while the store is small. Supersedes the
"similarity band" proposal in 003-era DESIGN drafts.
**Why:** A similarity floor empties the candidate pool in young databases
and adds nothing POS+rarity matching doesn't already give; the upper bound
is the part that protects fairness. Allowing API calls for pool words would
fire dozens of HTTP requests per question for marginal gain — the API stays
reserved for the one word being asked about.

## 011 — Session semantics (2026-07)

**Decision:** The review log stores the chosen gloss text as the response
(not an option index). Words for which no question can be built (no
definition anywhere, or no distractors) are auto-suspended so they stop
being served. The scheduler seam ships in phase 3 with a placeholder
(SimpleScheduler: missed words first, then new rarest-first, one correct
answer graduates a word) so the session loop runs against the real
interface before SM-2 lands.
**Why:** The gloss text keeps the log self-contained — a future RL scheduler
can see *which* distractor fooled the player even if options are regenerated
differently later. Auto-suspension prevents definition-less words from being
re-served and re-skipped forever. Building the session against the protocol
from day one is what makes phase 4 a drop-in.

## 012 — Binary SM-2 adaptation as the default scheduler (2026-07)

**Decision:** SM2Scheduler adapts classic SM-2 to PreLexy's binary outcomes:
a correct answer advances the interval ladder (1 day, 6 days, then
interval × ease) and raises ease by 0.1; a miss resets repetitions and
schedules the word for tomorrow, leaving ease unchanged (as original SM-2
does for sub-3 quality grades). Ease floor 1.3. Status becomes "known" at
the third consecutive success, but due dates alone drive what gets served.
Rows written before spacing existed (due_at NULL, status "learning") count
as immediately due. The swap from SimpleScheduler touched only the one line
in `play` that names the scheduler — the modularity requirement holds.
**Why:** SM-2's 0–5 quality grades don't fit a four-option MCQ; the binary
mapping keeps the algorithm's behaviour (growing intervals, ease
personalisation per word) without inventing fake grades. Anything cleverer
(FSRS, RL personalisation) plugs into the same seam later, trained on the
review log.

## 013 — Distractors: similarity band over all of WordNet; rarity removed (2026-07)

**Decision:** Distractor candidates are sampled from all single-word WordNet
lemmas of the target's POS and selected purely by embedding similarity inside
a (floor, ceiling) band; rarity no longer participates. Fallback when
similarity is unavailable for a pair: random same-POS candidates. Supersedes
010 (ceiling-only, store-pool, rarity-matched).
**Why:** The first real playtest showed the store-pool + rarity approach
collapses: ultra-rare literary words tie at zipf 0, so the "closest in
rarity" neighbors were always the same alphabetically-first words — which
were also the session's own words, making questions solvable by elimination.
The decisive argument against rarity: the player never sees the distractor
word, only its definition, so the hidden word's rarity contributes nothing
to how tempting its gloss is. Domain-plausibility comes from embedding
closeness — the original design intent, now viable because the WordNet-wide
pool is large enough for a similarity floor. (Owner ruling, 2026-07-06.)

## 014 — Config file; new-word ratio trumps the review backlog (2026-07)

**Decision:** A TOML config file at `$XDG_CONFIG_HOME/prelexy/config.toml`
(auto-created with commented defaults) holds `session_length` and
`new_ratio`; CLI flags override it per session. In session composition,
`new_ratio` reserves slots for new words even when a review backlog exists;
when either pool runs short the other fills the gap. New-word ordering
shuffles rarity ties per session (seedable rng) instead of falling back to
alphabetical order.
**Why:** The playtest showed a matured backlog can fill an entire session
with the exact same words — technically correct scheduling, terrible
manners. The owner wants these knobs tweakable between sessions without
editing code; stdlib `tomllib` keeps it dependency-free. Tie shuffling fixes
the "every fresh database serves 'accurse' first" determinism that zipf-0
ties created.

## 015 — Pronunciation-on-demand via the OS speech engine (2026-07)

**Decision:** Word pronunciation joins the scope (the ROADMAP audio
exclusion now covers only audio *beyond* pronunciation). `p` at the answer
prompt speaks the current word; `prelexy say <word>` works outside
sessions. Implementation: the operating system's own engine — macOS `say`,
Windows SAPI via PowerShell, Linux `espeak-ng`/`espeak` — through
subprocess, no new Python dependencies, graceful install hint when absent.
**Why:** "I don't even know how to pronounce that" was a real playtest
friction, and googling a word mid-quiz reveals its definition. OS engines
are free and offline, matching the project constraints; quality is
good enough for single words. Future upgrade: cached human recordings from
Wiktionary.

## 016 — Minimal channel-based debug facility (2026-07)

**Decision:** One tiny module (`prelexy/debug.py`): `log(channel, message)`
prints dimmed to stderr only when enabled via `prelexy --debug` or
`PRELEXY_DEBUG=1`. Channels are bare strings per subsystem; no logging
framework, no levels, no registration.
**Why:** Playtest debugging (distractor quality) needed visibility into
selection internals, and more subsystems will need the same as the game
grows (owner request: keep it expandable). Stderr keeps game output and
pipes clean; the no-ceremony design means adding diagnostics anywhere is a
one-liner, which is what makes it likely to actually happen.
