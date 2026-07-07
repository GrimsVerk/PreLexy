# Roadmap

## v1 — "Read Dorian Gray without a dictionary" (tier 1, English)

v1 is done when this works end to end:

> Point PreLexy at a `.txt` book → it extracts and ranks the words you likely don't
> know → you run a multiple-choice session in the terminal ("pick the correct
> definition") → your progress persists between sessions under your profile →
> previously seen words come back for review when the scheduler says they're due.

### Success criteria

- [x] `prelexy ingest <file>` extracts lemma-based items from an English text,
      filters noise (stopwords, proper nouns, dictionary-membership check), ranks
      candidates by rarity, and stores them *(owner-verified 2026-07)*
- [ ] `prelexy play` runs an MCQ session with real definitions and plausible
      distractors, and shows the example sentence from the source text
      *(works; "plausible" pending band calibration — docs/VERIFICATION.md)*
- [x] Progress is per profile and survives program restarts
      *(owner-verified across days)*
- [x] Reviews come due on schedule, and the scheduler is swappable behind an
      interface without touching any other code *(owner-verified; swap was a
      one-line change)*
- [ ] Works fully offline after initial setup (API used only as a fallback for
      missing definitions, with results cached locally) *(offline works; the
      API fallback path has never fired live — low risk, fails soft)*

### Phases

1. **Extraction CLI** *(implemented, owner-verified)* — ingest a text:
   tokenize, apply the extraction policy (lemmas for English), filter noise,
   rank by frequency/rarity; persist sources/items/occurrences to SQLite.
2. **MCQ generation** *(implemented — `prelexy question <word>` previews one)*
   — definition lookup through the offline-first chain (cache → WordNet →
   free API); distractors sampled from the hardest-available WordNet-wide
   pool by definition-text similarity (DECISIONS 013/017/018).
3. **Session loop + saves** *(implemented — `prelexy play`)* — terminal UI,
   profiles, answer recording, and the append-only review log.
4. **Scheduler** *(implemented — SM-2 is the default)* — the `Scheduler`
   interface with SM-2 as the default implementation; sessions composed from
   due reviews plus new items.
5. **Polish** — ranking quality, distractor quality tuning, UX friction, docs.

## Version sequence

Development is strictly sequential: **finish v1 polish, then build v2, then
build v3** (docs/BACKLOG.md mirrors this as Stages 1–3). The only exception
is the stuck rule in CLAUDE.md: if everything remaining in the current
stage is blocked or awaiting the owner, continue into the next stage and
journal why.

## v2 — learn a new language from zero (tier 2)

v2 is done when this works end to end:

> Point PreLexy at a real Dutch podcast transcript → it extracts and ranks
> the **exact surface forms** used (learn "was", never an unheard
> conjugation — grammar is absorbed from input volume, DECISIONS 002) →
> MCQ sessions where the options are glosses **in the learner's strong
> language** (English for the owner) → per-profile spaced repetition —
> while English mode keeps working, in the same database.

Any language is supported when the whole stack supports it: a spaCy
pipeline, wordfreq data, a bilingual gloss source, and a TTS voice.
Languages missing a piece are recorded in BACKLOG "Deferred" ("maybe
later") with what's missing — never half-implemented. **Dutch is the
required first language** (the owner's target; used for all real-world
testing).

Phases: (1) language-support registry + graceful unsupported errors
*(implemented)*; (2) Dutch NLP plumbing and a non-English noise gate
*(implemented)*; (3) bilingual gloss chain: OMW → kaikki.org Wiktionary
importer → cached free API *(implemented — DECISIONS 023)*; (4) distractor
pool for non-English targets *(implemented — English-gloss similarity
reused)*; (5) per-profile language settings + config `default_language`
*(implemented)*; (6) `.srt`/`.vtt` transcript ingestion *(implemented)*;
(7) owner verification with a real transcript *(AWAITING OWNER —
docs/VERIFICATION.md has the commands)*.

## v3 — learn programming languages from official docs (tier 3)

v3 is done when this works end to end:

> Ingest official documentation (Python stdlib first, then any library) →
> drill methods and functions as "pick the correct description" with
> spaced repetition — without breaking the natural-language modes.

Items are qualified names (`list.pop`); glosses come from the docs
themselves (no dictionary needed); distractors come from the same corpus
through the existing `SimilarityProvider` seam — first pass with gloss-text
similarity on the English descriptions, custom-trained code embeddings only
if that proves inadequate (new dependency → owner approval). The stage
opens with a design spike that lands in docs/DESIGN.md for owner review
before implementation.

## Exploratory (no version assigned)

- An RL-based personalized scheduler trained on each player's review log,
  plugged in behind the `Scheduler` interface.

## Out of scope (all versions, until explicitly revisited)

- GUI, web, or mobile interfaces — terminal only
- Audio beyond word pronunciation (hearing how the current word is
  pronounced — `p` during a session, `prelexy say <word>` — is in scope;
  general audio playback and speech interfaces are not)
- Cloud sync or online accounts — profiles are local to the machine
- Paid data sources or APIs — the project stays entirely free
