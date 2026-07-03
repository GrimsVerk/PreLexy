import json
from pathlib import Path

import click

from prelexy.store import Store
from prelexy.textproc import extract_candidates

_db_option = click.option(
    "--db",
    "db_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    envvar="PRELEXY_DB",
    help="Database file [default: ~/.local/share/prelexy/prelexy.db]",
)


@click.group()
def cli():
    """PreLexy — learn the vocabulary of the texts you actually read."""


@cli.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--language", default="en", show_default=True)
@click.option("--title", default=None, help="Source title [default: the file name]")
@click.option(
    "--kind",
    default="book",
    show_default=True,
    type=click.Choice(["book", "subtitles", "transcript", "docs"]),
)
@_db_option
def ingest(file, language, title, kind, db_path):
    """Extract learnable vocabulary from FILE and store it."""
    path = str(file.resolve())
    with Store(db_path) as store:
        if store.find_source_by_path(path) is not None:
            raise click.ClickException(
                f"{file} was already ingested; re-ingesting would double its counts."
            )
        text = file.read_text(encoding="utf-8", errors="replace")
        click.echo(f"Extracting from {file.name} … (first run loads models, be patient)")
        try:
            candidates = extract_candidates(text, language)
        except (OSError, ValueError) as error:  # missing/unsupported spaCy model
            raise click.ClickException(str(error)) from error
        source_id = store.add_source(title or file.stem, language, kind, path)
        n_occurrences = 0
        for candidate in candidates:
            item_id = store.get_or_create_item(
                language,
                candidate.form,
                lemma=candidate.lemma,
                pos=candidate.pos,
                metadata={"zipf": candidate.zipf},
            )
            store.add_occurrences(item_id, source_id, candidate.occurrences)
            n_occurrences += len(candidate.occurrences)
    click.echo(f"Stored {len(candidates)} items ({n_occurrences} occurrences).")
    if candidates:
        click.echo("\nRarest finds:")
        for candidate in candidates[:10]:
            click.echo(
                f"  {candidate.form:<22} zipf {candidate.zipf:4.2f}"
                f"  ×{len(candidate.occurrences)}"
            )


@cli.command()
@click.option("--language", default="en", show_default=True)
@click.option("--limit", default=20, show_default=True)
@_db_option
def words(language, limit, db_path):
    """List stored vocabulary, rarest first."""
    with Store(db_path) as store:
        rows = store.list_items(language)
    if not rows:
        raise click.ClickException(
            f"No {language!r} items stored yet — run `prelexy ingest <file>` first."
        )
    ranked = sorted(rows, key=lambda r: json.loads(r["metadata"]).get("zipf", 0.0))
    click.echo(f"{'form':<22} {'pos':<6} {'zipf':>5}  occurrences")
    for row in ranked[:limit]:
        zipf = json.loads(row["metadata"]).get("zipf", 0.0)
        click.echo(
            f"{row['form']:<22} {row['pos'] or '?':<6} {zipf:>5.2f}  {row['n_occurrences']}"
        )


@cli.command()
@click.argument("form")
@click.option("--language", default="en", show_default=True)
@_db_option
def question(form, language, db_path):
    """Preview a multiple-choice question for a stored word (* marks the answer)."""
    from prelexy.mcq import build_question
    from prelexy.similarity import SpacyVectors
    from prelexy.textproc import load_nlp

    with Store(db_path) as store:
        item = store.find_item(language, form)
        if item is None:
            raise click.ClickException(
                f"{form!r} is not stored — run `prelexy ingest` on a text containing it."
            )
        try:
            similarity = SpacyVectors(load_nlp(language))
        except (OSError, ValueError):
            similarity = None  # no vectors: distractors matched by POS and rarity only
        built = build_question(store, item, similarity=similarity)
        if built is None:
            raise click.ClickException(
                f"Couldn't build a question for {form!r} — no definition or no "
                "distractors available yet."
            )
    if built.context:
        click.echo(f"“{built.context}”\n")
    click.echo(f"What does “{built.form}” mean?\n")
    for index, option in enumerate(built.options):
        marker = "*" if index == built.answer else " "
        click.echo(f" {marker} {index + 1}. {option}")
    click.echo("\n(* marks the correct answer — preview mode)")


@cli.command()
@click.option(
    "--profile",
    "profile_name",
    default="default",
    show_default=True,
    help="Player profile; each profile tracks its own progress.",
)
@click.option("--language", default="en", show_default=True)
@click.option("--length", "n_questions", default=10, show_default=True,
              help="Questions per session.")
@_db_option
def play(profile_name, language, n_questions, db_path):
    """Start a practice session."""
    from prelexy.scheduler import SimpleScheduler
    from prelexy.session import run_session
    from prelexy.similarity import SpacyVectors
    from prelexy.textproc import load_nlp

    try:
        similarity = SpacyVectors(load_nlp(language))
    except (OSError, ValueError):
        similarity = None  # no vectors: distractors matched by POS and rarity only
    with Store(db_path) as store:
        profile_id = store.get_or_create_profile(profile_name)
        run_session(
            store,
            profile_id,
            language,
            SimpleScheduler(),
            similarity=similarity,
            n_questions=n_questions,
        )
