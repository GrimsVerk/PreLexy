# prelexy: rules for agents

Terminal vocabulary game: ingest real texts, extract the rare words, and drill them with spaced repetition.

## Every session

- Read `next-steps.md` first. Write your task there before you start; delete it when done. Nothing may live only in chat: the next session starts fresh with only these files.
- One feature per session.
- When unsure, pick a reasonable default, note the assumption (in `docs/DECISIONS.md` if it will matter later), and keep going.

## Files

- `docs/VISION.md`: what matters, the tiebreaker. `docs/DESIGN.md`: what we are building. `ROADMAP.md`: versions and success criteria.
- `docs/DECISIONS.md`: numbered owner rulings and why, newest at the bottom. Don't relitigate; to change one, ask the owner and add a superseding entry.
- `docs/BACKLOG.md`: Proposed ideas need the owner's OK before you build them; never start Deferred items.
- `docs/VERIFICATION.md`: what was verified where. `docs/JOURNAL.md` Field notes: standing operational facts.

## Working

- Non-trivial work: plan it in plan mode first. `/adversarial-review` attacks a plan before you build it (optional).
- A feature too big for one context: `/orchestrate`.
- Work on a branch, never on `main`. Run the checks below locally, then open a PR and merge it (`gh pr merge --rebase --delete-branch`). CI runs only on `main`; a red `main` is the next task.
- Never force-push, rewrite pushed history, or skip hooks (`--no-verify`).
- Paths in repo files are relative, so any computer can resume the work. Machine-specific values go in one gitignored local file with a committed `.example`.

## Project rules

- Free and offline-first: no paid services; free APIs only as a cached fallback. No new dependencies without asking the owner; they must be MIT-compatible.
- Keep the seams: scheduler and similarity stay swappable behind their protocols; rarity never influences distractor selection (DECISIONS 013); nothing may preclude tier 2 (languages from media) or tier 3 (programming docs).
- All SQL lives in `prelexy/store.py`. Diagnostics go through `prelexy/debug.py` (add a channel, not a new mechanism).
- Package at `prelexy/` (not `src/`), Python 3.11-3.13 (`requires-python`, DECISIONS 028). `environment.yml` (the owner's conda env) is kept in step with `pyproject.toml` by hand.
- Real spaCy models and audio exist only on the owner's machine: ask for `prelexy --debug` transcripts instead of claiming it works, and update `docs/VERIFICATION.md`.

## Checks

```sh
uv sync && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
```

## Tests

- Test behaviour, not implementation. Keep tests that protect what matters: core user flows, anything that can lose data, payments.
- Tests run offline and deterministically: no real network, clock or randomness. The root `conftest.py` fetches the WordNet/OMW corpora once before the network guard starts; model-dependent tests skip without the model.
- For logic with a clear interface, the `test-writer` subagent can write tests from the spec while you write the code.

## Processes and agents

- Never stop processes or agents by name pattern (`pkill -f`, `killall`): other agents run identical commands. Stop only what you started, by its own ID.
- Before a big fan-out of subagents, check remaining usage; hitting the limit mid-run kills them all.

## Licensing

MIT (see `LICENSE`), chosen by the owner. Don't change it or add another license.
