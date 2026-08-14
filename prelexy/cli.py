import json
from collections.abc import Sequence
from pathlib import Path

import click

from prelexy import debug
from prelexy.config import Config
from prelexy.docsproc import DocEntry
from prelexy.store import Store
from prelexy.textproc import Candidate, extract_candidates

_db_option = click.option(
    "--db",
    "db_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    envvar="PRELEXY_DB",
    help="Database file [default: db_path from the config file, else "
    "~/.local/share/prelexy/prelexy.db]",
)

_language_option = click.option(
    "--language",
    default=None,
    help="Language of the items [default: default_language from the config file]",
)


def _resolve_db(db_path: Path | None, config: Config) -> Path | None:
    """--db flag > PRELEXY_DB env (both land in db_path) > config > XDG."""
    if db_path:
        return db_path
    if config["db_path"]:
        return Path(config["db_path"]).expanduser()
    return None


def _validate_language(code: str) -> str:
    from prelexy.languages import UnsupportedLanguageError, get_language

    try:
        get_language(code)
    except UnsupportedLanguageError as error:
        raise click.ClickException(str(error)) from error
    return code


def _resolve_language(language: str | None, config: Config) -> str:
    return _validate_language(language or config["default_language"])


@click.group()
@click.option(
    "--debug",
    "debug_flag",
    is_flag=True,
    help="Print diagnostic detail to stderr (e.g. distractor scores).",
)
def cli(debug_flag: bool) -> None:
    """PreLexy — learn the vocabulary of the texts you actually read."""
    if debug_flag:
        debug.enable()


@cli.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@_language_option
@click.option("--title", default=None, help="Source title [default: the file name]")
@click.option(
    "--kind",
    default=None,
    type=click.Choice(["book", "subtitles", "transcript", "docs"]),
    help="[default: book, or subtitles for .srt/.vtt files]",
)
@_db_option
def ingest(
    file: Path,
    language: str | None,
    title: str | None,
    kind: str | None,
    db_path: Path | None,
) -> None:
    """Extract learnable vocabulary from FILE and store it.

    Plain text, .srt, and .vtt are accepted; subtitle files are converted
    to prose (timestamps and cue numbers stripped) before extraction.
    """
    config = _load_config_or_die()
    language = _resolve_language(language, config)
    with Store(_resolve_db(db_path, config)) as store:
        result = _ingest_file(store, file, language, title, kind)
        if result is None:
            raise click.ClickException(
                f"{file} was already ingested; re-ingesting would double its counts."
            )
    candidates, n_occurrences = result
    click.echo(f"Stored {len(candidates)} items ({n_occurrences} occurrences).")
    if candidates:
        click.echo("\nRarest finds:")
        for candidate in candidates[:10]:
            click.echo(
                f"  {candidate.form:<22} zipf {candidate.zipf:4.2f}  ×{len(candidate.occurrences)}"
            )


def _ingest_file(
    store: Store,
    file: Path,
    language: str,
    title: str | None = None,
    kind: str | None = None,
) -> tuple[list[Candidate], int] | None:
    """Extract and store one file; None when its path is already ingested."""
    from prelexy.clean import SUBTITLE_SUFFIXES, strip_subtitles

    path = str(file.resolve())
    if store.find_source_by_path(path) is not None:
        return None
    text = file.read_text(encoding="utf-8", errors="replace")
    if file.suffix.lower() in SUBTITLE_SUFFIXES:
        text = strip_subtitles(text)
        kind = kind or "subtitles"
    kind = kind or "book"
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
    return candidates, n_occurrences


@cli.command()
@_language_option
@click.option("--limit", default=20, show_default=True)
@_db_option
def words(language: str | None, limit: int, db_path: Path | None) -> None:
    """List stored vocabulary, rarest first."""
    config = _load_config_or_die()
    language = _resolve_language(language, config)
    with Store(_resolve_db(db_path, config)) as store:
        rows = store.list_items(language)
    if not rows:
        raise click.ClickException(
            f"No {language!r} items stored yet — run `prelexy ingest <file>` first."
        )
    ranked = sorted(rows, key=lambda r: json.loads(r["metadata"]).get("zipf", 0.0))
    click.echo(f"{'form':<22} {'pos':<6} {'zipf':>5}  occurrences")
    for row in ranked[:limit]:
        zipf = json.loads(row["metadata"]).get("zipf", 0.0)
        click.echo(f"{row['form']:<22} {row['pos'] or '?':<6} {zipf:>5.2f}  {row['n_occurrences']}")


