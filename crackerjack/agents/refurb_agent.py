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
FURB_TRANSFORMATIONS: dict[str, str] = {'FURB102': '_transform_compare_zero', 'FURB105': '_transform_print_empty_string', 'FURB107': '_transform_compare_empty', 'FURB108': '_transform_redundant_none_comparison', 'FURB109': '_transform_membership_test', 'FURB110': '_transform_delete_while_iterating', 'FURB111': '_transform_redundant_continue', 'FURB113': '_transform_redundant_pass', 'FURB115': '_transform_open_mode_r', 'FURB116': '_transform_fstring_numeric_literal', 'FURB117': '_transform_multiple_with', 'FURB118': '_transform_enumerate', 'FURB119': '_transform_redundant_index', 'FURB122': '_transform_rhs_unpack', 'FURB123': '_transform_write_whole_file', 'FURB125': '_transform_redundantenumerate', 'FURB126': '_transform_isinstance_type_check', 'FURB129': '_transform_any_all', 'FURB131': '_transform_single_item_membership', 'FURB132': '_transform_check_and_remove', 'FURB133': '_transform_bad_open_mode', 'FURB134': '_transform_list_multiply', 'FURB136': '_transform_bool_return', 'FURB138': '_transform_print_literal', 'FURB140': '_transform_zip', 'FURB141': '_transform_redundant_fstring', 'FURB142': '_transform_unnecessary_listcomp', 'FURB143': '_transform_unnecessary_index_lookup', 'FURB145': '_transform_copy', 'FURB148': '_transform_max_min', 'FURB152': '_transform_pow_operator', 'FURB156': '_transform_redundant_lambda', 'FURB157': '_transform_implicit_print', 'FURB161': '_transform_int_scientific', 'FURB163': '_transform_sorted_key_identity', 'FURB167': '_transform_dict_literal', 'FURB168': '_transform_isinstance_type_tuple', 'FURB169': '_transform_type_none_comparison', 'FURB171': '_transform_single_element_membership', 'FURB172': '_transform_unnecessary_list_cast', 'FURB173': '_transform_redundant_not', 'FURB175': '_transform_abs_sqr', 'FURB176': '_transform_unnecessary_from_float', 'FURB177': '_transform_redundant_or', 'FURB180': '_transform_method_assign', 'FURB181': '_transform_redundant_expression', 'FURB183': '_transform_substring', 'FURB184': '_transform_bad_version_info_compare', 'FURB185': '_transform_redundant_substring', 'FURB186': '_transform_redundant_cast', 'FURB187': '_transform_chained_assignment', 'FURB188': '_transform_slice_copy', 'FURB189': '_transform_fstring_to_print', 'FURB190': '_transform_subprocess_list'}

