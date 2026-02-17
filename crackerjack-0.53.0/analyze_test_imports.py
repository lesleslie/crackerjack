#!/usr/bin/env python3

import re
from pathlib import Path


def analyze_test_imports(
    tests_dir: Path = Path("tests"),
) -> dict[str, list[tuple[int, str]]]:
    expensive_imports = {}

    patterns = [
        r"^from crackerjack\.(?!models\.protocols|config)(\S+)",
        r"^import crackerjack\.(?!models\.protocols|config)(\S+)",
    ]

    for test_file in tests_dir.glob("test_*.py"):
        imports = []

        with test_file.open() as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()

                if not line.startswith(("from crackerjack.", "import crackerjack.")):
                    continue

                if any(
                    safe in line
                    for safe in ["models.protocols", "import CrackerjackSettings"]
                ):
                    continue

                for pattern in patterns:
                    if re.match(pattern, line):
                        imports.append((line_num, line))
                        break

        if imports:
            expensive_imports[str(test_file)] = imports

    return expensive_imports


def categorize_by_cost(imports: dict) -> dict[str, list[str]]:

    cost_categories = {
        "critical": [],
        "high": [],
        "medium": [],
        "low": [],
    }

    for file_path, import_list in imports.items():
        for line_num, import_stmt in import_list:
            module = (
                import_stmt.split("from ")[1].split(" import")[0]
                if " from " in import_stmt
                else import_stmt.split("import ")[1]
            )

            if any(
                expensive in module for expensive in ["__main__", "crackerjack.api"]
            ):
                if file_path not in cost_categories["critical"]:
                    cost_categories["critical"].append(file_path)
            elif any(
                high in module
                for high in ["core.", "agents.", "executors.", "managers."]
            ):
                if (
                    file_path not in cost_categories["high"]
                    and file_path not in cost_categories["critical"]
                ):
                    cost_categories["high"].append(file_path)
            elif any(medium in module for medium in ["services.", "adapters."]):
                if (
                    file_path not in cost_categories["medium"]
                    and file_path not in cost_categories["high"]
                    and file_path not in cost_categories["critical"]
                ):
                    cost_categories["medium"].append(file_path)
            else:
                if (
                    file_path not in cost_categories["low"]
                    and file_path not in cost_categories["medium"]
                    and file_path not in cost_categories["high"]
                    and file_path not in cost_categories["critical"]
                ):
                    cost_categories["low"].append(file_path)

    return cost_categories


def main() -> None:
    print("Analyzing test files for expensive module-level imports...\n")

    imports = analyze_test_imports()

    if not imports:
        print("✅ No expensive module-level imports found!")
        return

    print(f"Found {len(imports)} test files with expensive imports:\n")

    categories = categorize_by_cost(imports)

    total = sum(len(files) for files in categories.values())
    print(f"Total files affected: {total}\n")

    for category, files in categories.items():
        if files:
            print(f"## {category.upper()} PRIORITY ({len(files)} files)")
            for file_path in sorted(set(files)):
                file_imports = imports.get(file_path, [])
                print(f"\n{file_path}:")
                for line_num, import_stmt in file_imports:
                    print(f"  Line {line_num}: {import_stmt}")
            print()

    print("\n" + "=" * 70)
    print("RECOMMENDATION:")
    print("=" * 70)
    print("""
Move these imports inside test functions to prevent them from loading
during pytest collection. Example:


    from crackerjack.api import run_crackerjack

    def test_something():
        result = run_crackerjack()


    def test_something():
        from crackerjack.api import run_crackerjack
        result = run_crackerjack()

Priority order for fixes:
1. CRITICAL: __main__, api imports (huge impact)
2. HIGH: core, agents, executors imports
3. MEDIUM: managers, services imports
4. LOW: utilities, simple modules
""")


if __name__ == "__main__":
    main()
