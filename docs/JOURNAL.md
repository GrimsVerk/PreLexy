# Session journal

Two parts. **Field notes** are standing operational facts a fresh session
must know — edit in place, prune when stale. The **Log** is the history of
past sessions; work in flight now lives in `next-steps.md`, so
add a Log entry only when something is worth keeping beyond git history. Owner
playtest transcripts live in `docs/playtests/` and are referenced from entries.

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
- Distractor band values (0.45 / 0.85) are provisional — calibrate against
  `[mcq]` score lines from owner `--debug` playtests before trusting them.
- `pods sync --ingest` verified at scale (owner 2026-07-07): 429 Tweakers
  episodes fetched via yt-dlp and ingested, ~1,500 items each. Dutch v2 is
  the owner's real corpus now. yt-dlp warns "no impersonate target" — a
  cosmetic warning, downloads succeed anyway.
- Python docs archive names carry the micro version
  (`python-3.13.x-docs-html.zip`); resolve the name from
  docs.python.org/3/download.html rather than hard-coding, and always
  `curl -fL` (without -f, curl exits 0 on a 404 error page).
- Current NLTK (3.10+) resolves the Open Multilingual Wordnet through the
  `omw-2.0` corpus; `omw-1.4` alone no longer satisfies it and 8 Dutch/OMW
  tests fail with `LookupError`. Fixed 2026-07-20: the workflow,
  `.claude/session-setup.sh`, `prelexy/textproc.py`, and README now fetch
  `omw-2.0` (replacing `omw-1.4`, not alongside it — deps are unpinned so
  every environment gets the latest NLTK; an old NLTK couldn't fetch
  `omw-2.0` anyway, so carrying both names bought nothing).

## Log

### 2026-10-29 — template v2 (v1.0.1)

- Branch `chore/template-v2`: `copier update` from v0.4.7 to v1.0.1. The summer
  pipeline is gone (plan/template-sync/test-the-tests/review gates, auto-merge,
  CODEOWNERS, worker spawning, GLOSSARY, ceremony docs); CI is one `check` job
  on push to `main`. `AGENTS.md` now says MIT, closing the 2026-10-29 hand-off
  below. Process changes recorded in DECISIONS 027.

### 2026-10-29 — go-public preparation

- Branch `go-public`: added MIT `LICENSE`, the `pyproject.toml` license field,
  and a README License section (DECISIONS 026).
- Secret scan of every ref (incl. `refs/pull/*`) with gitleaks 8.30.1 and
  trufflehog 3.99.2, plus a manual pass over `git log -p --all`: nothing found.
- Path audit: no machine-specific paths in tracked files; the `~/` paths are
  the app's portable XDG defaults, so no local-override file was needed.
- Hand-off: AGENTS.md "Licensing" paragraph is now stale (see DECISIONS 026).

### 2026-08-14 (later) — template v0.4.7 landed; CI gates live

- PR #3 (prep) and PR #4 (the update itself) are merged; PreLexy is on
  template v0.4.7. The update jumped v0.1.0 -> v0.4.7 in one step and brought
  the merge pipeline (plan, template-sync, secrets, test-the-tests, LLM
  review), the planning system under `docs/plans/`, CODEOWNERS and GLOSSARY.
- Four files conflicted, all resolved by keeping this project's content and
  taking the template's where it had something to add: `pyproject.toml`,
  `.claude/settings.json`, `README.md`, `docs/DESIGN.md`. Details in the PR #4
  description and DECISIONS 025.
- `ci.yml` and `tests/conftest.py` came through byte-identical to the render,
  which is what the root `conftest.py` bootstrap was for.
- **`template-sync` cannot pass on a conflicted update.** It replays `copier
  update` and demands the tree match byte-for-byte, but the replay leaves
  conflict markers in files this project owns content at — so the only
  satisfying tree is a broken one. PR #4 needed an override. Fix belongs
  upstream: detect that the replay itself conflicted, then require the PR to
  differ from it only inside those files.
- Both CI secrets failed on trailing newlines (field note above). The template
  token is now verified working; the Claude token was still broken at the time
  of writing.
- Deleted the empty `template/v0.4.4` branch: a leftover from the failed
  pre-fix update run, holding zero unique commits.