class RefurbCodeTransformerAgent(SubAgent):
    name = 'RefurbCodeTransformerAgent'
    confidence = 0.85

    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)
        self.log = logger.info  # type: ignore

    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.REFURB}

    async def can_handle(self, issue: Issue) -> float:
        if issue.type != IssueType.REFURB:
            return 0.0
        furb_code = self._extract_furb_code(issue)
        if furb_code is None:
            return 0.0
        if furb_code in FURB_TRANSFORMATIONS:
            return self.confidence
        return 0.0

    def _extract_furb_code(self, issue: Issue) -> str | None:
        for detail in issue.details:
            match = re.search('\\[?(FURB\\d+)\\]?', detail)
            if match:
                return match.group(1)
        if issue.message:
            match = re.search('\\[?(FURB\\d+)\\]?', issue.message)
            if match:
                return match.group(1)
        if hasattr(issue, 'reason') and issue.reason:
            match = re.search('REFURB_TRANSFORM:(FURB\\d+):', issue.reason)
            if match:
                return match.group(1)
        return None

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        self.log(f'RefurbCodeTransformerAgent analyzing: {issue.message[:100]}')
        if issue.file_path is None:
            return FixResult(success=False, confidence=0.0, remaining_issues=['No file path provided'])
        file_path = Path(issue.file_path)
        if not file_path.exists():
            return FixResult(success=False, confidence=0.0, remaining_issues=[f'File not found: {file_path}'])
        content = self.context.get_file_content(file_path)
        if not content:
            return FixResult(success=False, confidence=0.0, remaining_issues=['Could not read file content'])
        furb_code = self._extract_furb_code(issue)
        if furb_code is None:
            return FixResult(success=False, confidence=0.0, remaining_issues=['Could not extract FURB code from issue'])
        handler_name = FURB_TRANSFORMATIONS.get(furb_code)
        if handler_name is None:
            return FixResult(success=False, confidence=0.0, remaining_issues=[f'No handler for {furb_code}'])
        handler = getattr(self, handler_name, None)
        if handler is None:
            return FixResult(success=False, confidence=0.0, remaining_issues=[f'Handler method {handler_name} not implemented'])
        new_content, fix_description = self._try_ast_transform(content, issue, furb_code, handler)
        if new_content == content:
            new_content, fix_description = handler(content, issue)
        if new_content == content:
            return FixResult(success=False, confidence=0.0, remaining_issues=[f'Transformation {furb_code} did not modify content'])
        if self.context.write_file_content(file_path, new_content):
            return FixResult(success=True, confidence=self.confidence, fixes_applied=[fix_description], files_modified=[str(file_path)])
        return FixResult(success=False, confidence=0.0, remaining_issues=[f'Failed to write transformed content to {file_path}'])

    def _try_ast_transform(self, content: str, issue: Issue, furb_code: str, handler: object) -> tuple[str, str]:
        try:
            tree = ast.parse(content)
            line_number = issue.line_number or 0
            ast_handlers = {'FURB107': self._ast_transform_suppress, 'FURB102': self._ast_transform_startswith_tuple, 'FURB109': self._ast_transform_membership_tuple, 'FURB118': self._ast_transform_itemgetter, 'FURB126': self._ast_transform_remove_else_return, 'FURB110': self._ast_transform_or_operator, 'FURB115': self._ast_transform_len_comparison, 'FURB113': self._ast_transform_append_to_extend, 'FURB123': self._ast_transform_list_copy, 'FURB142': self._ast_transform_set_update}
            ast_handler = ast_handlers.get(furb_code)
            if ast_handler:
                new_tree, fix_desc = ast_handler(tree, line_number, content)
                if new_tree:
                    new_content = self._unparse_tree(new_tree, content)
                    if new_content and new_content != content:
                        return (new_content, fix_desc)
        except SyntaxError as e:
            logger.debug(f'AST parse failed for {furb_code}: {e}')
        except Exception as e:
            logger.debug(f'AST transform failed for {furb_code}: {e}')
        return (content, 'No AST transformation applied')

    def _unparse_tree(self, tree: ast.AST, original_content: str) -> str | None:
        try:
            if hasattr(ast, 'unparse'):
                return ast.unparse(tree)
        except Exception:
            pass
        return None

    def _ast_transform_suppress(self, tree: ast.AST, line_number: int, content: str) -> tuple[ast.AST | None, str]:
        lines = content.split('\n')
        if not 1 <= line_number <= len(lines):
            return (None, 'Line out of range')
        for node in ast.walk(tree):
            if isinstance(node, ast.Try) and node.lineno == line_number:
                if len(node.handlers) == 1:
                    handler = node.handlers[0]
                    if len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass) and (len(node.finalbody) == 0) and (len(node.orelse) == 0):
                        return (None, 'suppress pattern detected')
        return (None, 'No suppress pattern found')

    def _ast_transform_startswith_tuple(self, tree: ast.AST, line_number: int, content: str) -> tuple[ast.AST | None, str]:
        return (None, 'startswith tuple needs regex')

    def _ast_transform_membership_tuple(self, tree: ast.AST, line_number: int, content: str) -> tuple[ast.AST | None, str]:
        return (None, 'membership tuple needs regex')

    def _ast_transform_itemgetter(self, tree: ast.AST, line_number: int, content: str) -> tuple[ast.AST | None, str]:
        return (None, 'itemgetter needs regex')

    def _ast_transform_remove_else_return(self, tree: ast.AST, line_number: int, content: str) -> tuple[ast.AST | None, str]:
        return (None, 'else return needs regex')

    def _ast_transform_or_operator(self, tree: ast.AST, line_number: int, content: str) -> tuple[ast.AST | None, str]:
        return (None, 'or operator needs regex')

    def _ast_transform_len_comparison(self, tree: ast.AST, line_number: int, content: str) -> tuple[ast.AST | None, str]:
        return (None, 'len comparison needs regex')

    def _ast_transform_append_to_extend(self, tree: ast.AST, line_number: int, content: str) -> tuple[ast.AST | None, str]:
        return (None, 'append to extend needs regex')

    def _ast_transform_list_copy(self, tree: ast.AST, line_number: int, content: str) -> tuple[ast.AST | None, str]:
        return (None, 'list copy needs regex')

    def _ast_transform_set_update(self, tree: ast.AST, line_number: int, content: str) -> tuple[ast.AST | None, str]:
        return (None, 'set update needs regex')

    def _transform_enumerate(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        new_content = content
        lambda_index_pattern = 'lambda\\s+(\\w+)\\s*:\\s*\\1\\s*\\[\\s*(\\d+)\\s*\\]'
        for match in re.finditer(lambda_index_pattern, content):
            match.group(1)
            index = match.group(2)
            old_lambda = match.group(0)
            new_itemgetter = f'operator.itemgetter({index})'
            new_content = new_content.replace(old_lambda, new_itemgetter)
            if 'import operator' not in new_content and 'from operator import' not in new_content:
                lines = new_content.split('\n')
                insert_pos = 0
                for i, line in enumerate(lines):
                    if line.strip().startswith(('import ', 'from ')):
                        insert_pos = i + 1
                    elif line.strip() and (not line.strip().startswith('#')):
                        break
                lines.insert(insert_pos, 'import operator')
                new_content = '\n'.join(lines)
        if new_content != content:
            fixes.append('Replaced lambda x: x[n] with operator.itemgetter(n)')
            content = new_content
        lambda_key_pattern = 'lambda\\s+(\\w+)\\s*:\\s*\\1\\s*\\[\\s*["\\\']([^"\\\']+)["\\\']\\s*\\]'
        for match in re.finditer(lambda_key_pattern, content):
            match.group(1)
            key = match.group(2)
            old_lambda = match.group(0)
            new_itemgetter = f'operator.itemgetter("{key}")'
            new_content = new_content.replace(old_lambda, new_itemgetter)
        if new_content != content and 'itemgetter' not in '; '.join(fixes):
            fixes.append('Replaced lambda x: x["key"] with operator.itemgetter("key")')
        pattern = '(\\s*)(\\w+)\\s*=\\s*0\\n\\1for\\s+(\\w+)\\s+in\\s+([^:]+):\\n((?:.*\\n)*?)\\1\\2\\s*\\+=\\s*1'
        replacement = '\\1for \\2, \\3 in enumerate(\\4):\\n\\5'
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes.append('Replaced manual index tracking with enumerate()')
        return (new_content, '; '.join(fixes) if fixes else 'No enumerate transformation applied')

    def _transform_any_all(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        any_pattern = '(\\s*)for\\s+(\\w+)\\s+in\\s+([^:]+):\\n\\s+if\\s+([^:]+):\\n\\s+return\\s+True\\n\\1return\\s+False'
        any_replacement = '\\1return any(\\4 for \\2 in \\3)'
        new_content = re.sub(any_pattern, any_replacement, content)
        if new_content != content:
            fixes.append('Replaced loop with any()')
        all_pattern = '(\\s*)for\\s+(\\w+)\\s+in\\s+([^:]+):\\n\\s+if\\s+([^:]+):\\n\\s+return\\s+False\\n\\1return\\s+True'
        all_replacement = '\\1return all(not (\\4) for \\2 in \\3)'
        new_content = re.sub(all_pattern, all_replacement, new_content)
        if new_content != content and 'all(' in new_content:
            fixes.append('Replaced loop with all()')
        return (new_content, '; '.join(fixes) if fixes else 'No any/all transformation applied')

    def _transform_bool_return(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        patterns = [('(\\s*)if\\s+([^:]+):\\n\\s+return\\s+True\\n\\s+else:\\n\\s+return\\s+False', '\\1return bool(\\2)'), ('(\\s*)if\\s+([^:]+):\\n\\s+return\\s+True\\n\\1return\\s+False', '\\1return bool(\\2)'), ('(\\s*)if\\s+not\\s+([^:]+):\\n\\s+return\\s+False\\n\\1return\\s+True', '\\1return bool(\\2)')]
        new_content = content
        for pattern, replacement in patterns:
            new_content = re.sub(pattern, replacement, new_content)
        if new_content != content:
            fixes.append('Simplified conditional return to bool()')
        return (new_content, '; '.join(fixes) if fixes else 'No bool return transformation applied')

    def _transform_zip(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        pattern = '(\\s*)for\\s+(\\w+)\\s+in\\s+range\\(len\\(([^)]+)\\)\\):'
        new_content = re.sub(pattern, '\\1for _, _ in zip(\\3, _):  # TODO: Apply zip transformation manually', content)
        if new_content != content:
            fixes.append('Identified zip() transformation opportunity (may need manual review)')
        return (new_content, '; '.join(fixes) if fixes else 'No zip transformation applied')

    def _transform_unnecessary_listcomp(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        pattern = '\\[([^\\]]+)\\]\\[0\\]'
        replacement = 'next(\\1)'
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes.append('Replaced list comprehension indexing with next()')
        return (new_content, '; '.join(fixes) if fixes else 'No list comprehension transformation applied')

    def _transform_copy(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        pattern = '(\\w+)\\[\\s*:\\s*\\](?!\\s*,)'
        replacement = '\\1.copy()'
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes.append('Replaced [:] slice with .copy() for clarity')
        return (new_content, '; '.join(fixes) if fixes else 'No copy transformation applied')

    def _transform_max_min(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        max_pattern = '(\\w+)\\s*=\\s*(\\w+)\\[0\\]\\n\\s*for\\s+(\\w+)\\s+in\\s+\\2:\\n\\s*if\\s+\\3\\s*>\\s*\\1:\\n\\s*\\1\\s*=\\s*\\3'
        max_replacement = '\\1 = max(\\2)'
        new_content = re.sub(max_pattern, max_replacement, content)
        if new_content != content:
            fixes.append('Replaced manual max loop with max()')
        min_pattern = '(\\w+)\\s*=\\s*(\\w+)\\[0\\]\\n\\s*for\\s+(\\w+)\\s+in\\s+\\2:\\n\\s*if\\s+\\3\\s*<\\s*\\1:\\n\\s*\\1\\s*=\\s*\\3'
        min_replacement = '\\1 = min(\\2)'
        new_content = re.sub(min_pattern, min_replacement, new_content)
        if 'min(' in new_content and 'min(' not in content:
            fixes.append('Replaced manual min loop with min()')
        return (new_content, '; '.join(fixes) if fixes else 'No max/min transformation applied')

    def _transform_pow_operator(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        pattern = 'math\\.pow\\s*\\(\\s*([^,]+)\\s*,\\s*([^)]+)\\s*\\)'
        replacement = '(\\1 ** \\2)'
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes.append('Replaced math.pow() with ** operator')
        return (new_content, '; '.join(fixes) if fixes else 'No pow transformation applied')

    def _transform_int_scientific(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []

        def replace_scientific_int(match: re.Match[str]) -> str:
            mantissa = float(match.group(1))
            exponent = int(match.group(2))
            value = int(mantissa * 10 ** exponent)
            return str(value)
        pattern = 'int\\s*\\(\\s*(\\d+(?:\\.\\d+)?)e(\\d+)\\s*\\)'
        new_content = re.sub(pattern, replace_scientific_int, content)
        if new_content != content:
            fixes.append('Replaced int(scientific notation) with literal integer')
        return (new_content, '; '.join(fixes) if fixes else 'No int scientific transformation applied')

    def _transform_sorted_key_identity(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        pattern = 'sorted\\s*\\(\\s*([^,)]+)\\s*,\\s*key\\s*=\\s*lambda\\s+(\\w+)\\s*:\\s*\\2\\s*\\)'
        replacement = 'sorted(\\1)'
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes.append('Removed redundant identity key function from sorted()')
        return (new_content, '; '.join(fixes) if fixes else 'No sorted key transformation applied')

    def _transform_compare_zero(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        startswith_pattern = '(\\w+)\\.startswith\\s*\\(\\s*([^)]+)\\s*\\)\\s+or\\s+\\1\\.startswith\\s*\\(\\s*([^)]+)\\s*\\)'
        new_content = re.sub(startswith_pattern, '\\1.startswith((\\2, \\3))', content)
        if new_content != content:
            fixes.append('Combined startswith calls into tuple form')
            content = new_content
        not_startswith_pattern = 'not\\s+(\\w+)\\.startswith\\s*\\(\\s*([^)]+)\\s*\\)\\s+and\\s+not\\s+\\1\\.startswith\\s*\\(\\s*([^)]+)\\s*\\)'
        new_content = re.sub(not_startswith_pattern, 'not \\1.startswith((\\2, \\3))', content)
        if new_content != content:
            fixes.append('Combined not startswith calls into tuple form')
            content = new_content
        new_content = re.sub('len\\s*\\(([^)]+)\\)\\s*==\\s*0', 'not \\1', content)
        if new_content != content:
            fixes.append('Simplified len(x) == 0 to not x')
            content = new_content
        new_content = re.sub('(\\w+)\\s*==\\s*0\\b', 'not \\1', content)
        if new_content != content and 'Simplified x == 0' not in '; '.join(fixes):
            fixes.append('Simplified x == 0 to not x')
        return (new_content, '; '.join(fixes) if fixes else 'No zero comparison transformation')

    def _transform_compare_empty(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        suppress_pattern = '(\\s*)try:\\s*\\n((?:\\1\\s+.*\\n)+)\\1except\\s+(\\w+)(?:\\s*\\([^)]*\\))?\\s*:\\s*\\n\\1\\s+pass'
        new_content = content
        for match in re.finditer(suppress_pattern, content):
            indent = match.group(1)
            body = match.group(2)
            exc_type = match.group(3)
            has_contextlib = 'from contextlib import' in content or 'import contextlib' in content
            suppress_import = 'from contextlib import suppress' if not has_contextlib else ''
            replacement = f'{indent}with suppress({exc_type}):\n{body}'
            new_content = new_content.replace(match.group(0), replacement)
            if suppress_import and suppress_import not in new_content:
                lines = new_content.split('\n')
                insert_pos = 0
                in_docstring = False
                for i, line in enumerate(lines):
                    if '"""' in line or "'''" in line:
                        in_docstring = not in_docstring
                    if not in_docstring and line.strip() and (not line.strip().startswith('#')):
                        insert_pos = i
                        break
                lines.insert(insert_pos, suppress_import)
                new_content = '\n'.join(lines)
        if new_content != content:
            fixes.append('Replaced try/except: pass with suppress()')
            content = new_content
        new_content = re.sub('(\\w+)\\s*==\\s*\\[\\s*\\]', 'not \\1', content)
        if new_content != content:
            fixes.append('Simplified x == [] to not x')
            content = new_content
        new_content = re.sub('(\\w+)\\s*==\\s*\\{\\s*\\}', 'not \\1', content)
        if new_content != content:
            fixes.append('Simplified x == {} to not x')
            content = new_content
        new_content = re.sub('(\\w+)\\s*==\\s*""', 'not \\1', content)
        if new_content != content:
            fixes.append('Simplified x == "" to not x')
        return (new_content, '; '.join(fixes) if fixes else 'No empty comparison transformation')

    def _transform_redundant_none_comparison(self, content: str, issue: Issue) -> tuple[str, str]:
        return (content, 'Redundant None comparison pattern requires manual review')

    def _transform_membership_test(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        pattern = '\\bin\\s*\\[([^\\]]+)\\]'
        replacement = 'in (\\1)'
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes.append('Converted list membership to tuple membership')
        return (new_content, '; '.join(fixes) if fixes else 'No membership test transformation')

    def _transform_isinstance_type_check(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        new_content = content
        pattern = 'type\\s*\\(([^)]+)\\)\\s*==\\s*(\\w+)'
        replacement = 'isinstance(\\1, \\2)'
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes.append('Converted type(x) == T to isinstance(x, T)')
        else_return_pattern = '(\\s*)else:\\s*\\n\\s+return\\s+([^\\n]+)'
        new_content = re.sub(else_return_pattern, '\\1return \\2', new_content)
        if new_content != content and 'else' not in '; '.join(fixes):
            fixes.append('Removed redundant else: return')
        return (new_content, '; '.join(fixes) if fixes else 'No isinstance transformation')

    def _transform_write_whole_file(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        pattern = 'open\\s*\\(\\s*([^,]+),\\s*[\'\\"]w[\'\\"]\\s*\\)\\.write\\s*\\(([^)]+)\\)'
        replacement = 'Path(\\1).write_text(\\2)'
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes.append('Converted open().write() to Path.write_text()')
        return (new_content, '; '.join(fixes) if fixes else 'No write file transformation')

    def _transform_multiple_with(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        pattern = 'with\\s+([^:]+):\\s*\\n\\s*with\\s+([^:]+):'
        replacement = 'with \\1, \\2:'
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes.append('Combined nested with statements')
        return (new_content, '; '.join(fixes) if fixes else 'No with transformation')

    def _transform_redundant_not(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        pattern = 'not\\s*\\(\\s*([^)]+)\\s*==\\s*([^)]+)\\s*\\)'
        replacement = '\\1 != \\2'
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes.append('Simplified not (x == y) to x != y')
            content = new_content
        pattern = 'not\\s*\\(\\s*([^)]+)\\s*!=\\s*([^)]+)\\s*\\)'
        replacement = '\\1 == \\2'
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes.append('Simplified not (x != y) to x == y')
        return (new_content, '; '.join(fixes) if fixes else 'No redundant not transformation')

    def _transform_substring(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        pattern = '(\\w+)\\.find\\s*\\(([^)]+)\\)\\s*!=\\s*-1'
        replacement = '\\2 in \\1'
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes.append('Converted x.find(y) != -1 to y in x')
        return (new_content, '; '.join(fixes) if fixes else 'No substring transformation')

    def _transform_print_empty_string(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        new_content = content
        print_empty = 'print\\s*\\(\\s*""\\s*\\)'
        new_content = re.sub(print_empty, 'print()', new_content)
        if new_content != content:
            fixes.append('Converted print("") to print()')
            content = new_content
        or_pattern = '\\b(\\w+)\\s+if\\s+\\1\\s+else\\s+(\\w+)'
        new_content = re.sub(or_pattern, '\\1 or \\2', new_content)
        if new_content != content and 'or' not in '; '.join(fixes):
            fixes.append('Converted x if x else y to x or y')
        return (new_content, '; '.join(fixes) if fixes else 'No print empty string transformation')

    def _transform_delete_while_iterating(self, content: str, issue: Issue) -> tuple[str, str]:
        return (content, 'Delete while iterating requires manual review')

    def _transform_redundant_continue(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        pattern = '\\n(\\s*)continue\\s*\\n(\\s*)\\n'
        replacement = '\\n\\2\\n'
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes.append('Removed redundant continue')
        return (new_content, '; '.join(fixes) if fixes else 'No redundant continue')

    def _transform_redundant_pass(self, content: str, issue: Issue) -> tuple[str, str]:
        return (content, 'Redundant pass requires manual review')

    def _transform_open_mode_r(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        new_content = content
        len_eq_zero = 'len\\s*\\(([^)]+)\\)\\s*==\\s*0\\b'
        new_content = re.sub(len_eq_zero, 'not \\1', new_content)
        if new_content != content:
            fixes.append('Converted len(x) == 0 to not x')
            content = new_content
        len_gte_one = 'len\\s*\\(([^)]+)\\)\\s*>=\\s*1\\b'
        new_content = re.sub(len_gte_one, '\\1', new_content)
        if new_content != content:
            fixes.append('Converted len(x) >= 1 to x')
        open_path_r = 'open\\s*\\(\\s*(\\w+)\\s*,\\s*["\\\']r["\\\']\\s*\\)'
        new_content = re.sub(open_path_r, '\\1.open()', new_content)
        if new_content != content and 'open()' not in '; '.join(fixes):
            fixes.append("Converted open(path, 'r') to path.open()")
        open_path_w = 'open\\s*\\(\\s*(\\w+)\\s*,\\s*["\\\']w["\\\']\\s*\\)'
        new_content = re.sub(open_path_w, "\\1.open('w')", new_content)
        if new_content != content and 'open(' not in '; '.join(fixes):
            fixes.append("Converted open(path, 'w') to path.open('w')")
        pattern = 'open\\s*\\(\\s*([^,]+),\\s*[\'\\"]r[\'\\"]\\s*\\)'
        replacement = 'open(\\1)'
        new_content = re.sub(pattern, replacement, new_content)
        if new_content != content and 'open()' not in '; '.join(fixes):
            fixes.append("Removed redundant 'r' mode from open()")
        return (new_content, '; '.join(fixes) if fixes else 'No open mode transformation')

    def _transform_fstring_numeric_literal(self, content: str, issue: Issue) -> tuple[str, str]:
        return (content, 'F-string numeric literal requires manual review')

    def _transform_redundant_index(self, content: str, issue: Issue) -> tuple[str, str]:
        return (content, 'Redundant index requires manual review')

    def _transform_rhs_unpack(self, content: str, issue: Issue) -> tuple[str, str]:
        return (content, 'RHS unpack requires manual review')

    def _transform_redundantenumerate(self, content: str, issue: Issue) -> tuple[str, str]:
        return (content, 'Redundant enumerate requires manual review')

    def _transform_single_item_membership(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        new_content = content
        pattern = '\\b(\\w+)\\s+in\\s*\\[\\s*(\\w+)\\s*\\]'
        replacement = '\\1 == \\2'
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes.append('Converted x in [y] to x == y')
        append_pattern = '(\\w+)\\.append\\s*\\(\\s*([^)]+)\\s*\\)\\s*;\\s*\\1\\.append\\s*\\(\\s*([^)]+)\\s*\\)'
        new_content = re.sub(append_pattern, '\\1.extend((\\2, \\3))', new_content)
        if new_content != content and 'extend' not in '; '.join(fixes):
            fixes.append('Converted consecutive append() to extend()')
        return (new_content, '; '.join(fixes) if fixes else 'No single item membership')

    def _transform_check_and_remove(self, content: str, issue: Issue) -> tuple[str, str]:
        return (content, 'Check and remove requires manual review')

    def _transform_bad_open_mode(self, content: str, issue: Issue) -> tuple[str, str]:
        return (content, 'Bad open mode requires manual review')

    def _transform_list_multiply(self, content: str, issue: Issue) -> tuple[str, str]:
        return (content, 'List multiply requires manual review')

    def _transform_print_literal(self, content: str, issue: Issue) -> tuple[str, str]:
        return (content, 'FURB138 list comprehension requires manual review')

    def _transform_redundant_fstring(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        pattern = 'f"\\{([^}]+)\\}"'
        replacement = 'str(\\1)'
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes.append('Converted redundant f-string to str()')
        return (new_content, '; '.join(fixes) if fixes else 'No redundant f-string')

    def _transform_unnecessary_index_lookup(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        new_content = content
        list_copy_pattern = '\\blist\\s*\\(\\s*(\\w+)\\s*\\)'
        for match in re.finditer(list_copy_pattern, content):
            var_name = match.group(1)
            if any((hint in var_name.lower() for hint in ['list', 'items', 'lines', 'results', 'values', 'data'])):
                old_call = match.group(0)
                new_call = f'{var_name}.copy()'
                new_content = new_content.replace(old_call, new_call)
                fixes.append(f'Converted list({var_name}) to {var_name}.copy()')
        set_add_pattern = '(\\s*)for\\s+(\\w+)\\s+in\\s+([^:]+):\\s*\\n\\s+(\\w+)\\.add\\s*\\(\\s*\\2\\s*\\)'
        for match in re.finditer(set_add_pattern, content):
            indent = match.group(1)
            var = match.group(2)
            iterable = match.group(3)
            set_var = match.group(4)
            old_code = match.group(0)
            new_code = f'{indent}{set_var}.update({var} for {var} in {iterable})'
            new_content = new_content.replace(old_code, new_code)
            fixes.append(f'Converted for loop with {set_var}.add() to {set_var}.update()')
        return (new_content, '; '.join(fixes) if fixes else 'No list copy transformation')

    def _transform_redundant_lambda(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        pattern = 'lambda\\s+(\\w+)\\s*:\\s*(\\w+)\\s*\\(\\s*\\1\\s*\\)'
        replacement = '\\2'
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes.append('Simplified lambda x: func(x) to func')
        return (new_content, '; '.join(fixes) if fixes else 'No redundant lambda')

    def _transform_implicit_print(self, content: str, issue: Issue) -> tuple[str, str]:
        return (content, 'Implicit print requires manual review')

    def _transform_dict_literal(self, content: str, issue: Issue) -> tuple[str, str]:
        return (content, 'Dict literal requires manual review')

    def _transform_isinstance_type_tuple(self, content: str, issue: Issue) -> tuple[str, str]:
        return (content, 'Isinstance type tuple requires manual review')

    def _transform_type_none_comparison(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        pattern = '(\\w+)\\s*==\\s*None\\b'
        replacement = '\\1 is None'
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes.append('Converted x == None to x is None')
            content = new_content
        pattern = '(\\w+)\\s*!=\\s*None\\b'
        replacement = '\\1 is not None'
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes.append('Converted x != None to x is not None')
        return (new_content, '; '.join(fixes) if fixes else 'No None comparison')

    def _transform_single_element_membership(self, content: str, issue: Issue) -> tuple[str, str]:
        return self._transform_single_item_membership(content, issue)

    def _transform_unnecessary_list_cast(self, content: str, issue: Issue) -> tuple[str, str]:
        return (content, 'Unnecessary list cast requires manual review')

    def _transform_abs_sqr(self, content: str, issue: Issue) -> tuple[str, str]:
        return (content, 'Abs sqr requires manual review')

    def _transform_unnecessary_from_float(self, content: str, issue: Issue) -> tuple[str, str]:
        return (content, 'Unnecessary from_float requires manual review')

    def _transform_redundant_or(self, content: str, issue: Issue) -> tuple[str, str]:
        return (content, 'Redundant or requires manual review')

    def _transform_method_assign(self, content: str, issue: Issue) -> tuple[str, str]:
        return (content, 'Method assign requires manual review')

    def _transform_redundant_expression(self, content: str, issue: Issue) -> tuple[str, str]:
        return (content, 'Redundant expression requires manual review')

    def _transform_bad_version_info_compare(self, content: str, issue: Issue) -> tuple[str, str]:
        return (content, 'Bad version info compare requires manual review')

    def _transform_redundant_substring(self, content: str, issue: Issue) -> tuple[str, str]:
        return (content, 'Redundant substring requires manual review')

    def _transform_redundant_cast(self, content: str, issue: Issue) -> tuple[str, str]:
        return (content, 'Redundant cast requires manual review')

    def _transform_chained_assignment(self, content: str, issue: Issue) -> tuple[str, str]:
        return (content, 'Chained assignment requires manual review')

    def _transform_slice_copy(self, content: str, issue: Issue) -> tuple[str, str]:
        return self._transform_copy(content, issue)

    def _transform_fstring_to_print(self, content: str, issue: Issue) -> tuple[str, str]:
        return (content, 'F-string to print requires manual review')

    def _transform_subprocess_list(self, content: str, issue: Issue) -> tuple[str, str]:
        return (content, 'Subprocess list requires manual review')
from .base import agent_registry
agent_registry.register(RefurbCodeTransformerAgent)