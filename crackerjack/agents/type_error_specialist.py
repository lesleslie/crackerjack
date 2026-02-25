from __future__ import annotations
import ast
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING
from .base import FixResult, Issue, IssueType, SubAgent
if TYPE_CHECKING:
    from .base import AgentContext
logger = logging.getLogger(__name__)

class TypeErrorSpecialistAgent(SubAgent):
    name = 'TypeErrorSpecialist'

    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)
        self.log = logger.info  # type: ignore

    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.TYPE_ERROR}

    async def can_handle(self, issue: Issue) -> float:
        if issue.type != IssueType.TYPE_ERROR:
            return 0.0
        if not issue.message:
            return 0.0
        if issue.stage in ('zuban', 'pyscn'):
            return 0.85
        return 0.6

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        self.log(f'TypeErrorSpecialist analyzing: {issue.message[:100]}')
        if issue.file_path is None:
            return FixResult(success=False, confidence=0.0, remaining_issues=['No file path provided'])
        file_path = Path(issue.file_path)
        if not file_path.exists():
            return FixResult(success=False, confidence=0.0, remaining_issues=[f'File not found: {file_path}'])
        content = self.context.get_file_content(file_path)
        if not content:
            return FixResult(success=False, confidence=0.0, remaining_issues=['Could not read file content'])
        new_content, fixes_applied = await self._apply_type_fixes(content, issue, file_path)
        if new_content == content:
            return FixResult(success=False, confidence=0.0, remaining_issues=['No changes applied'])
        try:
            file_path.write_text(new_content)
            return FixResult(success=True, confidence=0.7, fixes_applied=fixes_applied, files_modified=[file_path])
        except Exception as e:
            return FixResult(success=False, confidence=0.0, remaining_issues=[f'Failed to write file: {e}'])

    async def _apply_type_fixes(self, content: str, issue: Issue, file_path: Path) -> tuple[str, list[str]]:
        fixes: list[Any] = []  # type: ignore
        new_content = content
        new_content, fix1 = self._fix_missing_return_types(new_content, issue)
        if fix1:
            fixes.extend(fix1)
        new_content, fix2 = self._add_future_annotations(new_content)
        if fix2:
            fixes.append("Added 'from __future__ import annotations'")
        new_content, fix3 = self._add_typing_imports(new_content, issue)
        if fix3:
            fixes.extend(fix3)
        new_content, fix4 = self._infer_and_add_return_types(new_content, issue)
        if fix4:
            fixes.extend(fix4)
        new_content, fix5 = self._fix_complex_generic_types(new_content, issue)
        if fix5:
            fixes.extend(fix5)
        new_content, fix6 = self._detect_and_fix_protocol_patterns(new_content, issue)
        if fix6:
            fixes.extend(fix6)
        new_content, fix7 = self._add_self_type_for_methods(new_content, issue)
        if fix7:
            fixes.extend(fix7)
        new_content, fix8 = self._fix_optional_union_types(new_content, issue)
        if fix8:
            fixes.extend(fix8)
        return (new_content, fixes)

    def _fix_missing_return_types(self, content: str, issue: Issue) -> tuple[str, list[str]]:
        fixes: list[Any] = []  # type: ignore
        lines = content.split('\n')
        new_lines = []
        for line in lines:
            if re.match('^\\s*def\\s+\\w+\\s*\\([^)]*\\)\\s*:', line):
                if '->' not in line and 'async def' not in line:
                    if any((keyword in issue.message.lower() for keyword in ('missing', 'return', 'type'))):
                        modified = line.rstrip().rstrip(':') + ' -> None:'
                        if modified != line:
                            new_lines.append(modified)
                            fixes.append(f'Added return type annotation: {modified[:80]}...')
                            continue
            new_lines.append(line)
        return ('\n'.join(new_lines), fixes)

    def _add_future_annotations(self, content: str) -> tuple[str, list[str]]:
        if 'from __future__ import annotations' in content:
            return (content, [])
        lines = content.split('\n')
        insert_index = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(('"""', "'''")):
                continue
            if stripped.startswith(('import ', 'from ')):
                insert_index = i
                break
            if stripped and (not stripped.startswith('#')):
                insert_index = i
                break
        lines.insert(insert_index, 'from __future__ import annotations')
        return ('\n'.join(lines), ['Added __future__ annotations import'])

    def _add_typing_imports(self, content: str, issue: Issue) -> tuple[str, list[str]]:
        fixes: list[Any] = []  # type: ignore
        new_imports = []
        message_lower = issue.message.lower()
        if 'optional' in message_lower or 'None' in message_lower:
            if 'from typing import' in content:
                if 'Optional' not in content:
                    content = re.sub('(from typing import [^\\n]+)', '\\1, Optional', content)
                    fixes.append('Added Optional to typing imports')
            else:
                new_imports.append('from typing import Optional')
        if 'union' in message_lower or ' | ' in issue.message:
            if 'from typing import' in content:
                if 'Union' not in content:
                    content = re.sub('(from typing import [^\\n]+)', '\\1, Union', content)
                    fixes.append('Added Union to typing imports')
            else:
                new_imports.append('from typing import Union')
        if 'list[' in message_lower or 'dict[' in message_lower:
            if 'from typing import' in content:
                if 'List' not in content or 'Dict' not in content:
                    content = re.sub('(from typing import [^\\n]+)', '\\1, List, Dict', content)
                    fixes.append('Added List, Dict to typing imports')
            else:
                new_imports.append('from typing import List, Dict')
        if new_imports:
            lines = content.split('\n')
            insert_index = 0
            for i, line in enumerate(lines):
                if 'from __future__ import annotations' in line:
                    insert_index = i + 1
                    break
                elif line.strip().startswith(('import', 'from')) and insert_index == 0:
                    insert_index = i
            for new_import in reversed(new_imports):
                lines.insert(insert_index, new_import)
                fixes.append(f'Added import: {new_import}')
            return ('\n'.join(lines), fixes)
        return (content, fixes)

    def _fix_generic_types(self, content: str, issue: Issue) -> tuple[str, list[str]]:
        return (content, [])

    def _infer_and_add_return_types(self, content: str, issue: Issue) -> tuple[str, list[str]]:
        fixes: list[str] = []
        message_lower = issue.message.lower()
        if not any((kw in message_lower for kw in ('missing return', 'return type', '->'))):
            return (content, fixes)
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return (content, fixes)
        lines = content.split('\n')
        modified_lines = lines.copy()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.returns is not None:
                    continue
                if issue.line_number and abs(node.lineno - issue.line_number) > 5:
                    continue
                inferred_type = self._infer_return_type_from_body(node, content)
                if inferred_type:
                    line_idx = node.lineno - 1
                    if 0 <= line_idx < len(modified_lines):
                        old_line = modified_lines[line_idx]
                        colon_pos = old_line.rfind(':')
                        if colon_pos > 0:
                            if old_line.rstrip().endswith(':'):
                                new_line = old_line[:colon_pos].rstrip() + f' -> {inferred_type}:'
                                if '\n' not in old_line[colon_pos + 1:]:
                                    modified_lines[line_idx] = new_line
                                    fixes.append(f"Inferred return type '{inferred_type}' for {node.name}() at line {node.lineno}")
        return ('\n'.join(modified_lines), fixes)

    def _infer_return_type_from_body(self, node: ast.FunctionDef | ast.AsyncFunctionDef, content: str) -> str | None:
        return_types: set[str] = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Return) and child.value:
                inferred = self._infer_type_from_expr(child.value)
                if inferred:
                    return_types.add(inferred)
            if isinstance(child, ast.Yield):
                if child.value:
                    inner_type = self._infer_type_from_expr(child.value)
                    return_types.add(f"Iterator[{inner_type or 'Any'}]")
                else:
                    return_types.add('Iterator[Any]')
            if isinstance(child, ast.YieldFrom):
                return_types.add('Iterator[Any]')
        if not return_types:
            return 'None'
        if len(return_types) == 1:
            return return_types.pop()
        return f"Union[{', '.join(sorted(return_types))}]"

    def _infer_type_from_expr(self, expr: ast.expr) -> str | None:
        handlers = {ast.Constant: self._infer_constant_type, ast.List: self._infer_list_type, ast.Dict: self._infer_dict_type, ast.Set: self._infer_set_type, ast.Tuple: self._infer_tuple_type, ast.Call: self._infer_call_type, ast.BinOp: self._infer_binop_type, ast.Compare: lambda e: 'bool', ast.BoolOp: lambda e: 'bool', ast.UnaryOp: self._infer_unaryop_type}
        handler = handlers.get(type(expr))
        return handler(expr) if handler else None  # type: ignore

    def _infer_constant_type(self, expr: ast.Constant) -> str:
        type_map = {type(None): 'None', bool: 'bool', int: 'int', float: 'float', str: 'str', bytes: 'bytes'}
        return type_map.get(type(expr.value), type(expr.value).__name__)

    def _infer_list_type(self, expr: ast.List) -> str:
        if expr.elts:
            inner_types = {self._infer_type_from_expr(e) or 'Any' for e in expr.elts}
            if len(inner_types) == 1:
                return f'list[{inner_types.pop()}]'
        return 'list[Any]'

    def _infer_dict_type(self, expr: ast.Dict) -> str:
        if expr.keys and expr.values:
            key_types = {self._infer_type_from_expr(k) or 'Any' for k in expr.keys if k}
            val_types = {self._infer_type_from_expr(v) or 'Any' for v in expr.values}
            kt = key_types.pop() if len(key_types) == 1 else 'Any'
            vt = val_types.pop() if len(val_types) == 1 else 'Any'
            return f'dict[{kt}, {vt}]'
        return 'dict[Any, Any]'

    def _infer_set_type(self, expr: ast.Set) -> str:
        if expr.elts:
            inner_types = {self._infer_type_from_expr(e) or 'Any' for e in expr.elts}
            if len(inner_types) == 1:
                return f'set[{inner_types.pop()}]'
        return 'set[Any]'

    def _infer_tuple_type(self, expr: ast.Tuple) -> str:
        if expr.elts:
            inner_types = [self._infer_type_from_expr(e) or 'Any' for e in expr.elts]
            return f"tuple[{', '.join(inner_types)}]"
        return 'tuple[()]'

    def _infer_call_type(self, expr: ast.Call) -> str | None:
        if isinstance(expr.func, ast.Name):
            factory_returns = {'list': 'list[Any]', 'dict': 'dict[Any, Any]', 'set': 'set[Any]', 'tuple': 'tuple[Any, ...]', 'str': 'str', 'int': 'int', 'float': 'float', 'bool': 'bool', 'frozenset': 'frozenset[Any]', 'range': 'range'}
            return factory_returns.get(expr.func.id)
        return None

    def _infer_binop_type(self, expr: ast.BinOp) -> str | None:
        left_type = self._infer_type_from_expr(expr.left)
        return left_type if left_type in ('str', 'int', 'float') else None

    def _infer_unaryop_type(self, expr: ast.UnaryOp) -> str | None:
        return 'bool' if isinstance(expr.op, ast.Not) else self._infer_type_from_expr(expr.operand)

    def _fix_complex_generic_types(self, content: str, issue: Issue) -> tuple[str, list[str]]:
        fixes: list[str] = []
        message_lower = issue.message.lower()
        if not any((kw in message_lower for kw in ('generic', 'subscript', 'type arguments', '['))):
            return (content, fixes)
        has_future_annotations = 'from __future__ import annotations' in content
        lines = content.split('\n')
        modified_lines = lines.copy()
        for i, line in enumerate(lines):
            if has_future_annotations:
                new_line = re.sub('\\bList\\[', 'list[', line)
                new_line = re.sub('\\bDict\\[', 'dict[', new_line)
                new_line = re.sub('\\bSet\\[', 'set[', new_line)
                new_line = re.sub('\\bTuple\\[', 'tuple[', new_line)
                new_line = re.sub('\\bFrozenSet\\[', 'frozenset[', new_line)
                if new_line != line:
                    modified_lines[i] = new_line
                    fixes.append(f'Modernized generic syntax on line {i + 1}')
        return ('\n'.join(modified_lines), fixes)

    def _detect_and_fix_protocol_patterns(self, content: str, issue: Issue) -> tuple[str, list[str]]:
        fixes: list[str] = []
        message_lower = issue.message.lower()
        if not any((kw in message_lower for kw in ('protocol', 'compatible', 'structural', 'duck'))):
            return (content, fixes)
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return (content, fixes)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                method_count = sum((1 for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))))
                attr_count = sum((1 for n in node.body if isinstance(n, ast.AnnAssign)))
                if method_count >= 2 and attr_count <= 1:
                    inherits_protocol = any((isinstance(base, ast.Name) and base.id == 'Protocol' or (isinstance(base, ast.Attribute) and base.attr == 'Protocol') for base in node.bases))
                    if not inherits_protocol and (not node.bases):
                        fixes.append(f"Class '{node.name}' may benefit from Protocol (structural subtyping) - has {method_count} methods")
        return (content, fixes)

    def _add_self_type_for_methods(self, content: str, issue: Issue) -> tuple[str, list[str]]:
        fixes: list[Any] = []  # type: ignore
        if not self._is_self_type_issue(issue.message):
            return (content, fixes)
        has_self_import = 'from typing import Self' in content
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return (content, fixes)
        lines = content.split('\n')
        modified_lines = lines.copy()
        needs_self_import = False
        class_names = self._collect_class_names(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                needs_self_import = self._process_class_methods(node, class_names, modified_lines, fixes, needs_self_import)
        if needs_self_import and (not has_self_import):
            self._add_self_import(modified_lines, fixes)
        return ('\n'.join(modified_lines), fixes)

    def _is_self_type_issue(self, message: str) -> bool:
        keywords = ('return type', 'self', 'instance', 'same type')
        return any((kw in message.lower() for kw in keywords))

    def _collect_class_names(self, tree: ast.AST) -> set[str]:
        return {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}

    def _process_class_methods(self, node: ast.ClassDef, class_names: set[str], lines: list[str], fixes: list[str], needs_import: bool) -> bool:
        class_name = node.name
        for item in node.body:
            if not isinstance(item, ast.FunctionDef):
                continue
            if self._should_skip_method(item):
                continue
            result = self._try_convert_to_self(item, class_name, lines)
            if result:
                lines[result['line_idx']] = result['new_line']
                fixes.append(f"Changed return type to 'Self' for {class_name}.{item.name}()")
                needs_import = True
        return needs_import

    def _should_skip_method(self, item: ast.FunctionDef) -> bool:
        if item.name.startswith('_') and (not item.name.startswith(('__enter__', '__exit__'))):
            return True
        return any((isinstance(d, ast.Name) and d.id == 'staticmethod' for d in item.decorator_list))

    def _try_convert_to_self(self, item: ast.FunctionDef, class_name: str, lines: list[str]) -> dict | None:
        if not item.returns:
            return None
        return_type = self._get_return_type_name(item.returns)
        if return_type != class_name:
            return None
        if isinstance(item.returns, ast.Name) and item.returns.id == 'Self':
            return None
        line_idx = item.lineno - 1
        if not 0 <= line_idx < len(lines):
            return None
        old_line = lines[line_idx]
        new_line = re.sub(f'\\b-> {class_name}\\b', '-> Self', old_line)
        if new_line == old_line:
            return None
        return {'line_idx': line_idx, 'new_line': new_line}

    def _get_return_type_name(self, returns: ast.expr) -> str | None:
        if isinstance(returns, ast.Name):
            return returns.id
        if isinstance(returns, ast.Constant):
            return str(returns.value)
        return None

    def _add_self_import(self, lines: list[str], fixes: list[str]) -> None:
        for i, line in enumerate(lines):
            if 'from typing import' in line and 'Self' not in line:
                lines[i] = re.sub('(from typing import [^\\n]+)', '\\1, Self', line)
                fixes.append('Added Self to typing imports')
                break

    def _fix_optional_union_types(self, content: str, issue: Issue) -> tuple[str, list[str]]:
        fixes: list[str] = []
        message_lower = issue.message.lower()
        if not any((kw in message_lower for kw in ('optional', 'union', 'none'))):
            return (content, fixes)
        has_future_annotations = 'from __future__ import annotations' in content
        if not has_future_annotations:
            return (content, fixes)
        lines = content.split('\n')
        modified_lines = lines.copy()
        for i, line in enumerate(lines):
            new_line = line
            optional_pattern = 'Optional\\[([^\\]]+(?:\\[[^\\]]*\\][^\\]]*)*)\\]'
            while re.search(optional_pattern, new_line):
                match = re.search(optional_pattern, new_line)
                if match:
                    inner_type = match.group(1)
                    new_line = new_line[:match.start()] + f'{inner_type} | None' + new_line[match.end():]
                    fixes.append(f'Converted Optional[{inner_type}] to {inner_type} | None on line {i + 1}')
            union_pattern = 'Union\\[([^\\]]+(?:\\[[^\\]]*\\][^\\]]*)*)\\]'
            while re.search(union_pattern, new_line):
                match = re.search(union_pattern, new_line)
                if match:
                    inner = match.group(1)
                    types = self._split_union_types(inner)
                    if 2 <= len(types) <= 5:
                        union_syntax = ' | '.join((t.strip() for t in types))
                        new_line = new_line[:match.start()] + union_syntax + new_line[match.end():]
                        fixes.append(f'Converted Union[{inner}] to {union_syntax} on line {i + 1}')
                    else:
                        break
            if new_line != line:
                modified_lines[i] = new_line
        return ('\n'.join(modified_lines), fixes)

    def _split_union_types(self, inner: str) -> list[str]:
        types = []
        current = ''
        depth = 0
        for char in inner:
            if char == '[':
                depth += 1
                current += char
            elif char == ']':
                depth -= 1
                current += char
            elif char == ',' and depth == 0:
                if current.strip():
                    types.append(current.strip())
                current = ''
            else:
                current += char
        if current.strip():
            types.append(current.strip())
        return types
from .base import agent_registry
agent_registry.register(TypeErrorSpecialistAgent)