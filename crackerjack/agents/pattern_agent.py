import ast
from pathlib import Path

from .base import FixResult, Issue, IssueType, SubAgent, agent_registry


class PatternAgent(SubAgent):
    def __init__(self, context) -> None:
        super().__init__(context)
        self.name = "PatternAgent"

    def get_supported_types(self) -> set[IssueType]:
        return {
            IssueType.COMPLEXITY,
        }

    async def can_handle(self, issue: Issue) -> float:
        message = issue.message.lower()

        if "furb107" in message:
            return 0.95

        if "furb115" in message:
            return 0.95

        if "furb104" in message:
            return 0.95

        if "furb111" in message and "lambda" in message:
            return 0.95

        if "furb135" in message and "key is unused" in message:
            return 0.9

        if issue.type == IssueType.COMPLEXITY:
            return 0.6

        return 0.0

    def _fix_try_except_pass_ast(self, tree: ast.AST) -> ast.AST:

        class TryExceptPassTransformer(ast.NodeTransformer):
            def visit_Try(self, node: ast.Try) -> ast.With | ast.Try:

                if (
                    len(node.handlers) == 1
                    and isinstance(node.handlers[0].type, ast.Name)
                    and node.handlers[0].type.id == "Exception"
                    and not node.handlers[0].name
                ):
                    handler_body = node.handlers[0].body
                    if not handler_body or (
                        len(handler_body) == 1 and isinstance(handler_body[0], ast.Pass)
                    ):
                        suppress_call = ast.Call(
                            func=ast.Name(id="suppress", ctx=ast.Load()),
                            args=[ast.Name(id="Exception", ctx=ast.Load())],
                            keywords=[],
                        )
                        with_item = ast.withitem(
                            context_expr=suppress_call,
                            optional_vars=None,
                        )
                        return ast.With(
                            items=[with_item],
                            body=node.body,
                            type_comment=None,
                        )

                return node

        transformer = TryExceptPassTransformer()
        return ast.fix_missing_locations(transformer.visit(tree))

    def _fix_len_check_ast(self, tree: ast.AST) -> ast.AST:

        class LenCheckTransformer(ast.NodeTransformer):
            def visit_Compare(self, node: ast.Compare) -> ast.expr:

                if (
                    len(node.ops) == 1
                    and isinstance(node.ops[0], ast.Gt)
                    and isinstance(node.left, ast.Call)
                    and isinstance(node.left.func, ast.Name)
                    and node.left.func.id == "len"
                    and len(node.comparators) == 1
                    and isinstance(node.comparators[0], ast.Constant)
                ):
                    comparator = node.comparators[0]
                    if comparator.value == 0:
                        if len(node.left.args) == 1:
                            return node.left.args[0]

                return node

        transformer = LenCheckTransformer()
        return ast.fix_missing_locations(transformer.visit(tree))

    def _fix_os_getcwd_ast(self, tree: ast.AST) -> ast.AST:

        class OsGetcwdTransformer(ast.NodeTransformer):
            def visit_Call(self, node: ast.Call) -> ast.Call | None:

                if (
                    isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "os"
                    and node.func.attr == "getcwd"
                    and not node.args
                ):
                    return ast.Call(
                        func=ast.Attribute(
                            value=ast.Name(id="Path", ctx=ast.Load()),
                            attr="cwd",
                            ctx=ast.Load(),
                        ),
                        args=[],
                        keywords=[],
                    )

                return node

        transformer = OsGetcwdTransformer()
        return ast.fix_missing_locations(transformer.visit(tree))

    def _fix_unnecessary_lambda_ast(self, tree: ast.AST) -> ast.AST:

        class LambdaWrapperTransformer(ast.NodeTransformer):
            def visit_Call(self, node: ast.Call) -> ast.Call | None:

                for i, arg in enumerate(node.args):
                    if (
                        isinstance(arg, ast.Lambda)
                        and not arg.args.args
                    ):
                        lambda_body = arg.body


                        if (
                            isinstance(lambda_body, ast.Call)
                            and not lambda_body.args
                            and not lambda_body.keywords
                        ):

                            new_args = list(node.args)
                            new_args[i] = lambda_body

                            return ast.Call(
                                func=node.func,
                                args=new_args,
                                keywords=node.keywords,
                            )

                return node

        transformer = LambdaWrapperTransformer()
        return ast.fix_missing_locations(transformer.visit(tree))

    def _ensure_pathlib_import(self, content: str) -> str:
        if (
            "from pathlib import Path" not in content
            and "import pathlib" not in content
        ):
            lines = content.split("\n")

            for i, line in enumerate(lines):
                if line.strip().startswith(("import ", "from ")):
                    lines.insert(i + 1, "from pathlib import Path")
                    break
            else:
                lines.insert(0, "from pathlib import Path")
            return "\n".join(lines)
        return content

    def _ensure_contextlib_import(self, content: str) -> str:
        if "from contextlib import suppress" not in content:
            lines = content.split("\n")

            for i, line in enumerate(lines):
                if line.strip().startswith(("import ", "from ")):
                    lines.insert(i + 1, "from contextlib import suppress")
                    break
            else:
                lines.insert(0, "from contextlib import suppress")
            return "\n".join(lines)
        return content

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        if not issue.file_path:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["No file path provided"],
            )

        file_path = Path(issue.file_path)

        try:
            content = self.context.get_file_content(file_path)
            if not content:
                return FixResult(
                    success=False,
                    confidence=0.0,
                    remaining_issues=[f"Could not read file: {file_path}"],
                )

            tree = ast.parse(content)

            if "furb107" in issue.message.lower():
                tree = self._fix_try_except_pass_ast(tree)
                self.log("Applied FURB107 fix (try/except/pass → suppress)")

            if "furb115" in issue.message.lower():
                tree = self._fix_len_check_ast(tree)
                self.log("Applied FURB115 fix (len() > 0 → truthiness)")

            if "furb104" in issue.message.lower():
                tree = self._fix_os_getcwd_ast(tree)
                self.log("Applied FURB104 fix (os.getcwd → Path.cwd)")

            if "furb111" in issue.message.lower():
                tree = self._fix_unnecessary_lambda_ast(tree)
                self.log("Applied FURB111 fix (remove unnecessary lambda wrapper)")

            fixed_content = ast.unparse(tree)

            if "furb104" in issue.message.lower():
                fixed_content = self._ensure_pathlib_import(fixed_content)

            if "furb107" in issue.message.lower():
                fixed_content = self._ensure_contextlib_import(fixed_content)

            if fixed_content != content:
                success = self.context.write_file_content(file_path, fixed_content)
                if success:
                    return FixResult(
                        success=True,
                        confidence=0.9,
                        fixes_applied=["Applied AST-based pattern fix"],
                        files_modified=[str(file_path)],
                    )

            return FixResult(
                success=True,
                confidence=1.0,
                fixes_applied=["Pattern already correct or not applicable"],
                files_modified=[],
            )

        except SyntaxError as e:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Syntax error in file: {e}"],
            )
        except Exception as e:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Error applying pattern fix: {e}"],
            )
        self._process_general_1()
        self._process_general_1()


agent_registry.register(PatternAgent)
