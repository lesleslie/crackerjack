import tempfile
import typing as t
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


class ConfigMode(t.TypedDict):
    max_time: float
    tiers: list[int]
    experimental: bool
    stages: list[str]


HOOKS_REGISTRY: dict[str, list[HookMetadata]] = {
    "structure": [
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
        },
    ],
    "package_management": [
        {
            "id": "uv-lock",
            "name": None,
            "repo": "https://github.com/astral-sh/uv-pre-commit",
            "rev": "0.8.14",
            "tier": 1,
            "time_estimate": 0.5,
            "stages": None,
            "args": None,
            "files": r"^pyproject\.toml$",
            "exclude": None,
            "additional_dependencies": None,
            "types_or": None,
            "language": None,
            "entry": None,
            "experimental": False,
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
            "exclude": r"uv\.lock|pyproject\.toml|tests/.*|docs/.*|.*\.md",
            "additional_dependencies": None,
            "types_or": None,
            "language": None,
            "entry": None,
            "experimental": False,
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
            "exclude": None,
            "additional_dependencies": None,
            "types_or": None,
            "language": None,
            "entry": None,
            "experimental": False,
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
        },
        {
            "id": "ruff-check",
            "name": None,
            "repo": "https://github.com/astral-sh/ruff-pre-commit",
            "rev": "v0.12.11",
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
        },
        {
            "id": "ruff-format",
            "name": None,
            "repo": "https://github.com/astral-sh/ruff-pre-commit",
            "rev": "v0.12.11",
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
        },
    ],
    "analysis": [
        {
            "id": "vulture",
            "name": None,
            "repo": "https://github.com/jendrikseipp/vulture",
            "rev": "v2.14",
            "tier": 3,
            "time_estimate": 2.0,
            "stages": ["pre-push", "manual"],
            "args": None,
            "files": "^crackerjack/.*\\.py$",
            "exclude": None,
            "additional_dependencies": None,
            "types_or": None,
            "language": None,
            "entry": None,
            "experimental": False,
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
        },
        {
            "id": "complexipy",
            "name": None,
            "repo": "https://github.com/rohaquinlop/complexipy-pre-commit",
            "rev": "v3.3.0",
            "tier": 3,
            "time_estimate": 2.0,
            "stages": ["pre-push", "manual"],
            "args": ["-d", "low"],
            "files": r"^crackerjack/.*\.py$",
            "exclude": r"^(\.venv/|tests/)",
            "additional_dependencies": None,
            "types_or": None,
            "language": None,
            "entry": None,
            "experimental": False,
        },
        {
            "id": "refurb",
            "name": None,
            "repo": "https://github.com/dosisod/refurb",
            "rev": "v2.1.0",
            "tier": 3,
            "time_estimate": 3.0,
            "stages": ["pre-push", "manual"],
            "args": ["--ignore", "FURB184", "--ignore", "FURB120"],
            "files": "^crackerjack/.*\\.py$",
            "exclude": r"^tests/.*\.py$",
            "additional_dependencies": None,
            "types_or": None,
            "language": None,
            "entry": None,
            "experimental": False,
        },
        {
            "id": "pyright",
            "name": None,
            "repo": "https://github.com/RobertCraigie/pyright-python",
            "rev": "v1.1.404",
            "tier": 3,
            "time_estimate": 5.0,
            "stages": ["pre-push", "manual"],
            "args": None,
            "files": "^crackerjack/.*\\.py$",
            "exclude": r"^crackerjack/(mcp|plugins)/.*\.py$|crackerjack/code_cleaner\.py$",
            "additional_dependencies": None,
            "types_or": None,
            "language": None,
            "entry": None,
            "experimental": False,
        },
    ],
    "experimental": [
        {
            "id": "pyrefly",
            "name": "pyrefly",
            "repo": "local",
            "rev": "",
            "tier": 3,
            "time_estimate": 5.0,
            "stages": ["manual"],
            "args": ["--check"],
            "files": "^crackerjack/.*\\.py$",
            "exclude": None,
            "additional_dependencies": ["pyrefly >= 0.1.0"],
            "types_or": ["python"],
            "language": "python",
            "entry": "python -m pyrefly",
            "experimental": True,
        },
        {
            "id": "ty",
            "name": "ty",
            "repo": "local",
            "rev": "",
            "tier": 3,
            "time_estimate": 2.0,
            "stages": ["manual"],
            "args": ["--check"],
            "files": "^crackerjack/.*\\.py$",
            "exclude": None,
            "additional_dependencies": ["ty >= 0.1.0"],
            "types_or": ["python"],
            "language": "python",
            "entry": "python -m ty",
            "experimental": True,
        },
    ],
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
  # {{ repo.comment }}
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

{%- endfor %}
"""


class DynamicConfigGenerator:
    def __init__(self) -> None:
        self.template = jinja2.Template(PRE_COMMIT_TEMPLATE)

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
                    filtered_hooks.append(hook)

        return filtered_hooks

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

        return self.template.render(repos=repos)

    def create_temp_config(
        self,
        mode: str,
        enabled_experimental: list[str] | None = None,
    ) -> Path:
        config_content = self.generate_config(mode, enabled_experimental)
        temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".yaml",
            prefix=f"crackerjack-{mode}-",
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
) -> Path:
    return DynamicConfigGenerator().create_temp_config(mode, enabled_experimental)


def get_available_modes() -> list[str]:
    return list(CONFIG_MODES.keys())


def add_experimental_hook(hook_id: str, hook_config: HookMetadata) -> None:
    hook_config["experimental"] = True
    HOOKS_REGISTRY["experimental"].append(hook_config)


def remove_experimental_hook(hook_id: str) -> None:
    HOOKS_REGISTRY["experimental"] = [
        hook for hook in HOOKS_REGISTRY["experimental"] if hook["id"] != hook_id
    ]