### 2026-08-14 — template update prep: toolchain adopted, CI restored

- `copier update` to the current template (v0.4.5) was failing before it
  started. Two causes, both recorded in `.copier-answers.yml`:
  **project_name** — v0.4.0 added a validator requiring a package-shaped
  name; `PreLexy` fails it. Copier does not error on an invalid recorded
  answer, it silently deletes it, then falls back to a default that renders
  empty inside the update scratch directory — so `--defaults` dies with
  "A project name is required", naming a field that *is* recorded.
  Now `prelexy`, which is what the package directory is called anyway.
  **_src_path** — was `ssh://git@github.com/...`. That form matches neither
  `insteadOf` rewrite CI installs (`https://github.com/` and
  `git@github.com:`), verified with an isolated git config, so the private
  template clone fails in CI regardless of `TEMPLATE_TOKEN`; and the bare
  host carries no key on the owner's machine either. Now the https URL,
  which is what template v0.4.5 records by design.
- Restored what the 2026-07-20 adoption declined, since copier treats a
  declined file as deleted and never brings it back: `pyproject.toml`,
  `uv.lock`, `.github/workflows/ci.yml`. **Not** restored:
  `src/prelexy/__init__.py` (would add a second, empty `prelexy` package
  shadowing the real one) and `tests/test_placeholder.py` (161 real tests).
- Adopting the template's CI meant adopting its toolchain: ruff (22 errors,
  19 files reformatted) and mypy `--strict` (573 errors → 0). The typing
  work found no bugs but did surface real looseness — Optional rows indexed
  without a check all over the tests, now asserted; `list.append(x) or True`
  in two test doubles; a `Config` TypedDict replacing `dict[str, object]`.
  Owner ruled for full strict rather than a scoped config (chat, 2026-08-14).
- `tests.yml` retired; `ci.yml` replaces it. It is restored **byte-identical
  to the template's own render**, deliberately: the suite's WordNet/OMW
  requirement is met by a new root `conftest.py` instead of a step in the
  workflow. The template ships `tests/conftest.py` but no root one, so the
  bootstrap is project-owned, survives updates untouched, and leaves
  `ci.yml` clean for the byte-for-byte `template-sync` check. Owner's point
  (chat): PreLexy's corpora are PreLexy's problem and have no business
  upstream — which is equally an argument against putting them in a
  template-owned file here.
- Friction: pushing a **tag** is denied for agent sessions (403 from the git
  proxy, and the GitHub API refuses ref writes) — the owner pushed the
  template's v0.1.0 tag. Branch pushes are fine. Also, NLTK refuses proxied
  downloads in this sandbox, so the new `ci.yml` fetch step could not be
  exercised through `uv run` here — though the bootstrap itself was verified
  by deleting `~/nltk_data` and watching the suite re-fetch it
  (docs/VERIFICATION.md).
- Hand-off: this branch is prep only — it does **not** update the template.
  Once merged, `copier update --defaults --trust` from `main` lands v0.4.5
  cleanly (verified on a scratch clone). Expect conflicts in `README.md`,
  `docs/DESIGN.md`, and `.claude/settings.json`: the template now ships files
  at paths PreLexy already owns. `template-sync` will need a `TEMPLATE_TOKEN`
  repository Actions secret before it can pass.

### 2026-07-20 — CI green: omw-2.0 corpus

- CI was failing: 8 Dutch/OMW tests raised `LookupError: Resource
  'omw-2.0' not found` (2 surfaced as `play` CLI exit-code-1 failures).
  Root cause: NLTK 3.10 needs the `omw-2.0` corpus but the workflow /
  setup / textproc only fetched `omw-1.4`. Owner confirmed no backcompat
  need, so replaced `omw-1.4` → `omw-2.0` in `.github/workflows/tests.yml`,
  `.claude/session-setup.sh`, `prelexy/textproc.py`, and README. Verified:
  with only `omw-2.0` on disk, suite is 161 passed, 1 skipped.

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

### 2026-07-07 (later) — Stage 2b + Stage 3 implemented

