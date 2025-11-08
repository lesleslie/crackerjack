import tempfile
import typing as t
from contextlib import suppress
from pathlib import Path

import jinja2


class HookMetadata(t.TypedDict):
    id: str
    name: str | None
    repo: str
    rev: str
    tier: int
    time_estimate: float
    stages: list[str] | None
    args: list[str] | None
    files: str | None
    exclude: str | None
    additional_dependencies: list[str] | None
    types_or: list[str] | None
    language: str | None
    entry: str | None
    experimental: bool
    pass_filenames: bool | None


class ConfigMode(t.TypedDict):
    max_time: float
    tiers: list[int]
    experimental: bool
    stages: list[str]


HOOKS_REGISTRY: dict[str, list[HookMetadata]] = {
    "structure": [
        {
            "id": "validate-regex-patterns",
            "name": "validate-regex-patterns",
            "repo": "local",
            "rev": "",
            "tier": 1,
            "time_estimate": 0.3,
            "stages": None,
            "args": None,
            "files": r"\.py$",
            "exclude": r"^\.venv/",
            "additional_dependencies": None,
            "types_or": None,
            "language": "system",
            "entry": "uv run python -m crackerjack.tools.validate_regex_patterns",
            "experimental": False,
            "pass_filenames": None,
        },
        {
            "id": "trailing-whitespace",
            "name": "trailing-whitespace",
            "repo": "https://github.com/pre-commit/pre-commit-hooks",
            "rev": "v6.0.0",
            "tier": 1,
            "time_estimate": 0.2,
            "stages": None,
            "args": None,
            "files": None,
            "exclude": r"^\.venv/",
            "additional_dependencies": None,
            "types_or": None,
            "language": None,
            "entry": None,
            "experimental": False,
            "pass_filenames": None,
        },
        {
            "id": "end-of-file-fixer",
            "name": "end-of-file-fixer",
            "repo": "https://github.com/pre-commit/pre-commit-hooks",
            "rev": "v6.0.0",
            "tier": 1,
            "time_estimate": 0.2,
            "stages": None,
            "args": None,
            "files": None,
            "exclude": r"^\.venv/",
            "additional_dependencies": None,
            "types_or": None,
            "language": None,
            "entry": None,
            "experimental": False,
            "pass_filenames": None,
        },
        {
            "id": "check-yaml",
            "name": "check-yaml",
            "repo": "https://github.com/pre-commit/pre-commit-hooks",
            "rev": "v6.0.0",
            "tier": 1,
            "time_estimate": 0.3,
            "stages": None,
            "args": None,
            "files": None,
            "exclude": r"^\.venv/",
            "additional_dependencies": None,
            "types_or": None,
            "language": None,
            "entry": None,
            "experimental": False,
            "pass_filenames": None,
        },
        {
            "id": "check-toml",
            "name": "check-toml",
            "repo": "https://github.com/pre-commit/pre-commit-hooks",
            "rev": "v6.0.0",
            "tier": 1,
            "time_estimate": 0.3,
            "stages": None,
            "args": None,
            "files": None,
            "exclude": r"^\.venv/",
            "additional_dependencies": None,
            "types_or": None,
            "language": None,
            "entry": None,
            "experimental": False,
            "pass_filenames": None,
        },
        {
            "id": "check-added-large-files",
            "name": "check-added-large-files",
            "repo": "https://github.com/pre-commit/pre-commit-hooks",
            "rev": "v6.0.0",
            "tier": 1,
            "time_estimate": 0.5,
            "stages": None,
            "args": None,
            "files": None,
            "exclude": r"^\.venv/",
            "additional_dependencies": None,
            "types_or": None,
            "language": None,
            "entry": None,
            "experimental": False,
            "pass_filenames": None,
        },
    ],
    "package_management": [
        {
            "id": "uv-lock",
            "name": None,
            "repo": "https://github.com/astral-sh/uv-pre-commit",
            "rev": "0.9.0",
            "tier": 1,
            "time_estimate": 0.5,
            "stages": None,
            "args": None,
            "files": r"^ pyproject\.toml$",
            "exclude": None,
            "additional_dependencies": None,
            "types_or": None,
            "language": None,
            "entry": None,
            "experimental": False,
            "pass_filenames": None,
        },
    ],
    "security": [
        {
            "id": "gitleaks",
            "name": None,
            "repo": "https://github.com/gitleaks/gitleaks",
            "rev": "v8.28.0",
            "tier": 2,
            "time_estimate": 1.0,
            "stages": None,
            "args": None,
            "files": None,
            "exclude": r"uv\.lock|pyproject\.toml|tests/.*|docs/.*|\.claude/.*|.*\.md",
            "additional_dependencies": None,
            "types_or": None,
            "language": None,
            "entry": None,
            "experimental": False,
            "pass_filenames": None,
        },
        {
            "id": "bandit",
            "name": None,
            "repo": "https://github.com/PyCQA/bandit",
            "rev": "1.8.6",
            "tier": 3,
            "time_estimate": 3.0,
            "stages": ["pre-push", "manual"],
            "args": ["-c", "pyproject.toml", "-r", "-ll"],
            "files": "^crackerjack/.*\\.py$",
            "exclude": r"^tests/",
            "additional_dependencies": None,
            "types_or": None,
            "language": None,
            "entry": None,
            "experimental": False,
            "pass_filenames": None,
        },
    ],
    "formatting": [
        {
            "id": "codespell",
            "name": None,
            "repo": "https://github.com/codespell-project/codespell",
            "rev": "v2.4.1",
            "tier": 2,
            "time_estimate": 1.0,
            "stages": None,
            "args": None,
            "files": None,
            "exclude": r"^\.venv/",
            "additional_dependencies": ["tomli"],
            "types_or": None,
            "language": None,
            "entry": None,
            "experimental": False,
            "pass_filenames": None,
        },
        {
            "id": "ruff-check",
            "name": None,
            "repo": "https://github.com/astral-sh/ruff-pre-commit",
            "rev": "v0.14.0",
            "tier": 2,
            "time_estimate": 1.5,
            "stages": None,
            "args": None,
            "files": None,
            "exclude": r"^\.venv/",
            "additional_dependencies": None,
            "types_or": None,
            "language": None,
            "entry": None,
            "experimental": False,
            "pass_filenames": None,
        },
        {
            "id": "ruff-format",
            "name": None,
            "repo": "https://github.com/astral-sh/ruff-pre-commit",
            "rev": "v0.14.0",
            "tier": 2,
            "time_estimate": 1.0,
            "stages": None,
            "args": None,
            "files": None,
            "exclude": r"^\.venv/",
            "additional_dependencies": None,
            "types_or": None,
            "language": None,
            "entry": None,
            "experimental": False,
            "pass_filenames": None,
        },
        {
            "id": "mdformat",
            "name": None,
            "repo": "https://github.com/executablebooks/mdformat",
            "rev": "0.7.22",
            "tier": 2,
            "time_estimate": 0.5,
            "stages": None,
            "args": None,
            "files": None,
            "exclude": r"^\.venv/",
            "additional_dependencies": ["mdformat-ruff"],
            "types_or": None,
            "language": None,
            "entry": None,
            "experimental": False,
            "pass_filenames": None,
        },
    ],
    "analysis": [
        {
            "id": "skylos",
            "name": "skylos-dead-code-detection",
            "repo": "local",
            "rev": "",
            "tier": 3,
            "time_estimate": 0.1,
            "stages": ["pre-push", "manual"],
            "args": ["crackerjack", "--exclude", "tests"],
            "files": None,
            "exclude": r"^tests/",
            "additional_dependencies": None,
            "types_or": None,
            "language": "system",
            "entry": "skylos",
            "experimental": False,
            "pass_filenames": False,
        },
        {
            "id": "creosote",
            "name": None,
            "repo": "https://github.com/fredrikaverpil/creosote",
            "rev": "v4.1.0",
            "tier": 3,
            "time_estimate": 1.5,
            "stages": ["pre-push", "manual"],
            "args": None,
            "files": None,
            "exclude": r"^\.venv/",
            "additional_dependencies": None,
            "types_or": None,
            "language": None,
            "entry": None,
            "experimental": False,
            "pass_filenames": None,
        },
        {
            "id": "complexipy",
            "name": None,
            "repo": "https://github.com/rohaquinlop/complexipy-pre-commit",
            "rev": "v3.3.0",
            "tier": 3,
            "time_estimate": 1.0,
            "stages": ["pre-push", "manual"],
            "args": ["-d", "low", "--max-complexity-allowed", "15"],
            "files": r"^crackerjack/.*\.py$",
            "exclude": r"^(\.venv/|tests/)",
            "additional_dependencies": None,
            "types_or": None,
            "language": None,
            "entry": None,
            "experimental": False,
            "pass_filenames": None,
        },
        {
            "id": "refurb",
            "name": None,
            "repo": "https://github.com/dosisod/refurb",
            "rev": "v2.2.0",
            "tier": 3,
            "time_estimate": 3.0,
            "stages": ["pre-push", "manual"],
            "args": [],
            "files": "^crackerjack/.*\\.py$",
            "exclude": r"^tests/",
            "additional_dependencies": None,
            "types_or": None,
            "language": None,
            "entry": None,
            "experimental": False,
            "pass_filenames": None,
        },
        {
            "id": "zuban",
            "name": "zuban-type-checking",
            "repo": "local",
            "rev": "",
            "tier": 3,
            "time_estimate": 0.15,
            "stages": ["pre-push", "manual"],
            "args": ["--config-file", "mypy.ini", "./crackerjack"],
            "files": None,
            "exclude": r"^tests/",
            "additional_dependencies": None,
            "types_or": None,
            "language": "system",
            "entry": "uv run zuban check",
            "experimental": False,
            "pass_filenames": False,
        },
    ],
    "experimental": [],
}

