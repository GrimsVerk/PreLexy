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

Early development. Phase 1 (the extraction CLI) is implemented: `ingest`
extracts, filters, and ranks vocabulary from a text into a local SQLite
database, and `words` lists it. The game itself (practice sessions, scheduling)
is not written yet. See [ROADMAP.md](ROADMAP.md) for goals and phases, and
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
# extract the vocabulary of a text into the local database
python -m prelexy ingest data/corpora/dorian_gray_oscar_wilde.txt

# list the stored words, rarest first
python -m prelexy words --limit 20

# run the test suite
python -m pytest
```

The database lives at `~/.local/share/prelexy/prelexy.db` by default; every
command accepts `--db <path>` (or the `PRELEXY_DB` environment variable) to
use a different one.

## Scope

**In scope:** multiple languages, multiple user profiles on the same machine,
entirely free (offline dictionaries first, free APIs only as a cached fallback).

**Out of scope:** GUI/web/mobile interfaces, audio playback, cloud sync.

## Repository layout

- `prelexy/` — the Python package (CLI, text processing, game engine)
- `data/corpora/` — input texts to learn from
- `docs/` — design ([DESIGN.md](docs/DESIGN.md)) and decision log
  ([DECISIONS.md](docs/DECISIONS.md))
- [`ROADMAP.md`](ROADMAP.md) — goals, phases, definition of done
