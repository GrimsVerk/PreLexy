# PreLexy — agent guidelines

Canonical working instructions for any coding agent in this repository.
Tool-specific entry points (e.g. `CLAUDE.md`) only point here; rules are
never duplicated elsewhere.

## Workflow

**Branches.** Never commit to the default branch directly; work on a branch
and let the owner merge. Never force-push or rewrite history on a branch
that has been pushed.

**Commits.** One conceptually contained commit per unit of work, pushed
when complete, with an imperative one-line message. The test suite must
pass before every commit. Documentation is updated in the same commit as
the code it describes — docs never lag the code.

**Tests.** New behaviour comes with tests in the same commit. The suite
runs offline and deterministically; a test that needs an unavailable
optional resource skips with a clear reason rather than failing.

**Dependencies.** No new dependencies without the owner's approval — ask
first, in chat.

**Decisions.** Design choices and owner rulings are recorded in
`docs/DECISIONS.md` (ADR-lite: one dated entry per decision, newest at the
bottom; create the file on the first decision). A recorded ruling is never
silently reversed — to change one, argue the case in chat, wait for the
owner, then add a superseding entry. History is never rewritten.

**Work queue.** When working unattended, implement only items the owner
has approved in `docs/BACKLOG.md` ("Approved" section, top to bottom), and
keep going until the list is done or you are truly blocked. New ideas are
written into "Proposed" as text — never coded unprompted. If an attempt is
stuck after 3–5 tries, log what was tried and why it failed, then move on;
if the blocker gates everything, build the simplest clearly-marked
stand-in and leave the real fix for the owner.

**Memory.** Chat is not storage. Anything a future session (or a different
agent) would need is written into the repository in the same unit of work:
decisions → `docs/DECISIONS.md`, work items and ideas → `docs/BACKLOG.md`,
session notes and hand-offs → `docs/JOURNAL.md` (one dated entry per
working session), user-facing behaviour → `README.md`.

**Honesty about verification.** Never claim something is verified in an
environment where you could not observe it. Record what was verified where;
"CI added" is not "CI verified" until a run has actually passed. When only
the owner can verify something, say exactly what to run and ask for the
output.

**Ambiguity.** Prefer stating what you need in chat and continuing on best
judgment over blocking; the owner reads chat. Stop and ask only when truly
blocked on something only the owner can provide.

## Enforcement

CI (`.github/workflows/tests.yml`) runs the test suite on every push and
pull request, regardless of which tool or agent wrote the code. Git-level
hooks live in `.pre-commit-config.yaml` (enable with `pre-commit install`);
note that its ruff/mypy hooks are ahead of this codebase — adopting those
toolchains is an open owner decision, and until then only the gitleaks
hook is expected to pass. A failing gate is fixed, never bypassed: no
`--no-verify`, no skipping or weakening checks to get green.

## Language-specific

Python 3.11, conda-managed (`environment.yml`), package at `prelexy/`, no
build step. Run the suite with `python -m pytest`. The offline rule is
enforced by the autouse fixture in `tests/conftest.py` (plus per-module
`no_network` fixtures). There is no lint/format/type configuration yet —
introducing ruff/mypy/`pyproject.toml` is tracked as an open decision, not
something to adopt unilaterally.
