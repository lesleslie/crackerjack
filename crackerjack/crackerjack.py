import sys
import typing as t
from subprocess import call
from subprocess import check_output
from subprocess import run

from acb.actions import dump
from acb.actions import load

import pdm_bump
import pdoc

from aioconsole import ainput
from aiopath import AsyncPath
from pydantic import BaseModel
from pydantic import ConfigDict

for mod in (pdm_bump, pdoc):  # look ruff / isort to get rid of this
    pass


# Crackerjack


class Crakerjack(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    our_path: AsyncPath = AsyncPath(__file__)
    pkg_path: AsyncPath = AsyncPath.cwd()
    pkg_dir: t.Optional[AsyncPath] = None
    pkg_name: str = "crackerjack"
    our_toml: t.Optional[dict] = None
    pkg_toml: t.Optional[dict] = None
    our_toml_path: t.Optional[AsyncPath] = None
    pkg_toml_path: t.Optional[AsyncPath] = None
    poetry_pip_env: bool = False

    async def update_pyproject_configs(self) -> None:
        toml_file = "pyproject.toml"
        self.our_toml_path = self.our_path.parent / toml_file
        self.pkg_toml_path = self.pkg_path / toml_file
        our_toml_config = await load.toml(self.our_toml_path)  # type: ignore
        pkg_toml_config = await load.toml(self.pkg_toml_path)  # type: ignore
        if self.poetry_pip_env:
            del pkg_toml_config["tool"]["poetry"]
        pkg_deps = pkg_toml_config["tool"]["pdm"]["dev-dependencies"]
        pkg_toml_config.setdefault("tool", our_toml_config.get("tool", {}))
        pkg_toml_config["tool"]["pdm"]["dev-dependencies"] = pkg_deps
        if self.pkg_path.stem == "crackerjack":
            await dump.toml(pkg_toml_config, self.our_toml_path)  # type: ignore
        else:
            await dump.toml(pkg_toml_config, self.pkg_toml_path)  # type: ignore

    async def clean_poetry_pipenv(self) -> None:
        root_files = [
            file
            async for file in self.pkg_path.iterdir()
            if ("poetry" or "Pip") in file.name
        ]
        if root_files:
            self.poetry_pip_env = True
            for file in root_files:
                await file.unlink()

    async def copy_configs(self) -> None:
        for config in (
            ".gitignore",
            ".pre-commit-config.yaml",
            ".libcst.codemod.yaml",
            ".crackerjack-config.yaml",
        ):
            config_path = self.our_path.parent / config
            pkg_config_path = self.pkg_path / config
            await pkg_config_path.touch(exist_ok=True)
            if self.pkg_path.stem == "crackerjack":
                await config_path.write_text(await pkg_config_path.read_text())
            # if poetry_pip_env:
            #     await config_pkg_path.unlink()
            config_text = await config_path.read_text()
            await pkg_config_path.write_text(
                config_text.replace("crackerjack", self.pkg_name)
            )
            run(["git", "add", config])

    @staticmethod
    async def run_interactive(hook: str) -> None:
        success = False
        while not success:
            fail = call(["pre-commit", "run", hook.lower(), "--all-files"])
            if fail > 0:
                retry = await ainput(f"\n{hook} failed. Retry? (y/n): ")
                if retry.lower() == "y":
                    continue
                sys.exit()
            success = True

    async def update_pkg_configs(self) -> None:
        await self.clean_poetry_pipenv()
        await self.copy_configs()
        installed_pkgs = check_output(
            ["pdm", "list", "--freeze"],
            universal_newlines=True,
        ).splitlines()
        if not len([pkg for pkg in installed_pkgs if "pre-commit" in pkg]):
            run(["pdm", "--pep582"])
            run(["pdm", "self", "add", "keyring"])
            run(["git", "init"])
            run(["git", "branch", "-m", "main"])
            run(["git", "add", "pyproject.toml"])
            run(["pdm", "add", "-d", "pre_commit"])
            run(["pre-commit", "install"])
            run(["git", "add", "pdm.lock"])
        await self.update_pyproject_configs()

    async def process(self, options: t.Any) -> None:
        imp_dir = self.pkg_path / "__pypackages__"
        sys.path.append(str(imp_dir))
        self.pkg_name = self.pkg_path.stem.lower()
        # self.pkg_name = underscore(self.pkg_path.stem.lower())
        self.pkg_dir = self.pkg_path / self.pkg_name
        await self.pkg_dir.mkdir(exist_ok=True)
        print("\nCrackerjacking...\n")
        if self.pkg_path.stem == "crackerjack" and options.update_precommit:
            run(["pre-commit", "autoupdate"])
        if options.publish:
            check_output(["pdm", "bump", options.publish])
        if not options.do_not_update_configs:
            await self.update_pkg_configs()
        if options.interactive:
            for hook in ("refurb", "pyright"):
                await self.run_interactive(hook)
        check_all = call(["pre-commit", "run", "--all-files"])
        if check_all > 0:
            call(["pre-commit", "run", "--all-files"])
        if options.publish:
            run(["pdm", "publish"])
        if options.commit:
            commit_msg = input("Commit message: ")
            call(["git", "commit", "-m", f"'{commit_msg}'", "--", "."])
            call(["git", "push", "origin", "main"])


crackerjack_it = Crakerjack().process
