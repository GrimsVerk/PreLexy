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
| v2: Dutch end-to-end (real model + real transcript) | AWAITING OWNER | ROADMAP v2 success criterion — commands below |
| v2: Dutch pronunciation voice quality | AWAITING OWNER | `prelexy say fiets --language nl` — report in chat |

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
