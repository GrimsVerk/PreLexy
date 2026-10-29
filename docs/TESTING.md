# Owner testing checklist

For the first real sessions. Real spaCy models and audio exist only on the
owner's machine, so these are the things CI cannot tell us. Setup is in the
README. Exact download commands for items 2 and 3 are in
[VERIFICATION.md](VERIFICATION.md) ("Owner verification commands").

- [ ] **Fresh install.** `uv sync`, install `en_core_web_md`, run `uv run prelexy --help`.
      Then try a command without a model (e.g. `ingest --language nl` before
      downloading the Dutch model): you should see one message naming the exact
      `spacy download` command, no traceback.
- [ ] **v3 full-stdlib check.** Download the Python docs HTML, `prelexy ingest-docs <dir>`,
      then `prelexy --debug play --language python`. Look for: sensible items,
      readable signatures/descriptions, distractors that are plausible but wrong.
- [ ] **Stage 2b downloads.** `import-glosses` on the raw wiktextract dump
      (form-of answers should be gone, set-aside Dutch words back in play) and
      `pods add` / `pods sync --ingest` with yt-dlp.
- [ ] **Distractor-feel playtest.** Play a few `--debug` sessions in English and
      Dutch. Note questions where a wrong option is really a synonym of the
      answer (too easy to confuse unfairly) or obviously absurd (too easy).
      Tuning knobs: `similarity_floor`, `similarity_ceiling`, `pool_size` in
      `~/.config/prelexy/config.toml`.
- [ ] **Day-to-day.** Play across a few days: reviews come back on schedule,
      `p` pronounces, quitting mid-session keeps progress.

## Reporting problems

Run the command again with `--debug` and paste the output (stderr is where it
goes, so `2>&1 | tee out.txt`) into a
[GitHub issue](https://github.com/GrimsVerk/PreLexy/issues), or into
`next-steps.md` as a task. Include the command, what you expected, and the
Python version (`uv run python --version`). For a bad question, paste the
`[mcq]` score lines and the word. Longer transcripts can go in
`docs/playtests/` (see VERIFICATION.md).
