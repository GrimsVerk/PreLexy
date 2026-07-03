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

Early planning / skeleton stage. The design is documented; the game is not yet
written. See [ROADMAP.md](ROADMAP.md) for goals and phases, and
[docs/DESIGN.md](docs/DESIGN.md) for the architecture and data model.

## Quickstart (development)

```bash
conda env create -f environment.yml
conda activate prelexy

# one-time data downloads (everything runs offline afterwards)
python -m nltk.downloader punkt wordnet omw-1.4
python -m spacy download en_core_web_md

python -m prelexy play   # placeholder for now
```

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
