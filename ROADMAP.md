# Roadmap

## v1 — "Read Dorian Gray without a dictionary" (tier 1, English)

v1 is done when this works end to end:

> Point PreLexy at a `.txt` book → it extracts and ranks the words you likely don't
> know → you run a multiple-choice session in the terminal ("pick the correct
> definition") → your progress persists between sessions under your profile →
> previously seen words come back for review when the scheduler says they're due.

### Success criteria

- [ ] `prelexy ingest <file>` extracts lemma-based items from an English text,
      filters noise (stopwords, proper nouns, dictionary-membership check), ranks
      candidates by rarity, and stores them
- [ ] `prelexy play` runs an MCQ session with real definitions and plausible
      distractors, and shows the example sentence from the source text
- [ ] Progress is per profile and survives program restarts
- [ ] Reviews come due on schedule, and the scheduler is swappable behind an
      interface without touching any other code
- [ ] Works fully offline after initial setup (API used only as a fallback for
      missing definitions, with results cached locally)

### Phases

1. **Extraction CLI** — ingest a text: tokenize, apply the extraction policy
   (lemmas for English), filter noise, rank by frequency/rarity; persist
   sources/items/occurrences to SQLite.
2. **MCQ generation** — definition lookup through the offline-first chain
   (WordNet → cache → free API); distractor selection (same POS,
   frequency-matched, similarity band).
3. **Session loop + saves** — terminal UI, profiles, answer recording, and the
   append-only review log.
4. **Scheduler** — the `Scheduler` interface with SM-2 as the default
   implementation; sessions composed from due reviews plus new items.
5. **Polish** — ranking quality, distractor quality tuning, UX friction, docs.

## Post-v1

- **v1.x — L2 mode (tier 2):** surface-form extraction policy (learn "was", not
  its lemma — conjugations are absorbed from input volume, not tables); bilingual
  definitions with the gloss in the learner's strong language (likely
  Wiktionary-derived data); per-profile language settings.
- **v2 — code-docs mode (tier 3, design-only today):** ingest programming/library
  documentation; custom-trained embeddings plugged in behind the existing
  `SimilarityProvider` interface; `language` values like `python`. No
  implementation until tiers 1–2 are solid.
- **Exploratory:** an RL-based personalized scheduler trained on each player's
  review log, plugged in behind the `Scheduler` interface.

## Out of scope (all versions, until explicitly revisited)

- GUI, web, or mobile interfaces — terminal only
- Audio playback or speech
- Cloud sync or online accounts — profiles are local to the machine
- Paid data sources or APIs — the project stays entirely free
