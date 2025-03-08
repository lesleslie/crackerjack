import re
import typing as t
from pathlib import Path
from subprocess import run as execute
from tomllib import loads

from pydantic import BaseModel
from tomli_w import dumps


class Crackerjack(BaseModel, arbitrary_types_allowed=True):
    our_path: Path = Path(__file__).parent
    pkg_path: Path = Path(Path.cwd())
    pkg_dir: t.Optional[Path] = None
    pkg_name: str = "crackerjack"
    our_toml: t.Optional[dict[str, t.Any]] = None
    pkg_toml: t.Optional[dict[str, t.Any]] = None
    our_toml_path: t.Optional[Path] = None
    pkg_toml_path: t.Optional[Path] = None
    python_version: str = "3.13"

    def swap_package_name(self, value: t.Any) -> t.Any:
        if isinstance(value, list):
            value.remove("crackerjack")
            value.append(self.pkg_name)
        elif isinstance(value, str):
            value = value.replace("crackerjack", self.pkg_name)
        return value

    def update_pyproject_configs(self) -> None:
        toml_file = "pyproject.toml"
        self.our_toml_path = self.our_path / toml_file
        self.pkg_toml_path = self.pkg_path / toml_file
        if self.pkg_path.stem == "crackerjack":
            self.our_toml_path.write_text(self.pkg_toml_path.read_text())
            return
        our_toml_config: t.Any = loads(self.our_toml_path.read_text())
        pkg_toml_config: t.Any = loads(self.pkg_toml_path.read_text())
        pkg_toml_config.setdefault("tool", {})
        pkg_toml_config.setdefault("project", {})
        for tool, settings in our_toml_config["tool"].items():
            for setting, value in settings.items():
                if isinstance(value, dict):
                    for k, v in {
                        x: self.swap_package_name(y)
                        for x, y in value.items()
                        if isinstance(y, str | list) and "crackerjack" in y
                    }.items():
                        settings[setting][k] = v
                elif isinstance(value, str | list) and "crackerjack" in value:
                    value = self.swap_package_name(value)
                    settings[setting] = value
                if setting in (
                    "exclude-deps",
                    "exclude",
                    "excluded",
                    "skips",
                    "ignore",
                ) and isinstance(value, list):
                    conf = pkg_toml_config["tool"].get(tool, {}).get(setting, [])
                    settings[setting] = list(set(conf + value))
            pkg_toml_config["tool"][tool] = settings
        python_version_pattern = r"\s*W*(\d\.\d*)"
        requires_python = our_toml_config["project"]["requires-python"]
        classifiers = []
        for classifier in pkg_toml_config["project"].get("classifiers", []):
            classifier = re.sub(
                python_version_pattern, f" {self.python_version}", classifier
            )
            classifiers.append(classifier)
        pkg_toml_config["project"]["classifiers"] = classifiers
        pkg_toml_config["project"]["requires-python"] = requires_python
        self.pkg_toml_path.write_text(dumps(pkg_toml_config))

    def copy_configs(self) -> None:
        config_files = (".gitignore", ".pre-commit-config.yaml", ".libcst.codemod.yaml")
        for config in config_files:
            config_path = self.our_path / config
            pkg_config_path = self.pkg_path / config
            pkg_config_path.touch()
            if self.pkg_path.stem == "crackerjack":
                config_path.write_text(pkg_config_path.read_text())
                continue
            if config != ".gitignore":
                pkg_config_path.write_text(
                    (config_path.read_text()).replace("crackerjack", self.pkg_name)
                )
            execute(["git", "add", config])

    def run_interactive(self, hook: str) -> None:
        success: bool = False
        while not success:
            fail = execute(["pre-commit", "run", hook.lower(), "--all-files"])
            if fail.returncode > 0:
                retry = input(f"\n\n{hook.title()} failed. Retry? (y/N): ")
                print()
                if retry.strip().lower() == "y":
                    continue
                raise SystemExit(1)
            success = True

    def update_pkg_configs(self) -> None:
        self.copy_configs()
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
        self.update_pyproject_configs()

    def run_pre_commit(self) -> None:
        check_all = execute(["pre-commit", "run", "--all-files"])
        if check_all.returncode > 0:
            check_all = execute(["pre-commit", "run", "--all-files"])
            if check_all.returncode > 0:
                print("\n\nPre-commit failed. Please fix errors.\n")
                raise SystemExit(1)

    def process(self, options: t.Any) -> None:
        self.pkg_name = self.pkg_path.stem.lower().replace("-", "_")
        self.pkg_dir = self.pkg_path / self.pkg_name
        self.pkg_dir.mkdir(exist_ok=True)
        print("\nCrackerjacking...\n")
        if not options.do_not_update_configs:
            self.update_pkg_configs()
            execute(["pdm", "install"])
        if self.pkg_path.stem == "crackerjack" and options.update_precommit:
            execute(["pre-commit", "autoupdate"])
        if options.interactive:
            for hook in ("refurb", "bandit", "pyright"):
                self.run_interactive(hook)
        self.run_pre_commit()
        for option in (options.publish, options.bump):
            if option:
                execute(["pdm", "bump", option])
                break
        if options.publish:
            build = execute(["pdm", "build"], capture_output=True, text=True)
            print(build.stdout)
            if build.returncode > 0:
                print(build.stderr)
                print("\n\nBuild failed. Please fix errors.\n")
                raise SystemExit(1)
            execute(["pdm", "publish", "--no-build"])
        if options.commit:
            commit_msg = input("\nCommit message: ")
            execute(
                [
                    "git",
                    "commit",
                    "-m",
                    commit_msg,
                    "--no-verify",
                    "--",
                    ".",
                ]
            )
            execute(["git", "push", "origin", "main"])
        print("\nCrackerjack complete!\n")


crackerjack_it = Crackerjack().process