@cli.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Where to write [default: <name>.cleaned.<ext> beside the input]",
)
def clean(file: Path, output: Path | None) -> None:
    """Clean a text file before ingesting it.

    Fixes common OCR artifacts; .srt/.vtt subtitle files are additionally
    converted to plain prose first.
    """
    from prelexy.clean import SUBTITLE_SUFFIXES, clean_text, strip_subtitles

    text = file.read_text(encoding="utf-8", errors="replace")
    if file.suffix.lower() in SUBTITLE_SUFFIXES:
        text = strip_subtitles(text)
    cleaned, counts = clean_text(text)
    output = output or file.with_suffix(".cleaned.txt")
    output.write_text(cleaned, encoding="utf-8")
    click.echo(f"Wrote {output}")
    for rule, count in counts.items():
        if count:
            click.echo(f"  {rule}: {count} fix(es)")
    if not any(counts.values()):
        click.echo("  (no artifacts found)")


@cli.command()
@click.argument("url")
@_language_option
@click.option(
    "--dest",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path("data/pods"),
    show_default=True,
    help="Where fetched subtitle files land.",
)
@click.option(
    "--ingest", "do_ingest", is_flag=True, help="Ingest the fetched subtitles immediately."
)
@_db_option
def fetch(
    url: str,
    language: str | None,
    dest: Path,
    do_ingest: bool,
    db_path: Path | None,
) -> None:
    """Download a YouTube video/playlist/channel's subtitles via yt-dlp.

    Grabs the (auto-generated) subtitle track for --language as .vtt files
    — ready for `prelexy ingest`, or ingested right away with --ingest.
    """
    from prelexy.pods import INSTALL_HINT, fetch_subtitles

    config = _load_config_or_die()
    language = _resolve_language(language, config)
    new_files = fetch_subtitles(url, language, dest)
    if new_files is None:
        raise click.ClickException(INSTALL_HINT)
    click.echo(f"Fetched {len(new_files)} new subtitle file(s) into {dest}.")
    if do_ingest and new_files:
        _ingest_paths(new_files, language, config, db_path)


def _ingest_paths(
    files: Sequence[Path], language: str, config: Config, db_path: Path | None
) -> None:
    with Store(_resolve_db(db_path, config)) as store:
        for file in files:
            result = _ingest_file(store, file, language)
            if result is None:
                click.echo(f"  {file.name}: already ingested, skipped")
            else:
                candidates, n_occurrences = result
                click.echo(f"  {file.name}: {len(candidates)} items ({n_occurrences} occurrences)")


