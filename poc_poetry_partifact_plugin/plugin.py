import os
import subprocess
from pathlib import Path
from typing import Optional

from cleo.events.console_command_event import ConsoleCommandEvent
from cleo.events.console_events import COMMAND, TERMINATE
from cleo.events.console_terminate_event import ConsoleTerminateEvent
from cleo.events.event_dispatcher import EventDispatcher
from cleo.io.io import IO
from cleo.io.outputs.output import Verbosity
from poetry.console.application import Application
from poetry.console.commands.add import AddCommand
from poetry.console.commands.install import InstallCommand
from poetry.console.commands.self.self_command import SelfCommand
from poetry.plugins.application_plugin import ApplicationPlugin
from tomlkit import parse as parse_toml

from poc_poetry_partifact_plugin.partifact.main import login

CONFIG_PATH = "./pyproject.toml"


class PocPartifactPlugin(ApplicationPlugin):  # type: ignore
    def activate(self, application: Application) -> None:
        application.event_dispatcher.add_listener(TERMINATE, self._handle_post_command)
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
            login(repository="aws", profile="amino-shared", role=None)
            io.write_line("<fg=green>aws codeartifact successfully configured</info>")
        except Exception as error:
            io.write_error_line(f"<error>Failed to configure aws codeartifact: \n{error}</>")
        finally:
            os.unsetenv("PYTHON_KEYRING_BACKEND")

    def _handle_post_command(
        self, event: ConsoleTerminateEvent, event_name: str, dispatcher: EventDispatcher
    ) -> None:
        if event.exit_code != 0:
            # The command failed, so the plugin shouldn't do anything
            # if the event was a "HTTPSConnectionPool" error, then try to login
            return

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

        if not self._is_pre_commit_package_installed():
            return

        if self._get_git_directory_path() is None:
            # Not in a git repository - can't install hooks
            return

        if self._are_pre_commit_hooks_installed():
            # pre-commit hooks already installed - nothing to do
            return

        if command.option("dry-run") is True:
            return

        self._install_pre_commit_hooks(io)

    def _install_pre_commit_hooks(self, io: IO) -> None:
        try:
            io.write_line("<info>Installing pre-commit hooks...</>")
            return_code = subprocess.check_call(
                ["poetry", "run", "pre-commit", "install"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if return_code == 0:
                io.write_line("<fg=green>pre-commit hooks successfully installed</info>")
            else:
                io.write_error_line("<error>Failed to install pre-commit hooks</>")
        except Exception as e:
            io.write_error_line(
                "<error>Failed to install pre-commit hooks due to an unexpected error</>"
            )
            io.write_error_line(f"<error>{e}</>")

    def _is_pre_commit_package_installed(self) -> bool:
        try:
            output = subprocess.check_output(
                ["poetry", "run", "pip", "freeze", "--local"],
            ).decode()
            return "pre-commit" in output
        except FileNotFoundError:
            return False

    def _are_pre_commit_hooks_installed(self) -> bool:
        git_root = self._get_git_directory_path()
        if git_root is None:
            return False
        return (git_root / "hooks" / "pre-commit").exists()

    def _get_git_directory_path(self) -> Optional[Path]:
        try:
            result = subprocess.check_output(
                ["git", "rev-parse", "--show-toplevel"],
            )
            return Path(result.decode().strip()) / ".git"
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    def _pyproject_toml_has_codeartifact(self) -> bool:
        """Determine if the pyproject.toml file has codeartifact in it."""

        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            toml_contents = f.read()

        parsed_toml = parse_toml(toml_contents)

        sources = parsed_toml.get("tool", {}).get("poetry", {}).get("source", [])

        for source in sources:
            if source.get("url", "").contains(".codeartifact."):
                return True

        return False
