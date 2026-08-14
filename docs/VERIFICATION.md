# Verification ledger

What has actually been verified, and where. Update in place whenever the
state changes; a feature is not "done" until verified where it needs to be.

States: **sandbox** = tests / real-data checks in the Claude sandbox (which
has real WordNet and wordfreq but *no spaCy model and no audio device*);
**owner** = confirmed on the owner's machine; **UNVERIFIED** = never
observed working end-to-end anywhere.

| Feature | State | Evidence / next step |
|---|---|---|
| Ingest pipeline (extract, filter, rank, store) | owner | ~4.5k items from Dorian Gray; ranked words sane |
| Play sessions, per-profile persistence | owner | multi-day sessions on `default` profile |
| SM-2 spacing (intervals, due-first serving) | owner | different-day exact repeat = 1-day intervals maturing |
| Profile picker | owner | 2026-07-06 transcript shows the menu |
| Gloss-vs-gloss scoring + `--debug` scores | owner | 2026-07-06 transcript, all questions in band |
| Full test suite on the real model | owner | playtests/2026-07-06-pytest.txt: 103 passed, 0 skipped |
| Top-10 hardest-pool sampling | owner | playtests/2026-07-06-play.txt: 500 scanned, pool 10, scores 0.53–0.85 (was 0.45–0.6) |
| Near-synonym ceiling exclusion | owner | same transcript: 'undiscipline' 0.892 excluded for 'wilfulness' |
| Config quotas (new 7 / seen 3) + band keys | owner | scheduler line: "quotas 3 seen + 7 new" |
| Gloss sanitizer ("; ; ; -Author" residue) | owner | no residue in any 2026-07-06 transcript |
| `clean` command | owner | playtests/2026-07-06-clean.txt matches sandbox counts exactly |
| Pronunciation (`say`, `p` in session) | owner | owner confirmed audio in chat, 2026-07-06 |
| Distractor band values (0.45 / 0.85) | calibrated (sandbox analysis of owner data) | DECISIONS 022: values confirmed against 2026-07-06 playtests; synonym guard added for the gleefulness case; residual: cousin synonyms. Re-check feel at next owner playtest |
| Free-API definition fallback | UNVERIFIED (fails soft) | only fires for words WordNet lacks; low risk, mocked in tests |
| SessionStart hook + setup script | sandbox (script itself) | hook wiring confirmed on next fresh Claude session |
| Stage 1 polish set (instance/POS/length/synonym guards, contexts, config) | sandbox | owner: next `--debug play` should feel harder and read cleaner |
| GitHub Actions CI | verified (GitHub runner) | run 362b31f green after dropping the pip-cache option; earlier runs all failed pre-pytest |
| v2: OMW English glosses for Dutch words | sandbox (real OMW data) | offline end-to-end Dutch MCQ in tests; owner run pending |
| v2: kaikki gloss importer | sandbox (synthetic extract) | owner: real kaikki Dutch file (commands below) |
| v2: subtitle (.srt/.vtt) ingestion | sandbox | owner: ingest a real podcast transcript |
| v2: profile language memory | sandbox | owner: play once with --language nl, then without |
| v2: Dutch end-to-end (real model + real transcript) | owner | playtests/2026-07-07-play-nl.txt: 3/3 with English glosses on a real podcast transcript (1,685 items). Known issues → Stage 2b: 7/10 words had no gloss and were suspended (need un-suspend on import + raw-data importer); form-of glosses ("inflection of abonneren:") are useless as answers |
| v2: Dutch pronunciation | owner (works; quality poor) | owner 2026-07-07: audio plays, voice bad in both languages — TTS upgrade parked in Deferred |

| v3: docs ingestion + code-mode questions | sandbox (synthetic Sphinx tree) | end-to-end play verified offline; owner: real stdlib run below |
| v3: full Python stdlib corpus (real model) | AWAITING OWNER | commands below |
| Template toolchain: ruff + mypy --strict + pytest via uv | sandbox | `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` (34 files clean), `uv run pytest` (161 passed, 1 skipped) — all run 2026-08-14 |
| `ci.yml` WordNet fetch step | UNVERIFIED (sandbox cannot run it) | NLTK refuses proxied downloads and this sandbox proxies all egress; the command matches the one `tests.yml` ran green on GitHub. Owner/CI: confirm the `checks` job goes green on the first run |
| `ci.yml` gate jobs (plan, template-sync, secrets, test-the-tests) | UNVERIFIED | never executed — they arrive with this change. `template-sync` also needs a `TEMPLATE_TOKEN` repository Actions secret, since the template repo is private |