@cli.command("ingest-docs")
@click.argument("docs_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option(
    "--language", default="python", show_default=True, help="Code language namespace for the items."
)
@click.option(
    "--modules",
    default=None,
    help="Comma-separated module filter, e.g. 'itertools,functools' [default: the whole corpus]",
)
@_db_option
def ingest_docs(docs_dir: Path, language: str, modules: str | None, db_path: Path | None) -> None:
    """Ingest a downloaded Sphinx HTML documentation tree.

    Reads objects.inv at DOCS_DIR's root and stores every documented
    function/method/class as a learnable item, with the doc's first
    description sentence as its definition and its signature as the
    after-answer context. Whole corpus by default; --modules narrows
    for focused study (DECISIONS 024).
    """
    from prelexy.docsproc import extract_glosses, parse_inventory
    from prelexy.languages import get_language

    config = _load_config_or_die()
    if get_language(language).kind != "code":
        raise click.ClickException(
            f"{language!r} is not a code language — use `prelexy ingest` for texts."
        )
    inventory = docs_dir / "objects.inv"
    if not inventory.exists():
        raise click.ClickException(
            f"No objects.inv in {docs_dir} — point at the root of a Sphinx HTML "
            "docs download (e.g. the python-3.x-docs-html archive, unpacked)."
        )
    try:
        entries = parse_inventory(inventory)
    except ValueError as error:
        raise click.ClickException(str(error)) from error
    if modules:
        wanted = {m.strip() for m in modules.split(",") if m.strip()}
        entries = [
            e
            for e in entries
            if e.module in wanted or any(e.module.startswith(m + ".") for m in wanted)
        ]
    if not entries:
        raise click.ClickException("Nothing learnable matched in the inventory.")

    by_page: dict[str, list[DocEntry]] = {}
    for entry in entries:
        by_page.setdefault(entry.page, []).append(entry)

    path = str(docs_dir.resolve())
    stored = unglossed = missing_pages = 0
    with Store(_resolve_db(db_path, config)) as store:
        if store.find_source_by_path(path) is not None:
            raise click.ClickException(
                f"{docs_dir} was already ingested; re-ingesting would double its counts."
            )
        source_id = store.add_source(docs_dir.name, language, "docs", path)
        order = 0
        for page, page_entries in by_page.items():
            html_file = docs_dir / page
            if not html_file.is_file():
                missing_pages += 1
                continue
            glosses = extract_glosses(
                html_file.read_text(encoding="utf-8", errors="replace"),
                {e.anchor for e in page_entries},
            )
            for entry in page_entries:
                found = glosses.get(entry.anchor)
                if found is None:
                    unglossed += 1
                    continue
                signature, gloss = found
                item_id = store.get_or_create_item(
                    language,
                    entry.name,
                    lemma=entry.name,
                    pos=entry.role,
                    metadata={
                        "kind": entry.role,
                        "module": entry.module,
                        "signature": signature,
                        "order": order,
                    },
                )
                store.add_occurrences(item_id, source_id, [(signature or entry.name, order)])
                if not store.senses_for(item_id):
                    store.add_sense(item_id, gloss, "en", "docs")
                stored += 1
                order += 1
    click.echo(f"Stored {stored} documented objects from {len(by_page)} pages.")
    if unglossed or missing_pages:
        click.echo(
            f"(skipped: {unglossed} without extractable descriptions, "
            f"{missing_pages} missing pages)"
        )


@cli.group()
def pods() -> None:
    """Save podcast channels and sync their transcripts."""


@pods.command("add")
@click.argument("url")
@_language_option
@_db_option
def pods_add(url: str, language: str | None, db_path: Path | None) -> None:
    """Save a channel/playlist URL (e.g. youtube.com/@tweakers/podcasts)."""
    config = _load_config_or_die()
    language = _resolve_language(language, config)
    with Store(_resolve_db(db_path, config)) as store:
        subscriptions = store.get_meta("pod_subscriptions", [])
        if any(sub["url"] == url for sub in subscriptions):
            raise click.ClickException(f"{url} is already saved.")
        subscriptions.append({"url": url, "language": language})
        store.set_meta("pod_subscriptions", subscriptions)
    click.echo(
        f"Saved ({language}). {len(subscriptions)} pod(s) — "
        "`prelexy pods sync --ingest` fetches new episodes."
    )


@pods.command("list")
@_db_option
def pods_list(db_path: Path | None) -> None:
    """Show the saved pods."""
    config = _load_config_or_die()
    with Store(_resolve_db(db_path, config)) as store:
        subscriptions = store.get_meta("pod_subscriptions", [])
    if not subscriptions:
        click.echo("No pods saved yet — `prelexy pods add <channel-url>`.")
        return
    for sub in subscriptions:
        click.echo(f"  [{sub['language']}] {sub['url']}")


@pods.command("remove")
@click.argument("url")
@_db_option
def pods_remove(url: str, db_path: Path | None) -> None:
    """Forget a saved pod."""
    config = _load_config_or_die()
    with Store(_resolve_db(db_path, config)) as store:
        subscriptions = store.get_meta("pod_subscriptions", [])
        remaining = [sub for sub in subscriptions if sub["url"] != url]
        if len(remaining) == len(subscriptions):
            raise click.ClickException(f"{url} is not a saved pod.")
        store.set_meta("pod_subscriptions", remaining)
    click.echo(f"Removed. {len(remaining)} pod(s) left.")


