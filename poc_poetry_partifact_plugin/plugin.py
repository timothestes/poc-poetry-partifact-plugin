import os

from cleo.events.console_command_event import ConsoleCommandEvent
from cleo.events.console_events import COMMAND
from cleo.events.event_dispatcher import EventDispatcher
from cleo.io.outputs.output import Verbosity
from poetry.console.application import Application
from poetry.console.commands.add import AddCommand
from poetry.console.commands.install import InstallCommand
from poetry.console.commands.self.self_command import SelfCommand
from poetry.plugins.application_plugin import ApplicationPlugin
from tomlkit import parse as parse_toml
from tomlkit.exceptions import TOMLKitError

from poc_poetry_partifact_plugin.partifact.main import login

# planning to use partifact once issue is resolved https://github.com/Validus-Risk-Management/partifact/issues/2
# from partifact.main import login

CONFIG_PATH = "./pyproject.toml"


class PocPartifactPlugin(ApplicationPlugin):  # type: ignore
    def activate(self, application: Application) -> None:
        application.event_dispatcher.add_listener(COMMAND, self._handle_pre_command)

    def _handle_pre_command(
        self, event: ConsoleCommandEvent, event_name: str, dispatcher: EventDispatcher
    ) -> None:
        """Run partifact.login before any Install or Add Commands"""
        command = event.command
        io = event.io

        if isinstance(command, SelfCommand):
            io.write_line(
                "<info>Poetry pre-commit plugin does not run for 'self' command.</info>",
                verbosity=Verbosity.DEBUG,
            )
            return

        if not any(isinstance(command, t) for t in [InstallCommand, AddCommand]):
            # Only run the plugin for install and add commands
            return

        if not self._pyproject_toml_has_codeartifact():
            # only run aws login if codeartifact is found in pyproject.toml
            return

        # run a codeartifact login command
        try:
            # env variable needed to solve https://github.com/python-poetry/poetry/issues/2692
            os.environ["PYTHON_KEYRING_BACKEND"] = "keyring.backends.null.Keyring"
            login(repository=self._get_repository(), profile=self._get_repository(), role=None)
            io.write_line("<fg=green>aws codeartifact successfully configured</info>")
        except Exception as error:
            io.write_error_line(f"<error>Failed to configure aws codeartifact: \n{error}</>")
        finally:
            # not sure if having this set to something will cause problems down the line
            os.unsetenv("PYTHON_KEYRING_BACKEND")

    def _pyproject_toml_has_codeartifact(self) -> bool:
        """Determine if the pyproject.toml file has codeartifact in it."""

        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            toml_contents = f.read()

        parsed_toml = parse_toml(toml_contents)

        sources = parsed_toml.get("tool", {}).get("poetry", {}).get("source", [])

        for source in sources:
            if ".codeartifact." in source.get("url", ""):
                return True

        return False

    def _get_repository(self) -> str:
        """Get the repository name from a pyproject.toml file."""
        CONFIG_PATH = "./pyproject.toml"
        try:
            with open(CONFIG_PATH, "r") as f:
                config = parse_toml(f.read())
        except FileNotFoundError:
            raise RuntimeError("no pyproject.toml found")
        except TOMLKitError:
            raise RuntimeError("invalid pyproject.toml")

        repo_names = []
        sources = config["tool"]["poetry"]["source"]

        for source in sources:
            if source.get("name"):
                repo_names.append(source["name"])

        if not repo_names:
            raise RuntimeError("tool.poetry.source requires a 'name' field")

        return repo_names[0]
