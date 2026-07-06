# Backlog

The agreed work queue. **Autonomous sessions implement items from
"Approved" only, strictly top to bottom** — the stages are sequential:
finish Stage 1 before starting Stage 2, finish Stage 2 before Stage 3.
Exception (CLAUDE.md stuck rule): when every remaining item of the current
stage is stuck or awaiting the owner, journal that state and continue into
the next stage rather than idling.

New ideas land in "Proposed" (one line of rationale each); the owner
promotes by moving them into Approved. "Deferred" items were explicitly
parked by the owner — do not start them, do not delete them.

## Approved

### Stage 1 — v1 polish (English mode)

1. **Exclude instance synsets from the distractor pool.** Named entities
   ("Argentine revolutionary leader … Guevara") are absurd distractors;
   WordNet marks them as instances (`instance_hypernyms()`), cheap to
   filter at candidate time.
2. **Fix the POS-fallback gloss-style leak.** When the target's gloss
   comes from a fallback POS (adjective "gartered" got the verb gloss
   "fasten with…"), its phrasing fingerprints it among same-POS distractor
   glosses. Draw the candidate pool from the POS the gloss actually came
   from.
3. **GitHub Actions CI**: pytest on every push (downloads NLTK data in the
   workflow; no spaCy model, so the one model test skips — same as the
   sandbox). Gives the owner an impartial green/red.
4. **Length/style-match distractor glosses** to the correct one — a crisp
   answer among sprawling encyclopedic options (or vice versa) is a tell.
5. **Context sentences: prefer the shortest sentence-complete
   occurrence.** Playtest evidence: 'comeliness' served a ~1,400-character
   sentence; OCR page breaks truncate others mid-sentence.
6. **Band calibration** from `docs/playtests/` data: first pass now
   (observed: in-band counts 31–341/500; 'gleefulness' at 0.716 acted as a
   near-synonym under the 0.85 ceiling → likely lower the ceiling; propose
   new defaults in config + mcq). Final pass needs a post-change owner
   playtest — note that in VERIFICATION and move on.
7. **Config additions:** `default_profile` (skip the picker),
   `default_language`, `db_path`, pronunciation voice/engine, `pool_size`,
   context-sentence toggle.
8. **gitignore `*.cleaned.txt`** — cleaned corpora are derived artifacts.

### Stage 2 — v2: learn a new language from zero (test language: Dutch)

Design anchors: DECISIONS 002 (surface forms, not lemmas), the `senses.
gloss_language` field (glosses shown in the learner's strong language —
English for the owner), ROADMAP "v2" for success criteria. The sandbox
cannot download spaCy models for any language — develop against hand-built
Docs as in tests/test_textproc.py; real-model verification is the owner's.

1. **Language-support registry.** One table (code) declaring what each
   language needs: spaCy pipeline names, wordfreq availability, gloss
   source, espeak voice. `--language xx` for an unsupported language →
   clear error listing exactly which pieces are missing; such languages
   are recorded under Deferred ("maybe later"), not half-implemented.
2. **Dutch NLP plumbing.** spaCy model mapping (`nl_core_news_md`
   preferred, `sm` fallback); dictionary-membership gate for non-English
   (wordfreq zipf > 0 as the noise filter, since WordNet is
   English-only); surface-form policy already exists in
   `textproc.item_form`.
3. **Bilingual gloss chain.** Spike first: Open Multilingual Wordnet via
   nltk (`synsets(word, lang='nld')` → English gloss) — measure coverage
   on real Dutch words. Richer path: kaikki.org Wiktionary extract for
   Dutch (free, downloadable once, parsed into the senses cache).
   Cached free API as last resort. Chain order and findings → DECISIONS.
4. **Distractors for non-English targets.** Candidate pool from the Dutch
   lemma source (OMW/kaikki), same POS; since options are *English*
   glosses, the existing gloss-vs-gloss similarity (English vectors)
   works unchanged — reuse it.
5. **Profile language settings.** `strong_language` and active language
   per profile (profiles.settings JSON); `default_language` from config;
   en and nl items coexisting in one DB (already keyed by language —
   verify with tests end to end).
6. **Subtitle/transcript formats.** Accept `.srt`/`.vtt` in ingest/clean
   (strip timestamps and cue numbers) — podcast transcripts often ship as
   subtitles.
7. **Dutch pronunciation.** espeak voice mapping exists (`nl`); verify the
   full path and cover with tests.
8. **Owner verification.** Needs a real Dutch podcast transcript from the
   owner + a playtest; add v2 rows to docs/VERIFICATION.md with the exact
   commands. Until then, verify with a small hand-made Dutch sample.

### Stage 3 — v3: learn programming languages from official docs

Coarse on purpose — item 1 refines this stage before code is written.
Constraint from day one (CLAUDE.md rule 5): nothing in v1/v2 may break.

1. **Design spike → docs/DESIGN.md section + DECISIONS entries.** What an
   item is for code (qualified names: `list.pop`, `itertools.chain`);
   what a gloss is (the doc entry's summary sentence — docs are their own
   dictionary, no WordNet); ingestion sources (official Python docs
   first; Sphinx `objects.inv` inventories as structured entry points).
   Owner reviews the design before implementation continues.
2. **Docs ingester.** Extraction policy for `language="python"`; parse
   inventory + doc text into items/occurrences (usage examples as context
   sentences).
3. **Glosses from the docs** stored in senses with provider `docs`.
4. **Distractors from the same corpus.** Pool = other items of the same
   docs corpus (kind-matched: method vs method); first pass reuses the
   existing gloss-text similarity on English doc descriptions. Custom
   code embeddings (the "pop ≠ pop" problem) only if that proves
   inadequate — training them means a new dependency, which needs owner
   approval (CLAUDE.md rule 4).
5. **Ordering/curriculum for code items** (corpus frequency? module
   grouping?) — bring options to the owner for a ruling.
6. **End to end:** ingest a Python stdlib subset (e.g. `itertools`,
   `collections`) → playable sessions; en/nl regression suites stay green.

## Proposed

- **Guardrail fire drill**: one supervised small task with a friction log
  reviewed after (probes too-strict settings).
- **Guardrail bait drill**: vague instruction + tempting Deferred items in
  view; correct outcome = proposals only (probes too-permissive).
- **`/playtest` slash command** (`.claude/commands/playtest.md`): paste a
  transcript → structured triage (diagnose, map to backlog, propose only).

## Deferred (owner: later — do not start)

- `stats` command (counts by status, due dates)
- Wiktionary human pronunciation recordings (cached), replacing OS TTS
- FSRS or RL-personalized scheduler trained on the review log
- **Unsupported languages** (grows as v2's registry rejects them): any
  language missing a spaCy pipeline, wordfreq data, a gloss source, or a
  TTS voice lands here with a note of what's missing.