@pods.command("sync")
@click.option(
    "--dest",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path("data/pods"),
    show_default=True,
)
@click.option(
    "--ingest", "do_ingest", is_flag=True, help="Ingest every new transcript immediately."
)
@_db_option
def pods_sync(dest: Path, do_ingest: bool, db_path: Path | None) -> None:
    """Fetch new episodes' subtitles from every saved pod.

    yt-dlp's download archive remembers what has already been fetched,
    so re-running only pulls what's new.
    """
    from prelexy.pods import INSTALL_HINT, fetch_subtitles

    config = _load_config_or_die()
    with Store(_resolve_db(db_path, config)) as store:
        subscriptions = store.get_meta("pod_subscriptions", [])
    if not subscriptions:
        raise click.ClickException("No pods saved — `prelexy pods add <channel-url>` first.")
    archive = Path(dest) / "archive.txt"
    total = 0
    for sub in subscriptions:
        click.echo(f"Syncing [{sub['language']}] {sub['url']}")
        new_files = fetch_subtitles(sub["url"], sub["language"], dest, archive=archive)
        if new_files is None:
            raise click.ClickException(INSTALL_HINT)
        total += len(new_files)
        if do_ingest and new_files:
            _ingest_paths(new_files, sub["language"], config, db_path)
    click.echo(f"Sync complete: {total} new subtitle file(s).")


@cli.command("import-glosses")
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@_language_option
@_db_option
def import_glosses(file: Path, language: str | None, db_path: Path | None) -> None:
    """Fill missing definitions from a kaikki.org Wiktionary extract.

    Download the language's JSONL from https://kaikki.org/dictionary/
    (e.g. Dutch), then run this after ingesting a transcript: items that
    got no definition from the offline chain are filled from the extract.
    """
    from prelexy.definitions import import_kaikki_glosses

    config = _load_config_or_die()
    language = _resolve_language(language, config)
    with Store(_resolve_db(db_path, config)) as store:
        filled, missing = import_kaikki_glosses(store, file, language)
    click.echo(f"{missing} item(s) had no definition; filled {filled} from {file.name}.")
    if filled:
        click.echo("(words previously set aside for lacking a definition return to play)")
    if missing > filled:
        click.echo(f"({missing - filled} remain unglossed — they will be set aside in play.)")


@cli.command()
@click.argument("word")
@_language_option
def say(word: str, language: str | None) -> None:
    """Pronounce a word aloud using the system speech engine."""
    from prelexy.speech import INSTALL_HINT, pronounce

    config = _load_config_or_die()
    language = _resolve_language(language, config)
    if not pronounce(word, language, voice=config["tts_voice"] or None):
        raise click.ClickException(INSTALL_HINT)


def definitions_language() -> str:
    from prelexy.definitions import STRONG_LANGUAGE

    return STRONG_LANGUAGE


def _load_config_or_die() -> Config:
    import tomllib

    from prelexy.config import config_path, load_config

    try:
        return load_config()
    except (OSError, ValueError, tomllib.TOMLDecodeError) as error:
        raise click.ClickException(f"Bad config file ({config_path()}): {error}") from error


def _choose_profile(store: Store) -> int:
    """Ask who is playing: pick an existing profile or create one."""
    profiles = store.list_profiles()
    if not profiles:
        name = click.prompt("No profiles yet — pick a name for yours", default="default")
        return store.get_or_create_profile(name.strip() or "default")
    click.echo("Who is playing?")
    for index, row in enumerate(profiles):
        click.echo(f"  {index + 1}. {row['name']}")
    click.echo("  n. new profile")
    while True:
        raw = click.prompt("Profile", type=str).strip()
        if raw.lower() == "n":
            name = click.prompt("Name for the new profile").strip()
            if name:
                return store.get_or_create_profile(name)
        elif raw.isdigit() and 1 <= int(raw) <= len(profiles):
            return int(profiles[int(raw) - 1]["id"])
        click.echo(f"  Pick 1–{len(profiles)}, or n for a new profile.")


