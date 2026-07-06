#!/usr/bin/env bash
# SessionStart hook: make a fresh Claude Code sandbox able to run the test
# suite. Idempotent and fast when everything is already present; never
# fails the session (always exits 0).

set -u

missing=$(python - <<'EOF'
import importlib.util
needed = {"click": "click", "nltk": "nltk", "spacy": "spacy",
          "wordfreq": "wordfreq", "pytest": "pytest"}
print(" ".join(pkg for mod, pkg in needed.items()
               if importlib.util.find_spec(mod) is None))
EOF
) || missing=""

if [ -n "$missing" ]; then
    echo "prelexy setup: installing $missing"
    pip install --quiet $missing || echo "prelexy setup: pip install failed (continuing)"
fi

python - <<'EOF' || echo "prelexy setup: nltk data fetch failed (continuing)"
import nltk
try:
    from nltk.corpus import wordnet
    wordnet.ensure_loaded()
except LookupError:
    nltk.download("wordnet", quiet=True)
    nltk.download("omw-1.4", quiet=True)
EOF

# spaCy *models* are not downloadable in this sandbox (GitHub releases are
# blocked by the egress policy) — model-dependent tests skip; that is expected.
exit 0
