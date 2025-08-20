from pathlib import Path

from crackerjack.models.protocols import OptionsProtocol
from crackerjack.models.task import HookResult
from crackerjack.plugins import (
    CustomHookDefinition,
    HookPluginBase,
    HookStage,
    PluginMetadata,
    PluginType,
)


class ExampleHookPlugin(HookPluginBase):
    def __init__(self) -> None:
        metadata = PluginMetadata(
            name="example - hooks",
            version="1.0.0",
            plugin_type=PluginType.HOOK,
            description="Example custom hooks for demonstration",
            author="Crackerjack Team",
            license="MIT",
        )
        super().__init__(metadata)

    def get_hook_definitions(self) -> list[CustomHookDefinition]:
        return [
            CustomHookDefinition(
                name="check - todos",
                description="Check for TODO / FIXME comments in code",
                command=["grep", " - n", " - E", "(TODO | FIXME | XXX)"],
                file_patterns=[" * .py", " * .js", " * .ts", " * .go", " * .rs"],
                timeout=30,
                stage=HookStage.FAST,
                requires_files=True,
                parallel_safe=True,
            ),
            CustomHookDefinition(
                name="check - print - statements",
                description="Check for debug print statements",
                command=["grep", " - n", "print("],
                file_patterns=[" * .py"],
                timeout=15,
                stage=HookStage.FAST,
                requires_files=True,
                parallel_safe=True,
            ),
            CustomHookDefinition(
                name="validate - json",
                description="Validate JSON files are well - formed",
                file_patterns=[" * .json"],
                timeout=30,
                stage=HookStage.COMPREHENSIVE,
                requires_files=True,
                parallel_safe=True,
            ),
        ]

    def execute_hook(
        self,
        hook_name: str,
        files: list[Path],
        options: OptionsProtocol,
    ) -> HookResult:
        if hook_name == "validate - json":
            return self._validate_json_files(files)
        else:
            return super().execute_hook(hook_name, files, options)

    def _validate_json_files(self, files: list[Path]) -> HookResult:
        import json
        import time

        start_time = time.time()
        errors = []

        json_files = [f for f in files if f.suffix == ".json"]

        for json_file in json_files:
            try:
                with open(json_file) as f:
                    json.load(f)
            except json.JSONDecodeError as e:
                errors.append(f"{json_file}: {e.lineno}: {e.msg}")
            except Exception as e:
                errors.append(f"{json_file}: {e}")

        duration = time.time() - start_time

        if errors:
            return HookResult(
                name="validate - json",
                status="failed",
                duration=duration,
                output="\n".join(errors),
                error_message=f"Found {len(errors)} JSON validation errors",
            )
        else:
            return HookResult(
                name="validate - json",
                status="passed",
                duration=duration,
                output=f"Validated {len(json_files)} JSON files",
                error_message="",
            )

    def activate(self) -> bool:
        if self.console:
            self.console.print("[green]✅[ / green] Example hook plugin activated")
        return True

    def deactivate(self) -> bool:
        if self.console:
            self.console.print("[yellow]⏹️[ / yellow] Example hook plugin deactivated")
        return True


plugin = ExampleHookPlugin()
