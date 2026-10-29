# Vision: prelexy

What matters when two reasonable choices disagree. Not requirements (those are in `DESIGN.md`).
Write each line so an agent could cite it to pick one option over another.

Drafted 2026-10-29 from README "Why", ROADMAP and DECISIONS 001/007/013; the owner has not reviewed this wording yet.

## What this is for

Learn the exact vocabulary of real texts before or while you use them: read a heavy novel like *The Picture of Dorian Gray* without reaching for a dictionary, learn a new language (Dutch) from the words its podcasts actually use, and, later, learn a library's API from its docs. Feed in the text, drill the rare words in the terminal, and spaced repetition makes them stick.

## Priorities, in order

1. Entirely free and offline after setup. No paid services ever; free APIs only as a cached fallback (DECISIONS 007).
2. The use cases rank in order: literature first, languages from media second, programming docs third. A choice that helps a lower tier must not hurt a higher one, and nothing may preclude tier 2 or 3 (DECISIONS 001).
3. Questions must be hard but fair: distractors close in meaning but not synonyms, and rarity never picks them (DECISIONS 013, 022).
4. Learner progress persists per profile, and the review log is append-only, never overwritten (DECISIONS 006).

## Not doing

- GUI, web or mobile interfaces: terminal only.
- Audio beyond pronouncing the current word.
- Cloud sync or online accounts: profiles are local to the machine.
- Paid data sources or APIs.
