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
            "rev": "v5.0.0",
            "tier": 1,
            "time_estimate": 0.2,
            "stages": None,
            "args": None,
            "files": None,
            "exclude": None,
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
            "rev": "v5.0.0",
            "tier": 1,
            "time_estimate": 0.2,
            "stages": None,
            "args": None,
            "files": None,
            "exclude": None,
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
            "rev": "v5.0.0",
            "tier": 1,
            "time_estimate": 0.3,
            "stages": None,
            "args": None,
            "files": None,
            "exclude": None,
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
            "rev": "v5.0.0",
            "tier": 1,
            "time_estimate": 0.3,
            "stages": None,
            "args": None,
            "files": None,
            "exclude": None,
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
            "rev": "v5.0.0",
            "tier": 1,
            "time_estimate": 0.5,
            "stages": None,
            "args": None,
            "files": None,
            "exclude": None,
            "additional_dependencies": None,
            "types_or": None,
            "language": None,
            "entry": None,
            "experimental": False,
        },
    ],
    "package_management": [
        {
            "id": "pyproject-fmt",
            "name": None,
            "repo": "https://github.com/tox-dev/pyproject-fmt",
            "rev": "v2.6.0",
            "tier": 1,
            "time_estimate": 0.5,
            "stages": None,
            "args": ["-n"],
            "files": None,
            "exclude": None,
            "additional_dependencies": None,
            "types_or": None,
            "language": None,
            "entry": None,
            "experimental": False,
        },
        {
            "id": "uv-lock",
            "name": None,
            "repo": "https://github.com/astral-sh/uv-pre-commit",
            "rev": "0.7.21",
            "tier": 1,
            "time_estimate": 0.5,
            "stages": None,
            "args": None,
            "files": "^pyproject\\.toml$",
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
            "id": "detect-secrets",
            "name": None,
            "repo": "https://github.com/Yelp/detect-secrets",
            "rev": "v1.5.0",
            "tier": 2,
            "time_estimate": 1.0,
            "stages": None,
            "args": None,
            "files": None,
            "exclude": "uv\\.lock|pyproject\\.toml|tests/.*|docs/.*|.*\\.md",
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
            "files": None,
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
            "exclude": None,
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
            "rev": "v0.12.3",
            "tier": 2,
            "time_estimate": 1.5,
            "stages": None,
            "args": None,
            "files": None,
            "exclude": None,
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
            "rev": "v0.12.3",
            "tier": 2,
            "time_estimate": 1.0,
            "stages": None,
            "args": None,
            "files": None,
            "exclude": None,
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
            "exclude": None,
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
            "files": None,
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
            "rev": "v4.0.3",
            "tier": 3,
            "time_estimate": 1.5,
            "stages": ["pre-push", "manual"],
            "args": None,
            "files": None,
            "exclude": None,
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
            "rev": "v3.0.0",
            "tier": 3,
            "time_estimate": 2.0,
            "stages": ["pre-push", "manual"],
            "args": ["-d", "low"],
            "files": None,
            "exclude": None,
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
            "args": None,
            "files": None,
            "exclude": None,
            "additional_dependencies": None,
            "types_or": None,
            "language": None,
            "entry": None,
            "experimental": False,
        },
        {
            "id": "autotyping",
            "name": "autotyping",
            "repo": "local",
            "rev": "",
            "tier": 3,
            "time_estimate": 7.0,
            "stages": ["pre-push", "manual"],
            "args": [
                "--aggressive",
                "--only-without-imports",
                "--guess-common-names",
                "crackerjack",
            ],
            "files": "^crackerjack/.*\\.py$",
            "exclude": None,
            "additional_dependencies": ["autotyping>=24.3.0", "libcst>=1.1.0"],
            "types_or": ["python", "pyi"],
            "language": "python",
            "entry": "python -m autotyping",
            "experimental": False,
        },
        {
            "id": "pyright",
            "name": None,
            "repo": "https://github.com/RobertCraigie/pyright-python",
            "rev": "v1.1.403",
            "tier": 3,
            "time_estimate": 5.0,
            "stages": ["pre-push", "manual"],
            "args": None,
            "files": None,
            "exclude": None,
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
            "additional_dependencies": ["pyrefly>=0.1.0"],
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
            "additional_dependencies": ["ty>=0.1.0"],
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
{%- for repo_group in repos %}
  {%- if repo_group.comment %}
  {%- endif %}
  - repo: {{ repo_group.repo }}
    {%- if repo_group.rev %}
    rev: {{ repo_group.rev }}
    {%- endif %}
    hooks:
    {%- for hook in repo_group.hooks %}
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
        self, hook: HookMetadata, config: ConfigMode, enabled_experimental: list[str]
    ) -> bool:
        if hook["tier"] not in config["tiers"]:
            return False
        if hook["experimental"]:
            if not config["experimental"]:
                return False
            if enabled_experimental and hook["id"] not in enabled_experimental:
                return False
        if hook["time_estimate"] > config["max_time"]:
            return False
        return True

    def filter_hooks_for_mode(
        self, mode: str, enabled_experimental: list[str] | None = None
    ) -> list[HookMetadata]:
        config = CONFIG_MODES[mode]
        filtered_hooks = []
        enabled_experimental = enabled_experimental or []
        for category_hooks in HOOKS_REGISTRY.values():
            for hook in category_hooks:
                if self._should_include_hook(hook, config, enabled_experimental):
                    filtered_hooks.append(hook)

        return filtered_hooks

    def group_hooks_by_repo(
        self, hooks: list[HookMetadata]
    ) -> dict[tuple[str, str], list[HookMetadata]]:
        repo_groups: dict[tuple[str, str], list[HookMetadata]] = {}
        for hook in hooks:
            key = (hook["repo"], hook["rev"])
            if key not in repo_groups:
                repo_groups[key] = []
            repo_groups[key].append(hook)

        return repo_groups

    def _get_repo_comment(self, repo_url: str) -> str | None:
        if repo_url == "https://github.com/pre-commit/pre-commit-hooks":
            return "File structure and format validators"
        elif (
            "security" in repo_url
            or "bandit" in repo_url
            or "detect-secrets" in repo_url
        ):
            return "Security checks"
        elif "ruff" in repo_url or "mdformat" in repo_url or "codespell" in repo_url:
            return "Code formatting and quality"
        elif repo_url == "local":
            return "Local tools and custom hooks"
        return None

    def generate_config(
        self, mode: str, enabled_experimental: list[str] | None = None
    ) -> str:
        filtered_hooks = self.filter_hooks_for_mode(mode, enabled_experimental)
        repo_groups = self.group_hooks_by_repo(filtered_hooks)
        repos = []
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
        self, mode: str, enabled_experimental: list[str] | None = None
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
    mode: str, enabled_experimental: list[str] | None = None
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
