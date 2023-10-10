import asyncio
import sys
import typing as t
from subprocess import run

from acb.actions.encode import dump
from acb.actions.encode import load
from aioconsole import ainput
from aioconsole import aprint
from aiopath import AsyncPath
from inflection import underscore
from pydantic import BaseModel


class Commands(BaseModel):
    pre_commit: str = "/usr/local/bin/pre-commit"
    git: str = "/usr/bin/git"
    pdm: str = "/usr/local/bin/pdm"


commands = Commands()


class Crakerjack(BaseModel, arbitrary_types_allowed=True):
    our_path: AsyncPath = AsyncPath(__file__).parent
    pkg_path: AsyncPath = AsyncPath.cwd()
    pkg_dir: t.Optional[AsyncPath] = None
    pkg_name: str = "crackerjack"
    our_toml: t.Optional[dict[str, t.Any]] = None
    pkg_toml: t.Optional[dict[str, t.Any]] = None
    our_toml_path: t.Optional[AsyncPath] = None
    pkg_toml_path: t.Optional[AsyncPath] = None
    poetry_pip_env: bool = False

    async def update_pyproject_configs(self) -> None:
        toml_file = "pyproject.toml"
        self.our_toml_path = self.our_path / toml_file
        self.pkg_toml_path = self.pkg_path / toml_file
        if self.pkg_path.stem == "crackerjack":
            await self.our_toml_path.write_text(await self.pkg_toml_path.read_text())
            return
        our_toml_config: t.Any = await load.toml(self.our_toml_path)  # type: ignore
        pkg_toml_config: t.Any = await load.toml(self.pkg_toml_path)  # type: ignore
        pkg_deps = pkg_toml_config["tool"]["pdm"]["dev-dependencies"]
        pkg_toml_config["tool"] = our_toml_config["tool"]
        for settings in pkg_toml_config["tool"].values():
            for setting, value in settings.items():
                if isinstance(value, str | list) and "crackerjack" in value:
                    if isinstance(value, list):
                        value.remove("crackerjack")
                        value.append(self.pkg_name)
                    else:
                        value = value.replace("crackerjack", self.pkg_name)
                    settings[setting] = value
        pkg_toml_config["tool"]["pdm"]["dev-dependencies"] = pkg_deps
        await dump.toml(pkg_toml_config, self.pkg_toml_path)  # type: ignore

    async def copy_configs(self) -> None:
        config_files = (
            ".gitignore",
            ".pre-commit-config.yaml",
            ".libcst.codemod.yaml",
        )
        for config in config_files:
            config_path = self.our_path / config
            pkg_config_path = self.pkg_path / config
            await pkg_config_path.touch(exist_ok=True)
            if self.pkg_path.stem == "crackerjack":
                await config_path.write_text(await pkg_config_path.read_text())
                continue
            config_text = await config_path.read_text()
            await pkg_config_path.write_text(
                config_text.replace("crackerjack", self.pkg_name)
            )
            run([commands.git, "add", config])

    @staticmethod
    async def run_interactive(hook: str) -> None:
        success: bool = False
        while not success:
            fail = run([commands.pre_commit, "run", hook.lower(), "--all-files"])
            if fail.returncode > 0:
                retry = await ainput(f"\n\n{hook.title()} failed. Retry? (y/N): ")
                await aprint()
                if retry.strip().lower() == "y":
                    continue
                sys.exit()
            success = True

    async def update_pkg_configs(self) -> None:
        await self.copy_configs()
        installed_pkgs = run(
            [commands.pdm, "list", "--freeze"], capture_output=True, text=True
        ).stdout.splitlines()
        if not len([pkg for pkg in installed_pkgs if "pre-commit" in pkg]):
            run([commands.pdm, "self", "add", "keyring"])
            run([commands.pdm, "config", "python.use_venv", "false"])
            run([commands.git, "init"])
            run([commands.git, "branch", "-m", "main"])
            run([commands.git, "add", "pyproject.toml"])
            run([commands.pdm, "add", "-d", "pre_commit"])
            run([commands.pdm, "add", "-d", "pytest"])
            run([commands.pdm, "add", "-d", "autotyping"])
            run([commands.pre_commit, "install"])
            run([commands.git, "add", "pdm.lock"])
            run([commands.git, "config", "advice.addIgnoredFile", "false"])
        await self.update_pyproject_configs()

    async def process(self, options: t.Any) -> None:
        imp_dir = self.pkg_path / "__pypackages__"
        sys.path.append(str(imp_dir))
        self.pkg_name = underscore(self.pkg_path.stem.lower())
        self.pkg_dir = self.pkg_path / self.pkg_name
        await self.pkg_dir.mkdir(exist_ok=True)
        await aprint("\nCrackerjacking...\n")
        if self.pkg_path.stem == "crackerjack" and options.update_precommit:
            run([commands.pre_commit, "autoupdate"])
        await asyncio.create_subprocess_shell('eval "$(pdm --pep582)"')
        if not options.do_not_update_configs:
            await self.update_pkg_configs()
        if options.interactive:
            for hook in ("refurb", "bandit", "pyright"):
                await self.run_interactive(hook)
        check_all = run([commands.pre_commit, "run", "--all-files"])
        if check_all.returncode > 0:
            run([commands.pre_commit, "run", "--all-files"])
        if options.publish:
            run([commands.pdm, "bump", options.publish])
        if options.publish:
            run([commands.pdm, "publish"])
        if options.commit:
            commit_msg = await ainput("\nCommit message: ")
            run(
                [
                    commands.git,
                    "commit",
                    "-m",
                    f"{commit_msg}",
                    "--no-verify",
                    "--",
                    ".",
                ]
            )
            run([commands.git, "push", "origin", "main"])
        await aprint("\nCrackerjack complete!\n")


crackerjack_it = Crakerjack().process