## Owner verification commands — v3 (Python docs)

```bash
# download the official docs once (~10 MB zip). The archive name carries
# the current micro version (python-3.13.x-docs-html.zip), so resolve it
# from the download page first; -f makes curl fail loudly on a 404.
NAME=$(curl -fsL https://docs.python.org/3/download.html | grep -o 'python-3[^"]*-docs-html\.zip' | head -1)
curl -fL -o python-docs.zip "https://docs.python.org/3/archives/$NAME"
unzip -q python-docs.zip -d data/

# ingest the WHOLE stdlib (default), then play
python -m prelexy ingest-docs data/python-3.*-docs-html
STAMP=$(date +%F)
python -m prelexy --debug play --language python 2>&1 | tee docs/playtests/$STAMP-play-py.txt

# focused study is the option, not the default:
#   python -m prelexy ingest-docs <dir> --modules itertools,functools
```

## Owner verification commands — Stage 2b (raw glosses + YouTube)

```bash
# yt-dlp does the YouTube fetching (one-time)
pip install yt-dlp

# the future-proof gloss source: the raw wiktextract dump (~2–3 GB
# download, all languages; the importer streams the .gz directly and
# filters to your language — no need to decompress). If the URL moved,
# use the "raw wiktextract data" link on kaikki.org/dictionary/rawdata.html
curl -fL -o raw-wiktextract-data.jsonl.gz \
  https://kaikki.org/dictionary/raw-wiktextract-data.jsonl.gz
python -m prelexy import-glosses raw-wiktextract-data.jsonl.gz --language nl
# expect: form-of answers gone, previously set-aside words back in play

# pods: save your channel once, then sync whenever
python -m prelexy pods add https://www.youtube.com/@tweakers/podcasts --language nl
python -m prelexy pods sync --ingest
python -m prelexy play   # Dutch remembered on your profile
```

## Owner verification commands — v2 (Dutch)

```bash
# one-time: the Dutch spaCy model
python -m spacy download nl_core_news_md

# ingest a real Dutch podcast transcript (.txt, .srt, or .vtt all work)
python -m prelexy ingest path/to/episode.srt --language nl
python -m prelexy words --language nl --limit 20

# optional but recommended: fill OMW's gloss gaps from Wiktionary.
# Download the Dutch extract (kaikki.org → Dictionaries → Dutch,
# "senses" JSONL, ~100+ MB), then:
python -m prelexy import-glosses path/to/kaikki.org-dictionary-Dutch.jsonl --language nl

# play in Dutch (remembered per profile after the first time)
STAMP=$(date +%F)
python -m prelexy --debug play --language nl 2>&1 | tee docs/playtests/$STAMP-play-nl.txt

# Dutch pronunciation (report in chat how it sounds)
python -m prelexy say fiets --language nl

git add docs/playtests
git commit -m "Dutch playtest transcripts $STAMP"
git push origin claude
```

## Owner verification commands

Run from the repo root (the `PreLexy` folder, branch `claude`). Each
command shows its output live **and** saves it where future sessions can
read it. Commit and push the transcripts when done.

```bash
mkdir -p docs/playtests
STAMP=$(date +%F)

# 0. one-time: regenerate the config file with the current keys
rm -f ~/.config/prelexy/config.toml

# 1. full test suite on the real model (includes the test the sandbox skips)
python -m pytest -q 2>&1 | tee docs/playtests/$STAMP-pytest.txt

# 2. band-calibration data: a debug question, then a full debug session
python -m prelexy --debug question vermilion 2>&1 | tee docs/playtests/$STAMP-question.txt
python -m prelexy --debug play 2>&1 | tee docs/playtests/$STAMP-play.txt

# 3. pronunciation — audio can't be captured to a file; say yes/no in chat
python -m prelexy say vermilion

# 4. the cleaner against the real corpus (writes dorian_gray_...cleaned.txt)
python -m prelexy clean data/corpora/dorian_gray_oscar_wilde.txt 2>&1 | tee docs/playtests/$STAMP-clean.txt

# 5. share everything with the next session
git add docs/playtests
git commit -m "Playtest transcripts $STAMP"
git push origin claude
```
