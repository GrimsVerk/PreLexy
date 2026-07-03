import click


@click.group()
def cli():
    """PreLexy — learn the vocabulary of the texts you actually read."""


@cli.command()
def play():
    """Start a practice session."""
    click.echo("PreLexy is under construction — nothing to play yet.")
    click.echo("See ROADMAP.md for what's coming.")
