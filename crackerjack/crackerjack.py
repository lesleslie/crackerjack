import sys
from subprocess import call

import pdm_bump
import pdoc
from acb.actions import dump
from acb.actions import load
from addict import Dict as adict
from aiopath import AsyncPath
from pydantic import BaseModel

for mod in (pdm_bump, pdoc):
    pass


# Crackerjack


class Crakerjack(BaseModel):
    path: AsyncPath = AsyncPath(".")
    pkg_path: AsyncPath = AsyncPath.cwd()
    pkg_name: str = "crackerjack"

    async def update_pkg_configs(self) -> None:
        for config in (".gitignore", ".pre-commit-config.yaml", ".libcst.codemod.yaml"):
            config_path = self.path / config
            config_pkg_path = self.pkg_path / config
            config_text = await config_path.read_text()
            await config_pkg_path.write_text(
                config_text.replace("crackerjack", self.pkg_name)
            )
        toml_file = "pyproject.toml"
        toml_path = self.path / toml_file
        pkg_toml_path = self.pkg_path / toml_file
        if not await pkg_toml_path.exists():
            call(["pdm", "init"])
        toml = await load.toml(toml_path)
        pkg_toml = await load.toml(pkg_toml_path)
        pkg_toml.tool = toml.tool
        pkg_toml.tool.pyanalyze.paths = [f"{self.pkg_name}/"]
        await dump.toml(pkg_toml, pkg_toml_path)

    async def process(
        self,
        options: adict[str, str | bool],
    ) -> None:
        imp_dir = self.pkg_path / "__pypackages__"
        sys.path.append(str(imp_dir))
        self.pkg_name = self.pkg_path.stem.lower()
        print("\nCrackerjacking...\n")
        await self.update_pkg_configs()
        try:
            call(["pre-commit", "run", "--all-files"])
        except Exception as err:
            raise err
        if options.publish:
            call(["pdm", "bump", options.publish])
            # call(["pdm", "publish"])


crackerjack_it = Crakerjack().process
