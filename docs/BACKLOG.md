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

### Stage 1 — v1 polish (English mode) — ✅ COMPLETED 2026-07-06

All eight items done (instance-synset exclusion, POS-follow pool, CI,
length gate, shortest-complete contexts, band calibration + synonym guard
per DECISIONS 022, the six config settings, cleaned-corpora gitignore).
Details: docs/JOURNAL.md entry of 2026-07-06 and the commit history.
Owner re-verification of question feel: next playtest.

### Stage 2 — v2: learn a new language from zero (test language: Dutch)
### — items 1–7 ✅ COMPLETED 2026-07-06; item 8 AWAITING OWNER

Implemented: language registry (unsupported → clear error naming missing
pieces), Dutch plumbing + wordfreq noise gate, OMW bilingual glosses with
surface→lemma fallback (DECISIONS 023), kaikki.org Wiktionary importer
(`prelexy import-glosses`), Dutch distractor pools with the synonym guard,
profile language memory (+ stored `strong_language` for future
per-profile glossing), `.srt`/`.vtt` ingestion, Dutch espeak voice.

8. **Owner verification (open).** Needs the Dutch spaCy model, a real
   podcast transcript, optionally a kaikki Dutch extract, and a playtest —
   exact commands in docs/VERIFICATION.md ("v2 (Dutch)" section). Dutch
   TTS quality also needs the owner's ear.

### Stage 3 — v3: learn programming languages from official docs

Coarse on purpose — item 1 refines this stage before code is written.
Constraint from day one (CLAUDE.md rule 5): nothing in v1/v2 may break.

1. **Design spike → docs/DESIGN.md section + DECISIONS entries.**
   ✅ Spike written 2026-07-06 — see DESIGN.md "Code documentation mode
   (v3) — PROPOSED", including four open questions. **AWAITING OWNER
   REVIEW before any item below starts.**
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
