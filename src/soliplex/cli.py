import enum
import os
import pathlib
from importlib.metadata import version

import typer
import uvicorn
from rich import console

import soliplex
from soliplex import config
from soliplex import installation
from soliplex import main
from soliplex import secrets


class ReloadOption(enum.StrEnum):
    CONFIG = "config"
    PYTHON = "python"
    BOTH = "both"


the_cli = typer.Typer(
    context_settings={
        "help_option_names": ["-h", "--help"],
    },
    no_args_is_help=True,
)

the_console = console.Console()


def version_callback(value: bool):
    if value:
        v = version("soliplex")
        the_console.print(f"soliplex version {v}")
        raise typer.Exit()


def get_installation_path(ctx: typer.Context) -> pathlib.Path:
    while ctx is not None:
        i_path = ctx.params.get("installation_path")

        if i_path is not None:
            return pathlib.Path(i_path).resolve()

        ctx = ctx.parent

    i_path = os.getenv("SOLIPLEX_INSTALLATION_PATH")
    if i_path is not None:
        return pathlib.Path(i_path).resolve()

    the_console.print("Installation path not found.")
    raise typer.Exit(code=1)


def get_installation(ctx: typer.Context) -> installation.Installation:
    installation_path = get_installation_path(ctx)
    i_config = config.load_installation(installation_path)
    i_config.reload_configurations()
    return installation.Installation(i_config)


installation_path_option: pathlib.Path | None = typer.Option(
    None,
    "-c",
    "--installation-path",
    help="Soliplex instllation path",
)


@the_cli.callback()
def app(
    _version: bool = typer.Option(
        False,
        "-v",
        "--version",
        callback=version_callback,
        help="Show version and exit",
    ),
    installation_path=installation_path_option,
):
    """soliplex CLI - RAG system"""


reload_option: ReloadOption = typer.Option(
    None,
    "-r",
    "--reload",
    help="Reload on changes to config, Python, or both",
)


@the_cli.command(
    "serve",
)
def serve(
    ctx: typer.Context,
    port: int = typer.Option(
        8000,
        "-p",
        "--port",
        help="Port number",
    ),
    reload=reload_option,
):
    """Run the Soliplex server"""
    installation_path = get_installation_path(ctx)

    reload_dirs = []
    reload_includes = []

    if reload in (ReloadOption.PYTHON, ReloadOption.BOTH):
        reload_dirs.extend(soliplex.__path__)
        reload_includes.append("*.yaml")

    if reload in (ReloadOption.CONFIG, ReloadOption.BOTH):
        reload_dirs.append(str(installation_path))
        reload_includes.append("*.yaml")
        reload_includes.append("*.yml")
        reload_includes.append("*.txt")

    if reload:
        os.environ["SOLIPLEX_INSTALLATION_PATH"] = str(installation_path)
        uvicorn.run(
            "soliplex.main:create_app",
            port=port,
            reload=reload,
            reload_dirs=reload_dirs,
            reload_includes=reload_includes,
        )
    else:
        app = main.create_app(installation_path)
        uvicorn.run(
            app,
            port=port,
        )


@the_cli.command(
    "check_config",
)
def check_config(
    ctx: typer.Context,
):
    """Check that secrets / env vars can be resolved"""
    the_installation = get_installation(ctx)

    try:
        the_installation.resolve_secrets()
    except secrets.SecretsNotFound as exc:
        the_console.print("===============")
        the_console.print("Missing secrets")
        the_console.print("===============")
        for secret_name in exc.secret_names.split(","):
            the_console.print(f"- {secret_name}")
    else:
        the_console.print("Secrets: OK")

    try:
        the_installation.resolve_environment()
    except config.MissingEnvVars as exc:
        the_console.print("=============================")
        the_console.print("Missing environment variables")
        the_console.print("=============================")
        for env_var in exc.env_vars.split(","):
            the_console.print(f"- {env_var}")
    else:
        the_console.print("Environment variables: OK")


@the_cli.command(
    "list_secrets",
)
def list_secrets(
    ctx: typer.Context,
):
    """List secrets defined in the installation"""
    the_installation = get_installation(ctx)
    the_console.print("==================")
    the_console.print("Configured secrets")
    the_console.print("==================")
    for secret_config in the_installation._config.secrets:
        print(f"- {secret_config.secret_name}")


@the_cli.command(
    "list_environment",
)
def list_environment(
    ctx: typer.Context,
):
    """List environment variables defined in the installation"""
    the_installation = get_installation(ctx)
    the_console.print("================================")
    the_console.print("Configured environment variables")
    the_console.print("================================")
    for key, value in the_installation._config.environment.items():
        print(f"- {key}: {value}")


if __name__ == "__main__":
    the_cli()
