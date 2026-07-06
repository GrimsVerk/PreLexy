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
