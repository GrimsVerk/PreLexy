# PreLexy

A terminal vocabulary game. Feed it real texts (books, subtitles, podcast
transcripts, programming docs); it finds the words you probably don't know and
drills them with multiple-choice questions, scheduling reviews with spaced
repetition (SM-2) so they stick. Free and offline-first.

Three flows, one tool:

1. **Read hard books without stopping.** Pre-teach the rare words of a specific
   novel before you read it.
2. **Learn a language from real media.** Ingest a Dutch podcast transcript and
   learn exactly the words it uses (definitions in English).
3. **Learn a programming language from its docs.** Ingest the Python standard
   library docs and drill the functions and classes.

## Install

Needs [uv](https://docs.astral.sh/uv/) and Python 3.11 to 3.13.

```bash
git clone https://github.com/GrimsVerk/PreLexy && cd PreLexy
uv sync

# one-time model download (English; add nl_core_news_md for Dutch).
# The project venv has no pip, so give it one without letting `uv run` remove it:
uv pip install pip
uv run --no-sync python -m spacy download en_core_web_md
uv run prelexy --help
```

WordNet data is fetched automatically on first use. If a model or data file is
missing, PreLexy prints the exact command to install it.

To run it as plain `prelexy` (no `uv run` prefix), activate the venv
(`source .venv/bin/activate`) or run `uv tool install .` once. `python -m
prelexy` works the same. (`environment.yml` is the owner's conda alternative,
kept in step with `pyproject.toml` by hand.)

## Quickstart

```bash
# 1. A book (a Dorian Gray copy is bundled)
prelexy ingest data/corpora/dorian_gray_oscar_wilde.txt
prelexy words --limit 20          # rarest first
prelexy play                      # pick or create a profile, then drill

# 2. A language from media (.txt, .srt or .vtt)
prelexy ingest episode.srt --language nl
prelexy play --language nl        # remembered per profile afterwards
#   from YouTube instead (needs `uv pip install yt-dlp`):
prelexy pods add https://www.youtube.com/@tweakers/podcasts --language nl
prelexy pods sync --ingest
#   more definitions from Wiktionary (raw wiktextract dump from kaikki.org):
prelexy import-glosses raw-wiktextract-data.jsonl.gz --language nl

# 3. Python from its docs (unpack the HTML archive from docs.python.org/3/download.html)
prelexy ingest-docs data/python-3.13-docs-html
prelexy play --language python
```

During a question: answer with the option number, `p` to hear the word, `q` to
quit. Also: `prelexy question WORD` previews one question with the answer
marked, `prelexy say WORD` pronounces a word, `prelexy clean FILE` tidies OCR
junk before ingesting. Run any command with `--help`.

## Where things live

- Database (words, progress, profiles): `~/.local/share/prelexy/prelexy.db`.
  Override with `--db PATH`, `PRELEXY_DB` or `db_path` in the config.
- Config: `~/.config/prelexy/config.toml`, created with commented defaults on
  first run (see below).
- Your texts: wherever you like; `data/corpora/` holds the bundled one and
  `data/pods/` is where `pods sync` saves transcripts.

## Debugging

`prelexy --debug <command>` prints diagnostics to stderr (distractor scores,
session mix, scheduling). To report a problem, paste that output; see
[docs/TESTING.md](docs/TESTING.md).

## Configuration

`~/.config/prelexy/config.toml` is created with commented defaults on first
run. It currently holds:

- `new_words` — new words per practice session, default 7
- `seen_words` — previously seen words (due reviews) per session, default 3.
  The quotas trump the review backlog: reviews never crowd new words out,
  and when either kind runs out the other fills the gap.
- `similarity_floor` / `similarity_ceiling` — the distractor band applied to
  definition-vs-definition similarity. Above the ceiling a candidate reads
  as a near-synonym and is excluded; the floor is a soft preference for
  plausible-but-wrong options. Check real scores with
  `prelexy --debug play` before tuning.
- `default_profile` — skip the who-is-playing menu (empty = ask)
- `default_language` — assumed by every command without `--language`
- `db_path` — database location (empty = the XDG default; `--db` and
  `PRELEXY_DB` still override)
- `tts_voice` — pronunciation voice (espeak-ng code or macOS voice name;
  empty = engine default)
- `pool_size` — distractors are sampled from this many of the hardest
  candidates; smaller = consistently harder, larger = more variety
- `show_context` — whether the source sentence appears after answering

CLI flags override the word counts per session:

```bash
prelexy play --new 12 --seen 8
```

(If you have a config file from an earlier version, retired keys like
`session_length`/`new_ratio` are ignored; delete the file to regenerate the
current template.)

## License

MIT, see [LICENSE](LICENSE). The bundled corpus in `data/corpora/` is Oscar
Wilde's *The Picture of Dorian Gray* (public domain) from the Standard Ebooks
edition, released under CC0 1.0.

## Repository layout

- `prelexy/` — the Python package (CLI, text processing, game engine)
- `data/corpora/` — input texts to learn from
- `docs/` — vision ([VISION.md](docs/VISION.md)), design
  ([DESIGN.md](docs/DESIGN.md)), decision log
  ([DECISIONS.md](docs/DECISIONS.md)), work queue
  ([BACKLOG.md](docs/BACKLOG.md)), session journal
  ([JOURNAL.md](docs/JOURNAL.md)), and verification ledger
  ([VERIFICATION.md](docs/VERIFICATION.md))
- [`ROADMAP.md`](ROADMAP.md) — goals, phases, definition of done
- `AGENTS.md` (with `CLAUDE.md` pointing to it), `.claude/` — working rules and
  setup for agents; `next-steps.md` — work in flight

## Develop

```sh
uv sync                     # install dev tools from pyproject.toml / uv.lock
uv run pre-commit install   # checks on every commit
```

Agents work on a branch, run the checks in `AGENTS.md` locally, then open and
merge a PR. CI (`.github/workflows/ci.yml`) runs one job on every push to
`main`: gitleaks, ruff, mypy and pytest.

## Template updates

`scripts/update-from-template.sh` pulls in the latest template on a branch and
opens a PR. If the template changed a dependency pin, run `uv lock` on that
branch too, or `uv sync --locked` fails in CI.


## License

MIT, see [LICENSE](LICENSE). The bundled corpus in `data/corpora/` is Oscar
Wilde's *The Picture of Dorian Gray* (public domain) from the Standard Ebooks
edition, released under CC0 1.0.
