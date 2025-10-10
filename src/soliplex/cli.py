import enum
import os
import pathlib
import typing
from importlib.metadata import version

import typer
import uvicorn
from rich import console

import soliplex
from soliplex import config
from soliplex import installation
from soliplex import main
from soliplex import models
from soliplex import secrets


class ReloadOption(str, enum.Enum):
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


installation_path_type = typing.Annotated[
    pathlib.Path,
    typer.Argument(
        envvar="SOLIPLEX_INSTALLATION_PATH",
        help="Soliplex instllation path",
    ),
]


def get_installation(
    installation_path: pathlib.Path,
) -> installation.Installation:
    i_config = config.load_installation(installation_path)
    i_config.reload_configurations()
    return installation.Installation(i_config)


@the_cli.callback()
def app(
    _version: bool = typer.Option(
        False,
        "-v",
        "--version",
        callback=version_callback,
        help="Show version and exit",
    ),
):
    """soliplex CLI - RAG system"""


reload_option: ReloadOption = typer.Option(
    None,
    "-r",
    "--reload",
    help="Reload on file changes",
)


@the_cli.command(
    "serve",
)
def serve(
    ctx: typer.Context,
    installation_path: installation_path_type,
    port: int = typer.Option(
        8000,
        "-p",
        "--port",
        help="Port number",
    ),
    reload: ReloadOption = reload_option,
):
    """Run the Soliplex server"""
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
    installation_path: installation_path_type,
):
    """Check that secrets / env vars can be resolved"""
    the_installation = get_installation(installation_path)

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

    # Check that conversion to models doesn't raise
    models.Installation.from_config(the_installation._config)
    the_console.print("Installation model: OK")
    for room_config in the_installation.get_room_configs(None).values():
        models.Room.from_config(room_config)
    the_console.print("Room models: OK")
    for compl_config in the_installation.get_completion_configs(None).values():
        models.Completion.from_config(compl_config)
    the_console.print("Completion models: OK")


@the_cli.command(
    "list_secrets",
)
def list_secrets(
    ctx: typer.Context,
    installation_path: installation_path_type,
):
    """List secrets defined in the installation"""
    the_installation = get_installation(installation_path)
    the_console.print("==================")
    the_console.print("Configured secrets")
    the_console.print("==================")
    for secret_config in the_installation._config.secrets:
        the_console.print(f"- {secret_config.secret_name}")

    the_console.print()


@the_cli.command(
    "list_environment",
)
def list_environment(
    ctx: typer.Context,
    installation_path: installation_path_type,
):
    """List environment variables defined in the installation"""
    the_installation = get_installation(installation_path)
    the_console.print("================================")
    the_console.print("Configured environment variables")
    the_console.print("================================")
    for key, value in the_installation._config.environment.items():
        the_console.print(f"- {key}: {value}")

    the_console.print()


@the_cli.command(
    "list_oidc_auth_providers",
)
def list_oidc_auth_providers(
    ctx: typer.Context,
    installation_path: installation_path_type,
):
    """List OIDC Auth Providers defined in the installation"""
    the_installation = get_installation(installation_path)

    the_console.print("==============================")
    the_console.print("Configured OIDC Auth Providers")
    the_console.print("==============================")

    for oidc_config in the_installation.oidc_auth_system_configs:
        the_console.print()
        the_console.print(f"- [ {oidc_config.id} ] {oidc_config.title}: ")
        the_console.print(f"  {oidc_config.server_url}")

    the_console.print()


@the_cli.command(
    "list_rooms",
)
def list_rooms(
    ctx: typer.Context,
    installation_path: installation_path_type,
):
    """List rooms defined in the installation"""
    the_installation = get_installation(installation_path)

    the_console.print("================")
    the_console.print("Configured Rooms")
    the_console.print("================")

    for room_config in the_installation.get_room_configs(None).values():
        the_console.print()
        the_console.print(f"- [ {room_config.id} ] {room_config.name}: ")
        the_console.print(f"  {room_config.description}")

    the_console.print()


@the_cli.command(
    "list_completions",
)
def list_completions(
    ctx: typer.Context,
    installation_path: installation_path_type,
):
    """List completions defined in the installation"""
    the_installation = get_installation(installation_path)

    the_console.print("======================")
    the_console.print("Configured Completions")
    the_console.print("======================")

    for compl_config in the_installation.get_completion_configs(None).values():
        the_console.print()
        the_console.print(f"- [ {compl_config.id} ] {compl_config.name}: ")

    the_console.print()


if __name__ == "__main__":
    the_cli()
