# Session journal

Two parts. **Field notes** are standing operational facts a fresh session
must know — edit in place, prune when stale. The **Log** is append-only:
every Claude working session adds one dated entry at the bottom — commits
made, discoveries, decisions taken, friction encountered (permission
prompts, denials, classifier blocks — this is the guardrail-tuning data),
and hand-off notes. Owner playtest transcripts live in `docs/playtests/`
and are referenced from entries.

## Field notes

- The owner's live database was ingested from the **uncleaned** Dorian Gray
  file (visible as "| remember" in context sentences). Re-ingesting the
  cleaned version into the same DB would double occurrence counts (items
  dedupe, occurrences don't) — fix is a fresh DB + ingest of the cleaned
  file, owner's call. The cleaned file exists untracked on the owner's
  machine at `data/corpora/dorian_gray_oscar_wilde.cleaned.txt`.
- `data/corpora/dorian_gray_oscar_wilde.txt` is the Project Gutenberg copy;
  the imperfect OCR is upstream, not local damage.
- `en_core_web_md` has **no vectors for most rare literary words** (owner
  check 2026-07-06: 5 of 6 sampled targets vectorless; only "wizen" had
  one). Word-level similarity is unreliable for exactly the words this game
  teaches — hence gloss-vs-gloss scoring (DECISIONS 017).
- The Claude sandbox cannot download spaCy models (GitHub releases blocked
  by egress policy); NLTK data and PyPI work fine. Real-vector behaviour is
  only observable on the owner's machine — see docs/VERIFICATION.md.
- The auto-mode permission classifier (a layer outside `.claude/settings.json`
  that we do not configure) has blocked: batch delete/restructure commands,
  branch surgery, and any attempt by the agent to write settings.json.
  Approved backlog items should spell out destructive intent ("delete X",
  "rewrite Y") so the classifier can see the action is sanctioned.
- Distractor band values (0.45 / 0.85) are provisional — calibrate against
  `[mcq]` score lines from owner `--debug` playtests before trusting them.

## Log

### 2026-07-06 — guardrails, context capture

- Earlier today: gloss sanitizer (b1a5b67), debug facility (55957c7),
  gloss-similarity scoring (47d9348), hardest-pool sampling (95207dc),
  config quotas + band (6e7fd29), clean command (0decdd1), guardrail files
  (6df0e2e). Owner applied `.claude/settings.json` themselves (9165366).
- This entry's session: added this journal, docs/VERIFICATION.md, and the
  unattended-session rules in CLAUDE.md (stuck → log → move on; simplest
  stand-in when a blocker gates everything; friction logging).
- Friction datum: the classifier denied the agent writing
  `.claude/settings.json` (self-modification) — correct behaviour; the
  owner pasted it instead. Earlier friction: batch `git rm`/`git mv`
  restructure denied until the owner granted permission in chat.
- Friction datum #2: *editing* settings.json (allowlist additions:
  git mv/rm/checkout/switch/stash/pull, mkdir, printf, setup script) was
  permitted when done right after an explicit owner instruction in chat —
  the classifier weighs conversational intent heavily.
- Owner ruling added late in the session: rolling context capture
  (DECISIONS 021) — repo-worthy info moves from chat to its file as it
  appears, routing table in CLAUDE.md.
- Awaiting owner: verification run (commands in docs/VERIFICATION.md),
  most importantly whether `prelexy say` produces audio, post-change
  `--debug play` scores for band calibration, and real-model pytest.
  Owner will then merge everything into main; from that point the `claude`
  branch accumulates only the unattended work done while they are away.

### 2026-07-06 (later) — owner verification results, version plans

- Owner ran the full verification batch (docs/playtests/2026-07-06-*):
  103/103 tests pass on the real model; top-10 pool confirmed (scores
  0.53–0.85, was 0.45–0.6); quotas live ("3 seen + 7 new"); glosses clean;
  cleaner counts match sandbox; **pronunciation produces audio** (chat).
  VERIFICATION ledger updated — everything owner-verifiable is now
  owner-verified except band calibration (data now exists) and the
  free-API fallback (fails soft, low risk).
- Calibration data points for Stage 1: in-band counts range 31–341 per
  500 scanned; 'gleefulness' (0.716) surfaced as a de-facto near-synonym
  of 'joyousness' below the 0.85 ceiling → consider lowering the ceiling;
  sparse-neighborhood words (pattered: 31 in band) produce easier options
  than dense ones (comeliness: 271) — expected, acceptable.
- 'comeliness' served a ~1,400-character context sentence → confirms the
  shortest-complete-occurrence backlog item.
