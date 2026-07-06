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
| Distractor band values (0.45 / 0.85) | UNCALIBRATED | needs `[mcq]` score data from post-top-10 playtests |
| Top-10 hardest-pool sampling | sandbox | owner: next `--debug play` should show scores clustering higher |
| Config quotas (new 7 / seen 3) + band keys | sandbox | owner: regenerate config (command 0), then play |
| Gloss sanitizer ("; ; ; -Author" residue) | sandbox (real WordNet) | owner: glosses should be clean next play |
| `clean` command | sandbox (real corpus: 1415 pipes, 53 hyphens) | owner: command 4 below |
| Pronunciation (`say`, `p` in session) | UNVERIFIED | no audio in sandbox — owner: command 3, report yes/no in chat |
| Free-API definition fallback | UNVERIFIED (fails soft) | only fires for words WordNet lacks; low risk, mocked in tests |
| SessionStart hook + setup script | sandbox (script itself) | hook wiring confirmed on next fresh Claude session |

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