- **Stage 2b (all five items):** import-glosses streams .jsonl.gz raw
  wiktextract dumps (magic-byte sniff), filters by lang_code, ranks real
  glosses over form-of (the lemma entry now beats "inflection of
  abonneren:"), un-suspends items it glosses; `prelexy fetch <url>`
  downloads YouTube (auto-)subtitles via yt-dlp (external tool, install
  hint, env pip dep) with --ingest; `prelexy pods add/list/remove/sync`
  stores subscriptions in the meta table and syncs via yt-dlp's download
  archive. Real-network verification is the owner's (commands in
  VERIFICATION "Stage 2b").
- **Stage 3 (all items):** registry kind split (natural|code, python
  registered); prelexy/docsproc.py parses Sphinx objects.inv (stdlib
  zlib) and extracts signature + first description sentence per object
  (stdlib html.parser); `prelexy ingest-docs <dir>` stores the WHOLE
  corpus by default with --modules as the optional filter (metadata:
  kind/module/signature/order); code distractors come from store.code_pool
  — cross-language by default, config code_pool_own_language restricts;
  scheduler serves code items in inventory order (item_order in the sort
  key); the signature line rides the existing after-answer context path.
  Sandbox-verified end to end on a synthetic docs tree; the real
  full-stdlib run is the owner's (VERIFICATION "v3").
- Suite: 137 → 158 passing (+1 model skip). Friction: none (no prompts,
  denials, or classifier events this run).
- Hand-off: everything in Approved is implemented. Owner verifies: Stage 1
  feel, v2 raw-gloss + pods flow, v3 full stdlib. All commands live in
  docs/VERIFICATION.md, newest sections first.

### 2026-07-07 (later) — bug fixes from the owner's first real v2/v3 run

Owner ran `pods sync --ingest` (429 Tweakers episodes, huge win — v2 works
at scale) then a v3 attempt that failed. Four bugs, all fixed:
- **Docs download URL wrong.** Hard-coded `python-3.13-docs-html.zip`
  doesn't exist (archives carry the micro version); curl without -f exited
  0 on the 404 page, failing only at unzip. VERIFICATION now resolves the
  name from the download page and uses `curl -fL` (also for kaikki).
- **Language-memory trap.** `play --language python` on the empty python
  corpus served nothing but still pinned python as the profile's language,
  so a later plain `play` hid the 429-episode Dutch corpus behind
  "Nothing to practice". Fix: run_session reports `had_items`; play
  remembers the language only when the session had items.
- **Uninformative empty message.** Now names the empty language and lists
  other languages that have words with the exact `play --language <x>`
  command (store.language_item_counts).
- **example_for unbounded.** Fetched every occurrence to pick the shortest
  complete sentence — tens of thousands after the mega-ingest. Added
  `ORDER BY length(context) LIMIT 200` (best sentence is always shortest,
  so the choice is unchanged).
- Suite 158 → 161. Friction: none. All Approved work remains implemented;
  the outstanding items are still owner verification (v2 raw glosses, v3
  full stdlib).

### 2026-07-20 — Copier adoption (template v0.1.0)

- Brought PreLexy under grimsverk-template management on branch
  `copier/adopt` (owner merges via draft PR; main untouched). Adopted:
  `AGENTS.md` (Enforcement/Language-specific sections adapted to the
  conda + `python -m pytest` reality), `.claude/agents/reviewer.md`,
  `.pre-commit-config.yaml` (not installed — its ruff/mypy hooks are
  ahead of the codebase), `tests/conftest.py` (socket-level no-network
  guard; suite identical: 161 passed, 1 model skip), `.copier-answers.yml`
  (baseline: v0.1.0, git+ssh URL), and `.DS_Store` in `.gitignore`.
- Kept PreLexy's versions of README.md, CLAUDE.md, `.claude/settings.json`,
  and `.github/workflows/tests.yml`; did NOT adopt the template's
  pyproject.toml / ci.yml / src layout / test placeholder — the
  uv+ruff+mypy toolchain migration is an owner decision, flagged in the
  adoption PR.
- Friction: tag pushes and API ref creation are blocked for agent
  sessions (403) — the owner pushed the template's v0.1.0 tag themselves.
- Discovery: current pip NLTK needs `omw-2.0` (field note above).