- Restructured docs/BACKLOG.md into sequential stages (v1 polish → v2
  languages → v3 code docs) per owner instruction; ROADMAP v2/v3 plans
  written. Owner merges to main next; unattended work then accumulates on
  `claude`.

### 2026-07-06 — unattended run: Stage 1 complete, Stage 2 built, v3 spike

- Pre-work per owner instruction: reviewed the two rate-limit-era commits
  (249da44, 5e28c8a) — content accurate; fixed two stale ROADMAP phase
  annotations found during the review (d4fd489). Owner had merged
  claude↔main (PRs #2/#3); rebased onto the merge.
- **Stage 1 (all eight items):** named-entity distractor exclusion +
  non-instance gloss preference ("china" → porcelain); distractor pool
  follows the gloss's POS (gartered/tabooed leak); GitHub Actions CI;
  gloss length gate (2.5×/40-char slack); shortest-complete example
  sentences (also dodges OCR-pipe contexts); band calibration verdict —
  values confirmed, WordNet synonym/relative guard added instead of band
  movement (DECISIONS 022); the six config settings wired end to end
  (default_profile/default_language/db_path/tts_voice/pool_size/
  show_context); cleaned-corpora gitignore.
- **Stage 2 (items 1–7):** language registry (en+nl; unsupported → error
  naming missing pieces); wordfreq membership gate for non-English; OMW
  bilingual glosses — Dutch words get English definitions offline, with
  surface→lemma fallback ("liep"→"lopen") (DECISIONS 023); kaikki.org
  Wiktionary importer for OMW's thin adjectives; Dutch distractor pools +
  language-aware synonym guard (huis/woning); profile language memory;
  .srt/.vtt ingestion with sentence-safe re-paragraphing. A Dutch MCQ
  builds fully offline in tests. Item 8 (real-model/transcript run)
  AWAITING OWNER — commands in VERIFICATION.
- **Stage 3:** design spike written into DESIGN.md ("Code documentation
  mode (v3) — PROPOSED"): objects.inv + Sphinx HTML ingestion, docs as
  their own dictionary, description-similarity distractors, no schema
  changes, zero new dependencies; four open questions listed. AWAITING
  OWNER REVIEW — per backlog, no v3 implementation until then.
- Suite grew 102 → 137 passing (+1 model skip). No permission prompts,
  denials, or classifier blocks this run (friction log: one transient
  classifier outage, retried fine; one non-fast-forward push resolved by
  rebase after the owner's merges).
- CI initially failed on every run — setup-python's `cache: pip` needs a
  requirements.txt/pyproject.toml to key on and dies before pytest when
  none exists. Dropped the cache option; run `362b31f` is **green on
  GitHub's runner** (checked via the Actions API from the sandbox).
  Lesson for the ledger: "CI added" ≠ "CI verified" until a run passes.
- Hand-off: owner returns → (1) v1-feel playtest + v2 Dutch commands in
  VERIFICATION, (2) review the v3 design + its four questions, (3) check
  CI runs on GitHub Actions. Everything else is done or owner-gated.

### 2026-07-07 — owner feedback round: Dutch verified, new work planned

- Owner questions answered: the two reviewed commits (249da44, 5e28c8a)
  are ancestors of the current branch (`git merge-base --is-ancestor`
  confirms) — the "divergence" on GitHub is the PR #2/#3 merge topology,
  no content lost. CI reds were purely the workflow config bug (pip cache
  needing a requirements file, job died before pytest); the local suite
  passed for every commit, and the same code went green once fixed.
- Dutch playtest (playtests/2026-07-07-play-nl.txt): end-to-end WORKS —
  real podcast transcript, 1,685 items, 3/3 correct with English glosses
  (owner had imported the deprecated kaikki Dutch extract). Failures it
  exposed, feeding Stage 2b: 7/10 served words had no gloss → suspended
  forever (imports must un-suspend items they gloss); form-of glosses
  ("inflection of abonneren:", "diminutive of graat") are useless as
  answers and stylistic tells; Dutch in-band counts are low (1–34/500 vs
  English 31–341) — the below-floor pool fallback carried those questions,
  as designed.
- Owner rulings captured this round: kaikki per-language extracts are
  deprecated → support the raw wiktextract dump (downloaded on the owner's
  machine; kaikki.org is 403-blocked from the sandbox); YouTube transcript
  fetching + pod subscriptions wanted (test channel:
  youtube.com/@tweakers/podcasts); v3 defaults to the ENTIRE stdlib with
  module filtering optional, cross-corpus distractors as a user choice,
  source line shown only after answering; one ingest for everything
  confirmed (subtitles already work for v1/English); TTS upgrade parked in
  Deferred (voice quality poor in both languages, owner: later).
