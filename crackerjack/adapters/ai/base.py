import ast
import asyncio
import json
import logging
import random
import re
import typing as t
from abc import ABC, abstractmethod
from uuid import UUID

from pydantic import BaseModel, Field

from crackerjack.models.adapter_metadata import AdapterStatus

MODULE_ID = UUID("00000000-0000-0000-0000-000000000000")
MODULE_STATUS = AdapterStatus.STABLE

logger = logging.getLogger(__name__)


class BaseCodeFixerSettings(BaseModel):
    model: str = Field(
        description="Model identifier for the AI provider",
    )
    max_tokens: int = Field(
        default=4096,
        ge=1,
        le=8192,
        description="Maximum tokens in API response",
    )
    temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Temperature for response consistency",
    )
    confidence_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum confidence score to apply fixes",
    )
    max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum API retry attempts",
    )
    max_file_size_bytes: int = Field(
        default=10_485_760,
        ge=1024,
        le=104_857_600,
        description="Maximum file size to process (security limit)",
    )


class BaseCodeFixer(ABC):
    def __init__(
        self,
        settings: BaseCodeFixerSettings | None = None,
    ) -> None:
        self._client: t.Any | None = None
        self._settings = settings
        self._client_lock: asyncio.Lock | None = None
        self._initialized = False

    async def init(self) -> None:
        if self._initialized:
            return

        if not self._settings:
            msg = "Settings not provided - pass settings to constructor"
            raise RuntimeError(msg)

        self._initialized = True
        logger.debug(f"{self.__class__.__name__} adapter initialized")

    async def fix_code_issue(
        self,
        file_path: str,
        issue_description: str,
        code_context: str,
        fix_type: str,
        max_retries: int = 3,
    ) -> dict[str, str | float | list[str] | bool]:
        return await self._fix_code_issue_with_retry(
            file_path,
            issue_description,
            code_context,
            fix_type,
            max_retries,
        )

    @abstractmethod
    async def _initialize_client(self) -> t.Any: ...

    @abstractmethod
    async def _call_provider_api(
        self,
        client: t.Any,
        prompt: str,
    ) -> t.Any: ...

    @abstractmethod
    def _extract_content_from_response(
        self,
        response: t.Any,
    ) -> str: ...

    @abstractmethod
    def _validate_provider_specific_settings(self) -> None: ...

    async def _fix_code_issue_with_retry(
        self,
        file_path: str,
        issue_description: str,
        code_context: str,
        fix_type: str,
        max_retries: int,
    ) -> dict[str, str | float | list[str] | bool]:
        client = await self._ensure_client()

        prompt = self._build_fix_prompt(
            file_path,
            issue_description,
            code_context,
            fix_type,
        )

        for attempt in range(max_retries):
            try:
                response = await self._call_provider_api(client, prompt)
                parsed = self._parse_fix_response(response)

                if self._validate_fix_quality(parsed, code_context):
                    return parsed

                if attempt < max_retries - 1:
                    prompt = self._enhance_prompt_for_retry(prompt, parsed)
                    continue

                return parsed

            except Exception as e:
                logger.warning(f"API call failed (attempt {attempt + 1}): {e}")

                if attempt == max_retries - 1:
                    return {
                        "success": False,
                        "error": self._sanitize_error_message(str(e)),
                        "confidence": 0.0,
                    }

                await self._backoff_delay(attempt)

        return {"success": False, "error": "Max retries exceeded", "confidence": 0.0}

    async def _ensure_client(self) -> t.Any:
        if self._client is None:
            if self._client_lock is None:
                self._client_lock = asyncio.Lock()

            async with self._client_lock:
                if self._client is None:
                    self._validate_provider_specific_settings()
                    self._client = await self._initialize_client()

        return self._client

    def _parse_fix_response(
        self,
        response: t.Any,
    ) -> dict[str, str | float | list[str] | bool]:
        try:
            content = self._extract_content_from_response(response)

            json_str = self._extract_json_from_response(content)

            data = json.loads(json_str)

            required_fields = ["fixed_code", "explanation", "confidence"]
            missing = [f for f in required_fields if f not in data]

            if missing:
                logger.warning(f"Missing fields in response: {missing}")
                data.setdefault("fixed_code", "")
                data.setdefault("explanation", "No explanation provided")
                data.setdefault("confidence", 0.5)

            confidence = float(data.get("confidence", 0.5))
            data["confidence"] = max(0.0, min(1.0, confidence))

            fixed_code = data["fixed_code"]
            is_valid, error_msg = self._validate_ai_generated_code(fixed_code)

            if not is_valid:
                logger.error(
                    f"AI-generated code failed security validation: {error_msg}",
                )
                return {
                    "success": False,
                    "error": f"Security validation failed: {error_msg}",
                    "confidence": 0.0,
                }

            explanation = self._sanitize_error_message(data["explanation"])

            return {
                "success": True,
                "fixed_code": fixed_code,
                "explanation": explanation,
                "confidence": data["confidence"],
                "changes_made": data.get("changes_made", []),
                "potential_side_effects": data.get("potential_side_effects", []),
            }

        except json.JSONDecodeError as e:
            sanitized_error = self._sanitize_error_message(str(e))
            logger.exception(f"Failed to parse JSON response: {sanitized_error}")
            return {
                "success": False,
                "error": f"Invalid JSON: {sanitized_error}",
                "confidence": 0.0,
            }
        except Exception as e:
            sanitized_error = self._sanitize_error_message(str(e))
            logger.exception(f"Unexpected error parsing response: {sanitized_error}")
            return {
                "success": False,
                "error": sanitized_error,
                "confidence": 0.0,
            }

    def _validate_ai_generated_code(self, code: str) -> tuple[bool, str]:
        is_valid, error_msg = self._check_dangerous_patterns(code)
        if not is_valid:
            return False, error_msg

        is_valid, error_msg = self._validate_ast_security(code)
        if not is_valid:
            return False, error_msg

        is_valid, error_msg = self._check_code_size_limit(code)
        if not is_valid:
            return False, error_msg

        return True, ""

    def _check_dangerous_patterns(self, code: str) -> tuple[bool, str]:
        dangerous_patterns = [
            (r"\beval\s*\(", "eval() call detected"),
            (r"\bexec\s*\(", "exec() call detected"),
            (r"\b__import__\s*\(", "dynamic import detected"),
            (
                r"subprocess\.\w+\([^)]*shell\s*=\s*True",
                "subprocess with shell=True detected",
            ),
            (r"\bos\.system\s*\(", "os.system() call detected"),
            (
                r"\bpickle\.loads?\s*\(",
                "pickle usage detected (unsafe with untrusted data)",
            ),
            (
                r"\byaml\.load\s*\([^)]*Loader\s*=\s*yaml\.Loader",
                "unsafe YAML loading detected",
            ),
        ]

        for pattern, message in dangerous_patterns:
            if re.search(pattern, code):  # REGEX OK: security validation
                return False, f"Security violation: {message}"

        return True, ""

    def _validate_ast_security(self, code: str) -> tuple[bool, str]:
        try:
            tree = ast.parse(code)
            self._scan_ast_for_dangerous_imports(tree)
        except SyntaxError as e:
            return (
                False,
                f"Syntax error in generated code: {self._sanitize_error_message(str(e))}",
            )
        except Exception as e:
            return (
                False,
                f"Failed to parse generated code: {self._sanitize_error_message(str(e))}",
            )

        return True, ""

    def _is_dangerous_import(self, node: ast.Import) -> bool:
        for alias in node.names:
            if alias.name in ("os", "subprocess", "sys"):
                return not self._is_safe_usage(node)
        return False

    def _scan_ast_for_dangerous_imports(self, tree: ast.AST) -> None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and self._is_dangerous_import(node):
                pass

    def _check_code_size_limit(self, code: str) -> tuple[bool, str]:
        assert self._settings is not None, "Settings not initialized"
        if len(code) > self._settings.max_file_size_bytes:
            return (
                False,
                f"Generated code exceeds size limit ({len(code)} > {self._settings.max_file_size_bytes})",
            )
        return True, ""

    def _is_safe_usage(self, import_node: ast.Import) -> bool:
        return True

    def _sanitize_error_message(self, error_msg: str) -> str:
        error_msg = re.sub(r"/[\w\-./ ]+/", "<path>/", error_msg)

        error_msg = re.sub(r"[A-Z]:\\[\w\-\\ ]+\\", "<path>\\", error_msg)

        error_msg = re.sub(r"sk-[a-zA-Z0-9]{20,}", "<api-key>", error_msg)

        error_msg = re.sub(r'["\'][\w\-]{32,}["\']', "<secret>", error_msg)

        return error_msg

    def _sanitize_prompt_input(self, user_input: str) -> str:
        sanitized = user_input

        injection_patterns = [
            r"(?i)(ignore previous|disregard previous|forget previous)",
            r"(?i)(system:|assistant:|user:)",
            r"(?i)(you are now|act as|pretend to be)",
        ]

        for pattern in injection_patterns:
            sanitized = re.sub(pattern, "[FILTERED]", sanitized)

        return sanitized.replace("```", "'''")

    def _build_fix_prompt(
        self,
        file_path: str,
        issue: str,
        context: str,
        fix_type: str,
    ) -> str:
        issue = self._sanitize_prompt_input(issue)
        context = self._sanitize_prompt_input(context)

        assert self._settings is not None, "Settings not initialized"
        if len(context) > self._settings.max_file_size_bytes:
            context = (
                context[: self._settings.max_file_size_bytes] + "\n... (truncated)"
            )

        return f"""You are an expert Python code fixer specialized in {fix_type} issues.

**Task**: Fix the following code issue in a production codebase.

**File**: {file_path}
**Issue Type**: {fix_type}
**Issue Description**: {issue}

**Current Code**:
```python
{context}
```

**Requirements**:
1. Fix the issue while maintaining existing functionality
2. Follow Python 3.13+ best practices
3. Preserve existing code style and formatting where possible
4. Ensure the fix is minimal and focused on the specific issue
5. Provide a confidence score (0.0-1.0) for your fix

**Response Format** (valid JSON only):
```json
{{
    "fixed_code": "... complete fixed code ...",
    "explanation": "Brief explanation of what was changed and why",
    "confidence": 0.95,
    "changes_made": ["change 1", "change 2"],
    "potential_side_effects": ["possible side effect 1"]
}}
```

Respond with ONLY the JSON, no additional text."""

    def _extract_json_from_response(self, content: str) -> str:
        if "```json" in content:
            json_start = content.find("```json") + 7
            json_end = content.find("```", json_start)
            return content[json_start:json_end].strip()

        if "```" in content:
            json_start = content.find("```") + 3
            json_end = content.find("```", json_start)
            return content[json_start:json_end].strip()

        return content.strip()

    def _validate_fix_quality(
        self,
        parsed_response: dict[str, str | float | list[str] | bool],
        original_code: str,
    ) -> bool:
        if not parsed_response.get("success"):
            return False

        fixed_code_raw = parsed_response.get("fixed_code", "")
        confidence_raw = parsed_response.get("confidence", 0.0)

        fixed_code = str(fixed_code_raw) if fixed_code_raw else ""
        confidence = (
            float(confidence_raw) if isinstance(confidence_raw, (int, float)) else 0.0
        )

        if not fixed_code or not fixed_code.strip():
            logger.warning("Fixed code is empty")
            return False

        if fixed_code.strip() == original_code.strip():
            logger.warning("Fixed code is identical to original")
            return False

        assert self._settings is not None, "Settings not initialized"
        min_confidence = self._settings.confidence_threshold
        if confidence < min_confidence:
            logger.info(f"Confidence {confidence:.2f} below threshold {min_confidence}")
            return False

        return True

    async def _backoff_delay(self, attempt: int) -> None:
        base_delay = 2**attempt

        jitter = random.uniform(-0.25, 0.25) * base_delay  # nosec B311
        delay = base_delay + jitter

        logger.info(f"Backing off for {delay:.2f}s before retry")
        await asyncio.sleep(delay)

    def _enhance_prompt_for_retry(
        self,
        original_prompt: str,
        previous_response: dict[str, str | float | list[str] | bool],
    ) -> str:
        confidence = previous_response.get("confidence", 0.0)

        return f"""
**Previous Attempt Analysis**:
The previous fix had confidence {confidence:.2f}.
Please provide a more robust solution with higher confidence.

{original_prompt}
"""
