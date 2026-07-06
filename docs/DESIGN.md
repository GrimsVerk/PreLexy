# Design

Status: pre-implementation draft. Items marked **(proposed)** are defaults chosen to
unblock development; the reasoning behind settled choices lives in
[DECISIONS.md](DECISIONS.md).

## Overview

PreLexy is an ingestion pipeline feeding a game loop:

```
text file → ingest: tokenize → extraction policy → filter → rank → store (SQLite)
                                                                      ↓
player ← terminal session ← MCQ generator ← scheduler picks due + new items
```

Three constraints shape everything:

1. **Three user tiers share one engine** — fluent reader (English literature),
   L2 learner (e.g., Dutch from podcast transcripts), and, in the future, a
   programmer learning library APIs from docs.
2. **The scheduler is swappable** without touching any other code (a future
   RL-personalized scheduler is the motivating case).
3. **Free and offline-first.**

## The item abstraction

The unit of learning is an **item**, not a "word". What counts as an item is decided
at ingest time by a per-language **extraction policy**:

| Tier | Language | Policy |
|------|----------|--------|
| 1 — fluent reading | `en` | lemma (`running` → `run`); a fluent reader conjugates intuitively |
| 2 — L2 from zero | `nl`, … | exact surface form: if the podcast only ever says "was", only "was" is practiced — targeted, not overwhelming; conjugation patterns emerge from input volume |
| 3 — code docs (future) | `python`, … | methods/functions (`list.pop`), via custom tokenization |

Everything downstream of ingestion — MCQ generation, scheduler, session loop,
storage — treats items as opaque and never re-tokenizes or normalizes. `language`
is a namespace, and a programming language is just another value of it; tier 3
requires no new structure, only a new policy and a new embedding source.

## Data model (SQLite)

Single database file, **(proposed)** at a platform-appropriate user data dir
(e.g. `~/.local/share/prelexy/prelexy.db`), accessed only through a thin storage
module (`prelexy/store.py`) so nothing else touches SQL directly. SQLite is stdlib
(`sqlite3`), so it adds no dependency.

Three separated concerns:

### Content — derived from input texts, profile-independent

- **`sources`** — one row per ingested text: `id`, `title`, `language`,
  `kind` (book / subtitles / transcript / docs), `path`, `added_at`
- **`items`** — the learnable units: `id`, `language`, `form` (the string as
  practiced), `lemma` (nullable), `pos` (nullable), `metadata` (JSON — future code
  items put module/signature here without schema changes). Unique on
  (`language`, `form`).
- **`occurrences`** — `item_id`, `source_id`, `context` (the sentence it appeared
  in), `position`. Provides example sentences for exercises and frequency counts
  for ranking.

### Knowledge — shared, cacheable