CONFIG_MODES: dict[str, ConfigMode] = {
    "fast": {
        "max_time": 5.0,
        "tiers": [1, 2],
        "experimental": False,
        "stages": ["pre-commit"],
    },
    "comprehensive": {
        "max_time": 30.0,
        "tiers": [1, 2, 3],
        "experimental": False,
        "stages": ["pre-commit", "pre-push", "manual"],
    },
    "experimental": {
        "max_time": 60.0,
        "tiers": [1, 2, 3],
        "experimental": True,
        "stages": ["pre-commit", "pre-push", "manual"],
    },
}

PRE_COMMIT_TEMPLATE = """repos:
{%- for repo in repos %}
  {%- if repo.comment %}

  {%- endif %}
  - repo: {{ repo.repo }}
    {%- if repo.rev %}
    rev: {{ repo.rev }}
    {%- endif %}
    hooks:
    {%- for hook in repo.hooks %}
      - id: {{ hook.id }}
        {%- if hook.name %}
        name: {{ hook.name }}
        {%- endif %}
        {%- if hook.entry %}
        entry: {{ hook.entry }}
        {%- endif %}
        {%- if hook.language %}
        language: {{ hook.language }}
        {%- endif %}
        {%- if hook.args %}
        args: {{ hook.args | tojson }}
        {%- endif %}
        {%- if hook.pass_filenames is not none %}
        pass_filenames: {{ hook.pass_filenames | lower }}
        {%- endif %}
        {%- if hook.files %}
        files: {{ hook.files }}
        {%- endif %}
        {%- if hook.exclude %}
        exclude: {{ hook.exclude }}
        {%- endif %}
        {%- if hook.types_or %}
        types_or: {{ hook.types_or | tojson }}
        {%- endif %}
        {%- if hook.stages %}
        stages: {{ hook.stages | tojson }}
        {%- endif %}
        {%- if hook.additional_dependencies %}
        additional_dependencies: {{ hook.additional_dependencies | tojson }}
        {%- endif %}
    {%- endfor %}

{%-endfor %}
"""


