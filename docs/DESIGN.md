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
- **Distractors (proposed):** real definitions of other items that are
  (a) the same part of speech, (b) frequency-matched (similarly rare), and
  (c) within a cosine-similarity band of the target — close enough to be
  plausible, far enough to be clearly wrong. Near-synonyms are excluded (too
  close is ambiguous and unfair), as is anything sharing a lemma with the
  target. Band thresholds are tunable constants, calibrated empirically in
  phase 2.

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
    def next_items(self, profile_id: int, now: datetime, limit: int) -> list[ItemState]:
        """Compose a session: due reviews first, then new items."""

    def record_review(self, state: ItemState, outcome: ReviewOutcome) -> ItemState:
        """Return updated state, including new due_at and scheduler_state blob."""
```

The scheduler owns `item_state.scheduler_state` (opaque JSON) and sets `due_at`;
core code never interprets the blob. Swapping algorithms is a config change, not a
migration: SM-2 stores its ease factor and interval there, a Leitner scheduler
stores a box number, a future RL policy stores whatever features it wants —
trained on `review_log`.

**(proposed)** Default implementation: **SM-2** — simple, battle-tested (classic
Anki), well documented.

## SimilarityProvider interface

```python
class SimilarityProvider(Protocol):
    def similarity(self, a: Item, b: Item) -> float: ...
    def neighbours(self, item: Item, k: int) -> list[tuple[Item, float]]: ...
```

One provider per language. Today: spaCy `en_core_web_md` vectors. Tier 3's
custom-trained code embeddings (needed because `pop` the Python method is nothing
like `pop` the English word) plug in here without touching the MCQ generator,
which depends only on this interface.

## Open questions

- Distractor similarity band and ranking thresholds — decide empirically (phase 2/5).
- Wiktionary/kaikki.org as the tier-2 bilingual source: dataset size and licensing
  ergonomics need a spike before v1.x.
- Whether `ingest` should also accept subtitle formats (`.srt`, `.vtt`) directly in
  v1 or plain `.txt` only (proposed: `.txt` only for v1).
- Text-cleanup depth for OCR-damaged inputs (e.g. `|` for `I` in the committed
  Dorian Gray scan): the dictionary filter quarantines the garbage, but heavier
  repair is deliberately out of core scope — input quality is the user's concern.