- **`senses`** — cached definitions: `id`, `item_id`, `gloss`, `gloss_language`
  (English definitions for tier 1; the learner's strong language for tier 2),
  `provider` (`wordnet` / `api` / `wiktionary`), `fetched_at`. API lookups land
  here, so offline coverage improves with use.

### Learner — per profile, mutable

- **`profiles`** — `id`, `name`, `settings` (JSON: active languages, strong
  language, session length, …). Multiple users on one machine are just rows here.
- **`item_state`** — per profile × item: `status`
  (new / learning / known / suspended), **`due_at`** (first-class column — the only
  thing the session loop reads to find due reviews), `scheduler_state` (opaque JSON
  blob **owned by the scheduler plugin**), `updated_at`.
- **`review_log`** — append-only events: `profile_id`, `item_id`, `ts`,
  `exercise` (e.g. `mcq_definition`), `response`, `correct`, `latency_ms`.
  Recorded from day 1: this is the training data a future RL scheduler needs, and
  aggregate state alone could not reconstruct it.

Plus **`meta`** (`schema_version`) for future migrations.

**Embeddings are deliberately not stored in the database.** Similarity queries go
through the `SimilarityProvider` interface (below); spaCy supplies vectors at
runtime today, and future custom code-embeddings live in their own artifact files.

## Extraction pipeline (phase 1)

1. Load text; light cleanup (whitespace, obvious junk lines).
2. Tokenize (current `prelexy/textproc.py` tokenizer as the starting point).
3. Apply the language's extraction policy (lemmatize via spaCy for `en`).
4. Filter: stopwords; proper nouns (POS tagging — otherwise character names like
   *Dorian* and *Basil* flood the candidate list); **dictionary-membership check** —
   a candidate must be found in the dictionary chain to be learnable. This doubles
   as the OCR-noise filter: garbage tokens from bad scans (the committed Dorian
   Gray file is imperfect OCR) are quarantined automatically rather than offered
   as vocabulary.
5. Rank candidates by rarity **(proposed:** corpus frequency via a wordlist such as
   `wordfreq`, rarest-first, tunable**)** — a fluent reader wants the rare words,
   not the common ones.
6. Persist `sources` / `items` / `occurrences`.

## MCQ exercise (phase 2)

Format (tier 1): show the item (with its example sentence from the source text),
ask **"pick the correct definition"** from four options.

- **Correct answer:** the item's top sense from the definition chain below.
- **Distractors:** top WordNet glosses of other same-POS words sampled from
  *all of WordNet* (~20k adjectives, ~100k nouns) — never from the words
  currently being studied, which made questions solvable by elimination.
  Selection is purely by embedding similarity **between the definitions
  themselves**: the correct gloss versus each candidate's gloss
  (DECISIONS 017) — rare literary words are usually absent from the pruned
  vector table, but their definitions are ordinary prose, so gloss-vs-gloss
  scoring has near-total coverage and measures the thing the player actually
  reads. Candidates must sit inside the band
  `SIMILARITY_FLOOR < s < SIMILARITY_CEILING` (`prelexy/mcq.py`) — above the
  ceiling the definitions nearly coincide (near-synonym: ambiguous, unfair),
  below the floor the gloss is from another domain (too obviously wrong).
  Band values are provisional; calibrate against real scores from
  `prelexy --debug question <word>`. Rarity plays no part (DECISIONS 013).
  Excluded: the target's lemma, duplicate glosses, and glosses that name
  the target word. Only when no provider is loaded at all do candidates
  fall back to random same-POS picks. Fully offline.

Other exercise types (cloze from the source sentence, reverse lookup) are natural
later additions; the `review_log.exercise` field already accommodates them.

## Definitions: offline-first chain

Lookup order, stopping at the first hit:

1. **WordNet** (via nltk, fully offline) **(proposed)**
2. **Local cache** — the `senses` table (previous API results)
3. **Free API fallback** — **(proposed)** dictionaryapi.dev (free, keyless);
   results are written to `senses`, so each word is fetched at most once.

Known weakness: WordNet glosses are terse and coverage of rare/archaic literary
words — exactly what tier 1 targets — is imperfect, which is why the fallback
chain matters. Upgrade path: offline Wiktionary extracts (kaikki.org) offer richer
glosses and, crucially, the **bilingual** glosses tier 2 needs; the
`senses.gloss_language` and `provider` fields are already shaped for it.

## Scheduler interface (phase 4)

```python
class Scheduler(Protocol):
    def next_items(self, store, profile_id: int, language: str,
                   now: datetime, limit: int) -> list[Row]:
        """Items to practice this session, most urgent first."""

    def record_review(self, state: Row, outcome: ReviewOutcome,
                      now: datetime) -> ItemSchedule:
        """Digest one review into the item's next status/due_at/state blob."""
```

The seam ships in phase 3 with `SimpleScheduler` (missed words first, then
new words rarest-first; one correct answer marks a word known, no spacing)
so the session loop is exercised before any real algorithm exists.

The scheduler owns `item_state.scheduler_state` (opaque JSON) and sets `due_at`;
core code never interprets the blob. Swapping algorithms is a config change, not a
migration: SM-2 stores its ease factor and interval there, a Leitner scheduler
stores a box number, a future RL policy stores whatever features it wants —
trained on `review_log`.

Default implementation: **SM2Scheduler**, a binary-outcome adaptation of
SM-2 (see DECISIONS 012): intervals of 1 day, 6 days, then interval × ease;
ease drifts up 0.1 per success (floor 1.3) and is untouched by misses, which
reset the ladder to tomorrow. "Known" from the third consecutive success —
but due dates, not statuses, drive scheduling. Sessions serve due reviews
(oldest due first), then new words rarest-first.

## SimilarityProvider interface

```python
class SimilarityProvider(Protocol):
    def similarity(self, a: str, b: str) -> float | None: ...       # word vs word
    def text_similarity(self, a: str, b: str) -> float | None: ...  # text vs text
```

One provider per language. Today: spaCy `en_core_web_md` vectors;
`text_similarity` averages content-token vectors (stopwords and punctuation
excluded — averaging them in inflates the similarity of any two English
sentences). Tier 3's custom-trained code embeddings (needed because `pop`
the Python method is nothing like `pop` the English word) plug in here
without touching the MCQ generator, which depends only on this interface.

## Diagnostics

`prelexy --debug <command>` (or `PRELEXY_DEBUG=1`) turns on diagnostic
output, dimmed on stderr so it never mixes with game output. The facility
(`prelexy/debug.py`) is deliberately minimal and extensible: any module
calls `debug.log(channel, message)` unconditionally — silent unless enabled,
one short channel name per subsystem ("mcq", "scheduler", …), no
registration. When a new subsystem misbehaves, add log calls under a new
channel rather than inventing a new mechanism.

## Pronunciation

`prelexy/speech.py` speaks a single word through the operating system's own
engine (macOS `say`, Windows SAPI, Linux `espeak-ng`) — free, offline, no
Python dependencies. Reached with `p` at the answer prompt (deliberately
does not reveal anything about the definition) or `prelexy say <word>`.
Upgrade path: Wiktionary hosts human recordings for many words; fetch on
demand, cache locally, fall back to the OS engine.

## Open questions

- Distractor similarity band and ranking thresholds — decide empirically (phase 2/5).
- Wiktionary/kaikki.org as the tier-2 bilingual source: dataset size and licensing
  ergonomics need a spike before v1.x.
- Whether `ingest` should also accept subtitle formats (`.srt`, `.vtt`) directly in
  v1 or plain `.txt` only (proposed: `.txt` only for v1).
- Text-cleanup depth for OCR-damaged inputs (e.g. `|` for `I` in the committed
  Dorian Gray scan): the dictionary filter quarantines the garbage, but heavier
  repair is deliberately out of core scope — input quality is the user's concern.
