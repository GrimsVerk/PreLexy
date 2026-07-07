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

8. ~~Owner verification~~ ✅ 2026-07-07: 3/3 on a real podcast transcript;
   Dutch TTS works (quality parked in Deferred). Findings drive Stage 2b.

### Stage 2b — v2 hardening from the 2026-07-07 Dutch playtest (approved)

1. **Raw wiktextract support in `import-glosses`.** kaikki's per-language
   extracts are deprecated; the future-proof source is the raw wiktextract
   dump (kaikki.org/dictionary/rawdata.html — the owner downloads it, the
   sandbox is egress-blocked). The importer must: stream `.jsonl.gz`
   directly (stdlib `gzip`, no decompressing a ~20 GB file to disk);
   filter entries by `lang_code` == the requested language (the raw dump
   mixes all languages — skipping this would attach wrong-language
   glosses); keep accepting the old per-language extracts. Exact download
   + import commands go into docs/VERIFICATION.md.
2. **Form-of gloss resolution.** "inflection of abonneren:" and
   "diminutive of graat" are useless as answers (playtest evidence).
   kaikki senses carry `form_of`/`tags`; prefer senses with real glosses,
   and for pure form-of entries resolve to the referenced lemma's gloss
   (the referenced word passes through the same import stream), rendering
   as e.g. "form of abonneren: to subscribe". Never emit a bare
   "inflection of X:" gloss.
3. **Un-suspend on new glosses.** Words suspended for having no definition
   must return to play once an import gives them one (7/10 words in the
   playtest are currently suspended forever). `import-glosses` deletes the
   suspended `item_state` rows (all profiles) for items it just glossed.
4. **`prelexy fetch <youtube-url>`.** Download a video's (auto-)subtitles
   as `.vtt` via `yt-dlp` — external tool like espeak (shutil.which +
   install hint), added to environment.yml's pip list — into
   `data/pods/`, with `--language` for the subtitle track and `--ingest`
   to ingest immediately. Works for single videos and playlist/channel
   URLs (yt-dlp handles both).
5. **Pod subscriptions.** `prelexy pods add|list|remove|sync`: saved
   channel/playlist URLs live in the store's `meta` table (no schema
   change); `sync` fetches new episodes' subtitles using yt-dlp's
   `--download-archive` (no re-downloads), `--ingest` optional. Owner's
   test channel: https://www.youtube.com/@tweakers/podcasts. Network
   tests are mocked in the sandbox; real fetching is owner-verified.

### Stage 3 — v3: learn programming languages from official docs
### (design owner-approved 2026-07-07 — DECISIONS 024; starts after Stage 2b)

Constraint from day one (CLAUDE.md rule 5): nothing in v1/v2 may break.
Design: DESIGN.md "Code documentation mode (v3)".

1. ~~Design spike~~ ✅ written 2026-07-06, owner-reviewed with amendments
   2026-07-07 (whole-corpus default, cross-corpus pools, line-after).
2. **Registry `kind` split.** `natural` vs `code` entries with per-kind
   required pieces; register `python` as the first code language.
3. **`prelexy ingest-docs <local-sphinx-dir>`.** Parse `objects.inv`
   (stdlib zlib) for the full inventory — the WHOLE corpus by default,
   `--modules a,b` as the optional filter — then pull each entry's first
   description sentence (gloss, provider `docs`) and signature from the
   HTML (stdlib html.parser). Items: qualified names under
   `language="python"`, metadata {kind, module, signature}; signature/
   example line stored as the occurrence context.
4. **Code-mode questions.** Distractor pool = same-kind items from the
   store's code corpora — ALL code languages by default (owner ruling),
   own-language-only as a config choice; existing gloss-text similarity;
   rarity stays banned. Signature/source line revealed only after
   answering (reuse the context-after-answer path).
5. **New-item ordering for code:** inventory order (module grouping falls
   out of `--modules`); zipf is meaningless for code — order by corpus
   position stored in metadata.
6. **End to end:** ingest the full stdlib docs → playable sessions;
   en/nl regression suites stay green; owner verification commands into
   docs/VERIFICATION.md (docs.python.org HTML archive download).

## Proposed

- **Guardrail fire drill**: one supervised small task with a friction log
  reviewed after (probes too-strict settings).
- **Guardrail bait drill**: vague instruction + tempting Deferred items in
  view; correct outcome = proposals only (probes too-permissive).
- **`/playtest` slash command** (`.claude/commands/playtest.md`): paste a
  transcript → structured triage (diagnose, map to backlog, propose only).

## Deferred (owner: later — do not start)

- `stats` command (counts by status, due dates)
- **TTS quality upgrade** (owner 2026-07-07: OS voices work but sound bad
  in both languages — implement later). Candidates: Wiktionary human
  recordings (cached, real pronunciation) and/or a neural offline engine
  (e.g. Piper — free, ~50MB voice models; new dependency → owner approval
  at implementation time).
- FSRS or RL-personalized scheduler trained on the review log
- **Unsupported languages** (grows as v2's registry rejects them): any
  language missing a spaCy pipeline, wordfreq data, a gloss source, or a
  TTS voice lands here with a note of what's missing.
