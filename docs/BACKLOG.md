# Backlog

The agreed work queue. **Autonomous sessions implement items from
"Approved" only**, top to bottom. Everything else is discussion material:
new ideas land in "Proposed" (with a line of rationale), and the owner
promotes them by moving them up. "Deferred" items were explicitly parked by
the owner — do not start them, do not delete them.

## Approved

(empty — the owner moves items here)

## Proposed

- **Exclude instance synsets from the distractor pool.** Named entities
  ("Argentine revolutionary leader … Guevara") are absurd distractors;
  WordNet marks them as instances, cheap to filter. Likely the best
  remaining easiness fix.
- **Fix the POS-fallback gloss-style leak.** When the target's gloss comes
  from a fallback POS (adjective "gartered" served the verb gloss "fasten
  with…"), its phrasing style fingerprints it among same-POS distractor
  glosses. Draw candidates from the gloss's actual POS instead.
- **Length/style-match distractor glosses** to the correct one — a crisp
  answer among sprawling encyclopedic options is a subtle tell.
- **Prefer complete context sentences.** OCR page breaks truncate some
  occurrences ("…and the coat that Charles of"); prefer occurrences that
  look sentence-complete.
- **Context-aware sense choice.** The correct gloss is always WordNet's
  first sense, which may not match the book's usage for polysemous words.
- **Config additions:** `default_profile` (skip the picker),
  `default_language`, `db_path`, pronunciation voice/engine, `pool_size`
  (difficulty knob), context-sentence toggle.
- **GitHub Actions CI** running pytest on push, so the owner sees green/red
  without trusting session claims.
- **`/playtest` slash command** (`.claude/commands/playtest.md`): paste a
  transcript → structured triage (diagnose, map to backlog, propose only).

## Deferred (owner: later — do not start)

- `stats` command (counts by status, due dates)
- Wiktionary human pronunciation recordings (cached), replacing OS TTS
- Dutch / L2 tier (surface-form policy exists; needs bilingual glosses)
- Programming-docs tier (custom embeddings behind SimilarityProvider)
- FSRS or RL-personalized scheduler trained on the review log
