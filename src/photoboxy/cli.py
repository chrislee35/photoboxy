import typer

from .photoboxy import generate_album

app = typer.Typer()
app.command()(generate_album)

if __name__ == "__main__":
    app()