class DynamicConfigGenerator:
    def __init__(self, package_directory: str | None = None) -> None:
        self.template = jinja2.Template(PRE_COMMIT_TEMPLATE)
        self.package_directory = self._sanitize_package_directory(
            package_directory or self._detect_package_directory()
        )

    def _sanitize_package_directory(self, package_directory: str) -> str:
        return package_directory.replace("-", "_")

    def _detect_package_directory(self) -> str:
        from pathlib import Path

        current_dir = Path.cwd()
        if (current_dir / "crackerjack").exists() and (
            current_dir / "pyproject.toml"
        ).exists():
            with suppress(Exception):
                import tomllib

                with (current_dir / "pyproject.toml").open("rb") as f:
                    data = tomllib.load(f)
                if data.get("project", {}).get("name") == "crackerjack":
                    return "crackerjack"

        pyproject_path = current_dir / "pyproject.toml"
        if pyproject_path.exists():
            with suppress(Exception):
                import tomllib

                with pyproject_path.open("rb") as f:
                    data = tomllib.load(f)

                if "project" in data and "name" in data["project"]:
                    package_name = str(data["project"]["name"])

                    if (current_dir / package_name).exists():
                        return package_name

        if (current_dir / current_dir.name).exists():
            return current_dir.name

        return current_dir.name

    def _should_include_hook(
        self,
        hook: HookMetadata,
        config: ConfigMode,
        enabled_experimental: list[str],
    ) -> bool:
        if hook["tier"] not in config["tiers"]:
            return False
        if hook["experimental"]:
            if not config["experimental"]:
                return False
            if enabled_experimental and hook["id"] not in enabled_experimental:
                return False
        return not hook["time_estimate"] > config["max_time"]

    def filter_hooks_for_mode(
        self,
        mode: str,
        enabled_experimental: list[str] | None = None,
    ) -> list[HookMetadata]:
        config = CONFIG_MODES[mode]
        filtered_hooks: list[HookMetadata] = []
        enabled_experimental = enabled_experimental or []
        for category_hooks in HOOKS_REGISTRY.values():
            for hook in category_hooks:
                if self._should_include_hook(hook, config, enabled_experimental):
                    updated_hook = self._update_hook_for_package(hook.copy())
                    filtered_hooks.append(updated_hook)

        return filtered_hooks

    def _update_hook_for_package(self, hook: HookMetadata) -> HookMetadata:
        if hook["id"] == "skylos" and hook["args"]:
            hook["args"] = [self.package_directory, "--exclude", "tests"]

        elif hook["id"] == "zuban" and hook["args"]:
            updated_args = []
            for arg in hook["args"]:
                if arg == "./crackerjack":
                    updated_args.append(f"./{self.package_directory}")
                else:
                    updated_args.append(arg)
            hook["args"] = updated_args

        elif hook["files"] and "crackerjack" in hook["files"]:
            hook["files"] = hook["files"].replace("crackerjack", self.package_directory)

        elif hook["exclude"] and "crackerjack" in hook["exclude"]:
            hook["exclude"] = hook["exclude"].replace(
                "crackerjack", self.package_directory
            )

        if hook["exclude"]:
            if "src/" not in hook["exclude"]:
                hook["exclude"] = f"{hook['exclude']}|^src/"
        else:
            if hook["id"] in (
                "skylos",
                "zuban",
                "bandit",
                "refurb",
                "complexipy",
            ):
                hook["exclude"] = r"^tests/|^src/"
            else:
                hook["exclude"] = "^src/"

        return hook

    def group_hooks_by_repo(
        self,
        hooks: list[HookMetadata],
    ) -> dict[tuple[str, str], list[HookMetadata]]:
        repo_groups: dict[tuple[str, str], list[HookMetadata]] = {}
        for hook in hooks:
            key = (hook["repo"], hook["rev"])
            if key not in repo_groups:
                repo_groups[key] = []
            repo_groups[key].append(hook)

        return repo_groups

    def _get_repo_comment(self, repo_url: str) -> str | None:
        repo_comments = {
            "https://github.com/pre-commit/pre-commit-hooks": "File structure and format validators",
            "local": "Local tools and custom hooks",
        }
        if repo_url in repo_comments:
            return repo_comments[repo_url]
        security_keywords = ["security", "bandit", "gitleaks"]
        if any(keyword in repo_url for keyword in security_keywords):
            return "Security checks"
        formatting_keywords = ["ruff", "mdformat", "codespell"]
        if any(keyword in repo_url for keyword in formatting_keywords):
            return "Code formatting and quality"

        return None

    def _merge_configs(
        self,
        base_config: dict[str, t.Any],
        new_config: dict[str, t.Any],
    ) -> dict[str, t.Any]:
        result = base_config.copy()

        for key, value in new_config.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value

        return result

    def generate_config(
        self,
        mode: str,
        enabled_experimental: list[str] | None = None,
    ) -> str:
        filtered_hooks = self.filter_hooks_for_mode(mode, enabled_experimental)
        repo_groups = self.group_hooks_by_repo(filtered_hooks)
        repos: list[dict[str, t.Any]] = []
        for (repo_url, rev), hooks in repo_groups.items():
            repo_data = {
                "repo": repo_url,
                "rev": rev,
                "hooks": hooks,
                "comment": self._get_repo_comment(repo_url),
            }
            repos.append(repo_data)

        content = self.template.render(repos=repos)
        # Preserve a space after 'repos:' to satisfy downstream consumers/tests
        if content.startswith("repos:\n"):
            content = content.replace("repos:\n", "repos: \n", 1)
        # Ensure 'hooks:' lines include a trailing space for readability
        content = content.replace("\n    hooks:\n", "\n    hooks: \n")
        return content

    def create_temp_config(
        self,
        mode: str,
        enabled_experimental: list[str] | None = None,
    ) -> Path:
        config_content = self.generate_config(mode, enabled_experimental)
        temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".yaml",
            prefix=f"crackerjack - {mode} -",
            delete=False,
            encoding="utf-8",
        )
        temp_file.write(config_content)
        temp_file.flush()
        temp_file.close()

        return Path(temp_file.name)


def generate_config_for_mode(
    mode: str,
    enabled_experimental: list[str] | None = None,
    package_directory: str | None = None,
) -> Path:
    return DynamicConfigGenerator(package_directory).create_temp_config(
        mode, enabled_experimental
    )


def get_available_modes() -> list[str]:
    return list[t.Any](CONFIG_MODES.keys())


def add_experimental_hook(hook_id: str, hook_config: HookMetadata) -> None:
    hook_config["experimental"] = True
    HOOKS_REGISTRY["experimental"].append(hook_config)


def remove_experimental_hook(hook_id: str) -> None:
    HOOKS_REGISTRY["experimental"] = [
        hook for hook in HOOKS_REGISTRY["experimental"] if hook["id"] != hook_id
    ]
