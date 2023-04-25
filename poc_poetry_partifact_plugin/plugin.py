import os

from cleo.events.console_command_event import ConsoleCommandEvent
from cleo.events.console_events import COMMAND
from cleo.events.event_dispatcher import EventDispatcher
from cleo.io.io import IO
from partifact.auth_token import get_token
from partifact.config import Configuration
from poetry.console.application import Application
from poetry.console.commands.add import AddCommand
from poetry.console.commands.install import InstallCommand
from poetry.plugins.application_plugin import ApplicationPlugin
from tomlkit import parse as parse_toml
from tomlkit.exceptions import TOMLKitError

CONFIG_PATH = "./pyproject.toml"


class PocPartifactPlugin(ApplicationPlugin):  # type: ignore
    name = "PocPartifactPlugin plugin"

    def activate(self, application: Application) -> None:
        application.event_dispatcher.add_listener(COMMAND, self._handle_pre_command)

    def _handle_pre_command(
        self, event: ConsoleCommandEvent, event_name: str, dispatcher: EventDispatcher
    ) -> None:
        """Run partifact.login before any Install or Add Commands"""
        command = event.command
        cleo_io = event.io

        if not any(isinstance(command, t) for t in [InstallCommand, AddCommand]):
            # Only run the plugin for install and add commands
            return

        try:
            parsed_toml = self._read_pyproject_file(file_path=CONFIG_PATH)
        except Exception as error:
            cleo_io.write_error_line(
                f"<error>{self.name} failed to read {CONFIG_PATH} pyproject file: \n{error}</>"
            )
            return

        if not self._pyproject_toml_has_codeartifact(parsed_toml=parsed_toml):
            # only run aws login if codeartifact is found in pyproject.toml
            return

        # run aws auth
        self._run_codeartifact_login(cleo_io=cleo_io, parsed_toml=parsed_toml)

    def _get_sources(self, parsed_toml: dict) -> list:
        """Return a list of all tool.poetry.source's in the parsed toml."""
        return parsed_toml.get("tool", {}).get("poetry", {}).get("source", [])

    def _read_pyproject_file(self, file_path: str) -> dict:
        """Read the pyproject.toml file contents and return the parsed contents."""
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                return parse_toml(file.read())
        except FileNotFoundError as error:
            raise RuntimeError(f"No pyproject.toml found at {file_path}") from error
        except TOMLKitError as error:
            raise RuntimeError("Invalid pyproject.toml") from error

    def _pyproject_toml_has_codeartifact(self, parsed_toml: dict) -> bool:
        """Determine if the pyproject.toml file has a codeartifact repository in it."""
        sources = self._get_sources(parsed_toml=parsed_toml)

        for source in sources:
            if ".codeartifact." in source.get("url", ""):
                return True

        return False

    def _get_repository(self, parsed_toml: dict) -> str:
        """Get the first repository name from a pyproject.toml file."""
        repo_names = []
        # if we are getting this far, we can assume at least one source exists...
        sources = self._get_sources(parsed_toml=parsed_toml)
        for source in sources:
            if source.get("name"):
                repo_names.append(source["name"])

        if not repo_names:
            raise RuntimeError("tool.poetry.source requires a 'name' field")

        return repo_names[0]

    def _run_codeartifact_login(self, cleo_io: IO, parsed_toml: dict) -> None:
        """Try to Run partifact.login command."""
        try:
            # env variable needed to solve https://github.com/python-poetry/poetry/issues/2692
            # os.environ["PYTHON_KEYRING_BACKEND"] = "keyring.backends.null.Keyring"
            repository = self._get_repository(parsed_toml)
            config = Configuration.load(repository, profile=repository, role=None)
            os.environ[f"POETRY_HTTP_BASIC_{repository}_PASSWORD"] = get_token(config)
            os.environ[f"POETRY_HTTP_BASIC_{repository}_USERNAME"] = "aws"
            cleo_io.write_line(
                f"<fg=green>{self.name} successfully configured AWS CodeArtifact for {repository}</info>"
            )
        except Exception as error:
            cleo_io.write_error_line(
                f"<error>{self.name} failed to configure AWS CodeArtifact for: \n{error}</>"
            )
        finally:
            pass
            # not sure if having this set to something will cause problems down the line
            # so unsetting it for now...
            # os.unsetenv("PYTHON_KEYRING_BACKEND")
