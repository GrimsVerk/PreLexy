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
        candidates = extract_candidates(text, language)
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
def play():
    """Start a practice session."""
    click.echo("Practice sessions arrive in phase 3 — nothing to play yet.")
    click.echo("Try `ingest` and `words` in the meantime; see ROADMAP.md.")