@cli.command()
@click.argument("form")
@_language_option
@_db_option
def question(form: str, language: str | None, db_path: Path | None) -> None:
    """Preview a multiple-choice question for a stored word (* marks the answer).

    Debug view: unlike a play session, the context sentence and the answer
    are shown up front.
    """
    from prelexy.mcq import build_question
    from prelexy.similarity import SpacyVectors
    from prelexy.textproc import load_nlp

    config = _load_config_or_die()
    language = _resolve_language(language, config)
    with Store(_resolve_db(db_path, config)) as store:
        item = store.find_item(language, form)
        if item is None:
            raise click.ClickException(
                f"{form!r} is not stored — run `prelexy ingest` on a text containing it."
            )
        try:
            # glosses are strong-language text, so similarity always uses
            # the English vectors — even for Dutch sessions
            similarity = SpacyVectors(load_nlp(definitions_language()))
        except (OSError, ValueError):
            similarity = None  # no vectors: random same-POS fallback
        built = build_question(
            store,
            item,
            similarity=similarity,
            band=(config["similarity_floor"], config["similarity_ceiling"]),
            pool_size=config["pool_size"],
            code_own_pool=config["code_pool_own_language"],
        )
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
    default=None,
    help="Player profile; each profile tracks its own progress. Without this "
    "flag, the config file's default_profile applies, else play asks.",
)
@click.option(
    "--language",
    default=None,
    help="Language to practice [default: the profile's last language, "
    "else default_language from the config file]",
)
@click.option(
    "--new",
    "new_words",
    default=None,
    type=click.IntRange(min=0),
    help="New words this session [default: new_words from the config file]",
)
@click.option(
    "--seen",
    "seen_words",
    default=None,
    type=click.IntRange(min=0),
    help="Previously seen words (due reviews) this session "
    "[default: seen_words from the config file]",
)
@_db_option
def play(
    profile_name: str | None,
    language: str | None,
    new_words: int | None,
    seen_words: int | None,
    db_path: Path | None,
) -> None:
    """Start a practice session."""
    from prelexy.scheduler import SM2Scheduler
    from prelexy.session import run_session
    from prelexy.similarity import SpacyVectors
    from prelexy.textproc import load_nlp

    config = _load_config_or_die()
    new_words = new_words if new_words is not None else config["new_words"]
    seen_words = seen_words if seen_words is not None else config["seen_words"]
    profile_name = profile_name or config["default_profile"] or None

    try:
        # glosses are strong-language text, so similarity always uses the
        # English vectors — even for Dutch sessions
        similarity = SpacyVectors(load_nlp(definitions_language()))
    except (OSError, ValueError):
        similarity = None  # no vectors: distractor band is skipped
    with Store(_resolve_db(db_path, config)) as store:
        profile_id = (
            store.get_or_create_profile(profile_name) if profile_name else _choose_profile(store)
        )
        settings = store.get_profile_settings(profile_id)
        language = _validate_language(
            language or settings.get("language") or config["default_language"]
        )
        summary = run_session(
            store,
            profile_id,
            language,
            SM2Scheduler(new_words=new_words, seen_words=seen_words),
            similarity=similarity,
            n_questions=new_words + seen_words,
            band=(config["similarity_floor"], config["similarity_ceiling"]),
            pool_size=config["pool_size"],
            show_context=config["show_context"],
            tts_voice=config["tts_voice"] or None,
            code_own_pool=config["code_pool_own_language"],
        )
        # remember the language only when it actually had items — a session
        # that served nothing must not pin the profile to an empty language
        # (2026-07-07: a failed `play --language python` hid a synced Dutch
        # corpus behind an empty default profile). strong_language is stored
        # for future per-profile glossing (glosses currently always English).
        if summary.had_items:
            store.update_profile_settings(
                profile_id,
                language=language,
                strong_language=settings.get("strong_language", definitions_language()),
            )
