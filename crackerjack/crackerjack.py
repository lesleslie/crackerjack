import asyncio
import re
import sys
import typing as t
from pathlib import Path
from subprocess import run as execute

from acb.actions.encode import dump, load
from aioconsole import ainput, aprint
from aiopath import AsyncPath
from inflection import underscore
from pydantic import BaseModel


class Config(BaseModel):
    python_version: str = "3.13"


class Crackerjack(BaseModel, arbitrary_types_allowed=True):
    our_path: AsyncPath = AsyncPath(__file__).parent
    pkg_path: AsyncPath = AsyncPath(Path.cwd())
    settings_path: AsyncPath = pkg_path / ".crackerjack.yaml"
    pkg_dir: t.Optional[AsyncPath] = None
    pkg_name: str = "crackerjack"
    our_toml: t.Optional[dict[str, t.Any]] = None
    pkg_toml: t.Optional[dict[str, t.Any]] = None
    our_toml_path: t.Optional[AsyncPath] = None
    pkg_toml_path: t.Optional[AsyncPath] = None
    config: t.Optional[Config] = None

    async def update_pyproject_configs(self) -> None:
        toml_file = "pyproject.toml"
        self.our_toml_path = self.our_path / toml_file
        self.pkg_toml_path = self.pkg_path / toml_file
        if self.pkg_path.stem == "crackerjack":
            await self.our_toml_path.write_text(await self.pkg_toml_path.read_text())
            return
        our_toml_config: t.Any = await load.toml(self.our_toml_path)  # type: ignore
        pkg_toml_config: t.Any = await load.toml(self.pkg_toml_path)  # type: ignore
        pkg_deps = pkg_toml_config["dependency-groups"]
        for tool, settings in our_toml_config["tool"].items():
            for setting, value in settings.items():
                if isinstance(value, str | list) and "crackerjack" in value:
                    if isinstance(value, list):
                        value.remove("crackerjack")
                        value.append(self.pkg_name)
                    else:
                        value = value.replace("crackerjack", self.pkg_name)
                    settings[setting] = value
                if setting in (
                    "exclude-deps",
                    "exclude",
                    "excluded",
                    "skips",
                    "ignore",
                ) and isinstance(value, list):
                    settings[setting] = set(
                        pkg_toml_config["tool"][tool][setting] + value
                    )
            pkg_toml_config["tool"][tool] = settings
        pkg_toml_config["dependency-groups"] = pkg_deps
        python_version_pattern = r"\s*W*(\d\.\d*)"
        requires_python = our_toml_config["project"]["requires-python"]
        classifiers = []
        for classifier in pkg_toml_config["project"]["classifiers"]:
            classifier = re.sub(
                python_version_pattern, f" {self.config.python_version}", classifier
            )
            classifiers.append(classifier)
        pkg_toml_config["project"]["classifiers"] = classifiers
        pkg_toml_config["project"]["requires-python"] = requires_python
        await dump.toml(pkg_toml_config, self.pkg_toml_path)  # type: ignore

    async def copy_configs(self) -> None:
        config_files = (".gitignore", ".pre-commit-config.yaml", ".libcst.codemod.yaml")
        for config in config_files:
            config_path = self.our_path / config
            pkg_config_path = self.pkg_path / config
            await pkg_config_path.touch(exist_ok=True)
            if self.pkg_path.stem == "crackerjack":
                await config_path.write_text(await pkg_config_path.read_text())
                continue
            if config != ".gitignore":
                await pkg_config_path.write_text(
                    (await config_path.read_text()).replace(
                        "crackerjack", self.pkg_name
                    )
                )
            execute(["git", "add", config])

    async def run_interactive(self, hook: str) -> None:
        success: bool = False
        while not success:
            fail = execute(["pre-commit", "run", hook.lower(), "--all-files"])
            if fail.returncode > 0:
                retry = await ainput(f"\n\n{hook.title()} failed. Retry? (y/N): ")
                await aprint()
                if retry.strip().lower() == "y":
                    continue
                sys.exit()
            success = True

    async def update_pkg_configs(self) -> None:
        await self.copy_configs()
        installed_pkgs = execute(
            ["pdm", "list", "--freeze"],
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        if not len([pkg for pkg in installed_pkgs if "pre-commit" in pkg]):
            print("Initializing project...")
            execute(["pdm", "self", "add", "keyring"])
            execute(["pdm", "config", "python.use_uv", "true"])
            execute(["git", "init"])
            execute(["git", "branch", "-m", "main"])
            execute(["git", "add", "pyproject.toml"])
            execute(["git", "add", "pdm.lock"])
            execute(["pre-commit", "install"])
            execute(["git", "config", "advice.addIgnoredFile", "false"])
        await self.update_pyproject_configs()

    async def load_config(self) -> None:
        await self.settings_path.touch(exist_ok=True)
        try:
            self.config = Config(**await load.yaml(self.settings_path))
        except TypeError:
            self.config = Config()
            await dump.yaml(self.config.model_dump(), self.settings_path)
            raise SystemExit("\nPlease configure '.crackerjack.yaml' and try again\n")

    async def run_pre_commit(self) -> None:
        check_all = execute(["pre-commit", "run", "--all-files"])
        if check_all.returncode > 0:
            check_all = execute(["pre-commit", "run", "--all-files"])
            if check_all.returncode > 0:
                await aprint("\n\nPre-commit failed. Please fix errors.\n")
                raise SystemExit()

    async def process(self, options: t.Any) -> None:
        self.pkg_name = underscore(self.pkg_path.stem.lower())
        self.pkg_dir = self.pkg_path / self.pkg_name
        await self.pkg_dir.mkdir(exist_ok=True)
        await aprint("\nCrackerjacking...\n")
        if not options.do_not_update_configs:
            await self.update_pkg_configs()
            execute(["pdm", "install"])
        if self.pkg_path.stem == "crackerjack" and options.update_precommit:
            execute(["pre-commit", "autoupdate"])
        if options.interactive:
            for hook in ("refurb", "bandit", "pyright"):
                await self.run_interactive(hook)
        await self.run_pre_commit()
        for option in (options.publish, options.bump):
            if option:
                execute(["pdm", "bump", option])
                break
        if options.publish:
            build = execute(["pdm", "build"], capture_output=True, text=True)
            await aprint(build.stdout)
            if build.returncode > 0:
                await aprint(build.stderr)
                await aprint("\n\nBuild failed. Please fix errors.\n")
                raise SystemExit()
            execute(["pdm", "publish", "--no-build"])
        if options.commit:
            commit_msg = await ainput("\nCommit message: ")
            execute(
                [
                    "git",
                    "commit",
                    "-m",
                    str(commit_msg),
                    "--no-verify",
                    "--",
                    ".",
                ]
            )
            execute(["git", "push", "origin", "main"])
        await aprint("\nCrackerjack complete!\n")

    async def run(self, options: t.Any) -> None:
        await self.load_config()
        process = asyncio.create_task(self.process(options))
        await process


crackerjack_it = Crackerjack().run
