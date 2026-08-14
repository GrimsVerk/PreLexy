"""Session-level test bootstrap. Project-owned — the template does not ship a
root conftest.py, only tests/conftest.py, so nothing here is at risk from a
template update.

Why this exists: prelexy fetches the WordNet/OMW corpora lazily, on first use.
Inside a test that lazy fetch hits the outbound-socket guard in
tests/conftest.py and fails, so eight Dutch/OMW tests need the data already on
disk. Doing it here — once, at startup, before any test's monkeypatch is
active — keeps that requirement out of the CI workflow, which is a
template-owned file that a template update would overwrite.

No-op when the corpora are already present, which is the normal case.
"""

import contextlib

from prelexy.textproc import get_wordnet


def pytest_configure() -> None:
    # Failing soft is deliberate: with no data and no network the suite still
    # runs, and the tests that need the corpora fail with NLTK's own
    # LookupError, which names the missing resource.
    with contextlib.suppress(Exception):
        get_wordnet()
