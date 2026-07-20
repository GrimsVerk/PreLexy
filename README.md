# PreLexy

PreLexy is a terminal-based vocabulary learning game. Feed it real texts — books,
subtitles, podcast transcripts — and it extracts the words you don't know yet,
drills them with multiple-choice exercises, and schedules reviews with spaced
repetition so they stick.

## Why

Three use cases drive the design, in priority order:

1. **Read heavy literature without interruption** *(v1 target).* You're fluent in
   English, but a novel like *The Picture of Dorian Gray* keeps sending you to the
   dictionary and breaking the flow of the story. PreLexy pre-teaches the hard
   vocabulary of a specific book so you can read it uninterrupted.
2. **Learn a new language from real media.** Feed in transcripts of, say, a Dutch
   podcast and memorize exactly the words it uses — surface forms only, no
   conjugation tables. With enough input, grammar is absorbed naturally by
   listening, instead of studied.
3. **Learn programming libraries from their docs** *(future, design-only).* Feed in
   the official Python docs, or the docs of a library you want to learn, and drill
   methods and functions the same way. This needs custom-trained embeddings, so it
   is not being built yet — but the architecture keeps the door open.

## Status

Early development. Phases 1–3 are implemented: `ingest` extracts, filters, and
ranks vocabulary from a text into a local SQLite database, `words` lists it,
`question` previews a generated multiple-choice question (definitions via
WordNet with a cached free-API fallback), and `play` runs an interactive
practice session that tracks per-profile progress, logs every answer, and
schedules reviews with spaced repetition (SM-2): correct answers push a word
further into the future, misses bring it back tomorrow.

Learning a new language (v2) works too: ingest a Dutch podcast transcript
(plain text or `.srt`/`.vtt`) and practice the exact words it uses, with
definitions in English — `--language nl` once, remembered per profile.
See [ROADMAP.md](ROADMAP.md) for goals and phases, and
[docs/DESIGN.md](docs/DESIGN.md) for the architecture and data model.

## Setup

First time:

```bash
conda env create -f environment.yml
conda activate prelexy

# one-time model/data downloads (everything runs offline afterwards)
python -m spacy download en_core_web_md
python -m nltk.downloader wordnet omw-1.4   # auto-fetched on first run if skipped
```

After pulling changes that touch `environment.yml`, refresh the existing
environment instead:

```bash
conda env update -f environment.yml --prune
```

## Usage

```bash
# optional: clean OCR artifacts (| for I, split hyphenation, page junk)
# out of a text first — writes <name>.cleaned.txt beside the input
python -m prelexy clean data/corpora/dorian_gray_oscar_wilde.txt

# extract the vocabulary of a text into the local database — one ingest
# for everything: books, plain transcripts, and .srt/.vtt subtitles
# (e.g. an English film's subtitles), in any supported language
python -m prelexy ingest data/corpora/dorian_gray_oscar_wilde.txt

# list the stored words, rarest first
python -m prelexy words --limit 20

# preview a multiple-choice question for a stored word
python -m prelexy question vermilion

# play a practice session — asks who is playing (pick a saved profile
# or create one); --profile skips the menu. During a question, answer
# with p to hear the word pronounced, q to quit.
python -m prelexy play
python -m prelexy play --profile alice --length 20

# pronounce any word outside a session
python -m prelexy say vermilion

# learn a language from a podcast: save the channel once, sync new
# episodes' transcripts straight from YouTube (needs `pip install yt-dlp`
# and the language's spaCy model: python -m spacy download nl_core_news_md)
python -m prelexy pods add https://www.youtube.com/@tweakers/podcasts --language nl
python -m prelexy pods sync --ingest
python -m prelexy play --language nl   # remembered per profile afterwards

# one-off fetch and manual ingest also work
python -m prelexy fetch https://www.youtube.com/watch?v=... --language nl --ingest
python -m prelexy ingest episode.srt --language nl

# top up definitions from Wiktionary (raw wiktextract dump from
# kaikki.org/dictionary/rawdata.html; .gz streamed directly)
python -m prelexy import-glosses raw-wiktextract-data.jsonl.gz --language nl

# learn a programming language from its official docs (download the
# Sphinx HTML archive, e.g. docs.python.org/3 → "Download" → HTML)
python -m prelexy ingest-docs data/python-3.13-docs-html
python -m prelexy play --language python

# any command with diagnostic detail on stderr (distractor scores, session mix)
python -m prelexy --debug question vermilion

# run the test suite (CI runs it on every push too)
python -m pytest
```

The database lives at `~/.local/share/prelexy/prelexy.db` by default; every
command accepts `--db <path>` (or the `PRELEXY_DB` environment variable) to
use a different one.

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
  `python -m prelexy --debug play` before tuning.
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
python -m prelexy play --new 12 --seen 8
```

(If you have a config file from an earlier version, retired keys like
`session_length`/`new_ratio` are ignored; delete the file to regenerate the
current template.)

## Scope

**In scope:** multiple languages, multiple user profiles on the same machine,
entirely free (offline dictionaries first, free APIs only as a cached fallback).

**Out of scope:** GUI/web/mobile interfaces, audio playback, cloud sync.

## Repository layout

- `prelexy/` — the Python package (CLI, text processing, game engine)
- `data/corpora/` — input texts to learn from
- `docs/` — design ([DESIGN.md](docs/DESIGN.md)), decision log
  ([DECISIONS.md](docs/DECISIONS.md)), work queue
  ([BACKLOG.md](docs/BACKLOG.md)), session journal
  ([JOURNAL.md](docs/JOURNAL.md)), and verification ledger
  ([VERIFICATION.md](docs/VERIFICATION.md))
- [`ROADMAP.md`](ROADMAP.md) — goals, phases, definition of done
- `CLAUDE.md`, `.claude/` — working rules and setup for Claude Code sessions
