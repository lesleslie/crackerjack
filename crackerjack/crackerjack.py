import sys
from subprocess import call
from subprocess import check_output
from subprocess import run

import pdm_bump
import pdoc
from acb.actions import dump
from acb.actions import load
from addict import Dict as adict
from aiopath import AsyncPath
from pydantic import BaseModel
from aioconsole import ainput

for mod in (pdm_bump, pdoc):
    pass


# Crackerjack


class Crakerjack(BaseModel):
    path: AsyncPath = AsyncPath(__file__)
    pkg_path: AsyncPath = AsyncPath.cwd()
    pkg_name: str = "crackerjack"
    poetry_pip_env: bool = False

    class Config:
        extra = "allow"

    async def clean_poetry_pip_env(self) -> None:
        root_files = [
            file
            async for file in self.pkg_path.iterdir()
            if ("poetry" or "Pip") in file.name
        ]
        if root_files:
            self.poetry_pip_env = True
            for file in root_files:
                await file.unlink()

    async def update_pyproject_configs(self) -> None:
        toml = await load.toml(self.toml_path)
        pkg_toml = await load.toml(self.pkg_toml_path)
        if self.poetry_pip_env:
            del pkg_toml.tool.poetry
        pkg_toml.tool = toml.tool
        await dump.toml(pkg_toml, self.pkg_toml_path)

    async def copy_configs(self) -> None:
        for config in (
            ".gitignore",
            ".pre-commit-config.yaml",
            ".libcst.codemod.yaml",
            "pyproject.toml",
        ):
            config_path = self.path.parent / config
            pkg_config_path = self.pkg_path / config
            await pkg_config_path.touch(exist_ok=True)
            check_output(["git", "add", str(pkg_config_path)])
            if self.pkg_path.stem == "crackerjack":
                await config_path.write_text(await pkg_config_path.read_text())
            elif config != "pyproject.toml":
                # if poetry_pip_env:
                #     await config_pkg_path.unlink()
                config_text = await config_path.read_text()
                await pkg_config_path.write_text(
                    config_text.replace("crackerjack", self.pkg_name)
                )

    async def update_pkg_configs(self) -> None:
        # await self.clean_poetry_pip_env()
        await self.copy_configs()
        toml_file = "pyproject.toml"
        self.toml_path = self.path.parent / toml_file
        self.pkg_toml_path = self.pkg_path / toml_file
        if not await self.pkg_toml_path.exists():
            check_output(["pdm", "init"])
        installed_pkgs = check_output(
            ["pdm", "list", "--freeze"],
            universal_newlines=True,
        ).splitlines()
        if not len([pkg for pkg in installed_pkgs if "pre-commit" in pkg]):
            check_output(["pdm", "add", "-d", "pre_commit"])
            check_output(["pre-commit", "install"])
        await self.update_pyproject_configs()

    async def process(
        self,
        options: adict[str, str | bool],
    ) -> None:
        imp_dir = self.pkg_path / "__pypackages__"
        sys.path.append(str(imp_dir))
        self.pkg_name = self.pkg_path.stem.lower()
        print("\nCrackerjacking...\n")
        if self.pkg_path.stem == "crackerjack":
            check_output(["pre-commit", "autoupdate"])
        await self.update_pkg_configs()
        if options.interactive:
            success = False
            while not success:
                fail = call(["pre-commit", "run", "mypy", "--all-files"])
                if fail > 0:
                    retry = await ainput("\nMyPy failed. Retry? (y/n): ")
                    if retry.lower == ("y"):
                        continue
                    sys.exit()
                success = True
        check_all = call(["pre-commit", "run", "--all-files"])
        if check_all > 0:
            call(["pre-commit", "run", "--all-files"])
        if options.publish:
            check_output(["pdm", "bump", options.publish])
            if options.commit:
                commit_msg = input("Commit message: ")
                call(["git", "commit", "-m", f"'{commit_msg}'", "--", "."])
                call(["git", "push", "origin", "main"])
            run(["pdm", "publish"])


crackerjack_it = Crakerjack().process
