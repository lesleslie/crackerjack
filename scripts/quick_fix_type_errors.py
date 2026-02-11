#!/usr/bin/env python3

import re
from pathlib import Path
from typing import List, Tuple


def fix_builtins_any(content: str) -> Tuple[str, int]:
    pattern = r'\bany\s*\('
    replacement = r'Any('
    new_content, count = re.subn(pattern, replacement, content)
    return new_content, count


def fix_list_dict_annotations(content: str) -> Tuple[str, int]:

    pattern1 = r'\blist\s*\['
    replacement1 = r'List['
    new_content, count1 = re.subn(pattern1, replacement1, content)


    pattern2 = r'\bdict\s*\['
    replacement2 = r'Dict['
    new_content, count2 = re.subn(pattern2, replacement2, new_content)

    return new_content, count1 + count2


def add_typing_imports(content: str) -> Tuple[str, int]:
    imports_needed = []


    if re.search(r'\bAny\s*\(', content):
        if 'from typing import' not in content or ('Any' not in content):
            imports_needed.append('Any')


    if re.search(r'\bList\s*\[', content):
        if 'from typing import' not in content or ('List' not in content):
            imports_needed.append('List')


    if re.search(r'\bDict\s*\[', content):
        if 'from typing import' not in content or ('Dict' not in content):
            imports_needed.append('Dict')

    if not imports_needed:
        return content, 0


    existing_import = re.search(r'from typing import\s+([^\n]+)', content)

    if existing_import:

        current_imports = existing_import.group(1).split(',')
        current_imports = [imp.strip() for imp in current_imports]

        for imp in imports_needed:
            if imp not in current_imports:
                current_imports.append(imp)

        new_import_str = ', '.join(current_imports)
        content = re.sub(
            r'from typing import\s+[^\n]+',
            f'from typing import {new_import_str}',
            content
        )
        return content, len(imports_needed)
    else:

        import_block = re.search(r'\n(import typing|from typing import)', content)
        if import_block:

            insert_pos = content.find('\n', import_block.end())
            new_import = f'from typing import {", ".join(imports_needed)}\n'
            content = content[:insert_pos] + new_import + content[insert_pos:]
        else:

            new_import = f'from typing import {", ".join(imports_needed)}\n'
            content = new_import + content

        return content, len(imports_needed)


def fix_missing_await_for_coroutines(content: str) -> Tuple[str, int]:
    fixes = 0


    lines = content.split('\n')
    new_lines = []

    i = 0
    while i < len(lines):
        line = lines[i]


        if re.search(r'=\s+[^=]+\([^)]*\)\s*$', line):


            if re.search(r'(async_|_async_|handle_|execute_|run_|fetch_|load_)', line):

                if i + 1 < len(lines) and 'Coroutine' in lines[i + 1]:

                    line = re.sub(r'(=\s+)([^=]+)(\s*\()', r'\1await \2\3', line)
                    fixes += 1

        new_lines.append(line)
        i += 1

    return '\n'.join(new_lines), fixes


def fix_file(file_path: Path) -> Tuple[str, int]:
    with open(file_path, 'r') as f:
        content = f.read()

    total_fixes = 0


    content, fixes = fix_builtins_any(content)
    total_fixes += fixes


    content, fixes = fix_list_dict_annotations(content)
    total_fixes += fixes


    content, fixes = add_typing_imports(content)
    total_fixes += fixes


    content, fixes = fix_missing_await_for_coroutines(content)
    total_fixes += fixes

    if total_fixes > 0:
        print(f"  Fixed {total_fixes} issue(s) in {file_path}")

    return content, total_fixes


def main():

    files_to_fix = [
        Path('crackerjack/core/defaults.py'),
        Path('crackerjack/services/ai/embeddings.py'),
        Path('crackerjack/parsers/json_parsers.py'),
        Path('crackerjack/parsers/regex_parsers.py'),
    ]

    total_fixed = 0

    for file_path in files_to_fix:
        if not file_path.exists():
            print(f"  ⚠️  File not found: {file_path}")
            continue

        print(f"🔧 Fixing {file_path}")
        try:
            new_content, fixes = fix_file(file_path)
            if fixes > 0:
                with open(file_path, 'w') as f:
                    f.write(new_content)
                total_fixed += fixes
            else:
                print(f"  No fixes needed")
        except Exception as e:
            print(f"  ❌ Error: {e}")

    print()
    print(f"✅ Total fixes applied: {total_fixed}")


if __name__ == '__main__':
    main()
