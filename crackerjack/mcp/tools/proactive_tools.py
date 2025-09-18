import typing as t


def _create_architectural_assessment(
    args: str, parsed_kwargs: dict[str, t.Any]
) -> dict[str, t.Any]:
    assessment = {
        "feature": parsed_kwargs.get("feature", "unknown"),
        "complexity": parsed_kwargs.get("complexity", "medium"),
        "context": args or "General development planning",
        "proactive_recommendations": [],
    }

    recommendations = []

    recommendations.append(
        {
            "agent": "crackerjack-architect",
            "priority": "high",
            "reason": "Expert architectural planning for crackerjack compliance",
            "action": 'Task tool with subagent_type ="crackerjack-architect" for feature planning and architecture',
            "benefits": [
                "Prevents violations through proper initial architecture",
                "Applies crackerjack patterns from the start",
                "Reduces iteration cycles by 50 % +",
                "Ensures consistency with project standards",
            ],
        }
    )

    complexity = parsed_kwargs.get("complexity", "medium")
    if complexity in ("high", "complex"):
        recommendations.append(
            {
                "agent": "refactoring-specialist",
                "priority": "high",
                "reason": "Complex features require careful structural planning",
                "action": 'Task tool with subagent_type ="refactoring-specialist" for complexity management',
            }
        )

    feature = parsed_kwargs.get("feature", "")
    if any(
        keyword in feature.lower() for keyword in ("auth", "security", "api", "data")
    ):
        recommendations.append(
            {
                "agent": "security-auditor",
                "priority": "medium",
                "reason": "Security-sensitive feature requires expert review",
                "action": 'Task tool with subagent_type ="security-auditor" for security validation',
            }
        )

    assessment["proactive_recommendations"] = recommendations
    assessment["planning_strategy"] = "proactive_architecture_first"

    return assessment


def _create_validation_results(file_path: str) -> dict[str, t.Any]:
    validation = {
        "file_path": file_path,
        "validation_results": [],
        "architectural_compliance": "unknown",
        "recommendations": [],
    }

    compliance_checks = [
        {
            "check": "complexity_compliance",
            "status": "requires_analysis",
            "message": "Cognitive complexity should be ≤15 per function",
            "tool": "complexipy",
        },
        {
            "check": "clean_code_patterns",
            "status": "requires_analysis",
            "message": "Follow DRY, YAGNI, KISS principles",
            "patterns": [
                "extract_method",
                "protocol_interfaces",
                "dependency_injection",
            ],
        },
        {
            "check": "security_patterns",
            "status": "requires_analysis",
            "message": "Use secure temp files, proper input validation",
            "tool": "bandit",
        },
        {
            "check": "type_annotations",
            "status": "requires_analysis",
            "message": "All functions must have proper type hints",
            "tool": "pyright",
        },
    ]

    validation["validation_results"] = [
        f"{check['check']}: {check['status']} - {check['message']}"
        for check in compliance_checks
    ]

    validation["recommendations"] = [
        "Run full crackerjack quality process: python - m crackerjack-t",
        "Use crackerjack-architect for complex refactoring decisions",
        "Apply pattern learning from successful fixes",
        "Validate against architectural plan before committing",
    ]

    validation["next_steps"] = [
        'Task tool with subagent_type ="crackerjack-architect" for architectural guidance',
        "Run comprehensive quality checks",
        "Apply learned patterns from pattern cache",
    ]

    return validation


def _create_pattern_suggestions(problem_context: str) -> dict[str, t.Any]:
    pattern_suggestions: dict[str, t.Any] = {
        "context": problem_context,
        "recommended_patterns": [],
        "implementation_guidance": [],
        "specialist_agents": [],
    }

    _add_complexity_patterns(pattern_suggestions, problem_context)
    _add_dry_patterns(pattern_suggestions, problem_context)
    _add_performance_patterns(pattern_suggestions, problem_context)
    _add_security_patterns(pattern_suggestions, problem_context)

    pattern_suggestions["specialist_agents"] = [
        {
            "agent": "crackerjack-architect",
            "when_to_use": "For architectural decisions and complex pattern application",
            "action": 'Task tool with subagent_type ="crackerjack-architect"',
        },
        {
            "agent": "refactoring-specialist",
            "when_to_use": "For complexity reduction and structural improvements",
            "action": 'Task tool with subagent_type ="refactoring-specialist"',
        },
        {
            "agent": "security-auditor",
            "when_to_use": "For security pattern validation and vulnerability assessment",
            "action": 'Task tool with subagent_type ="security-auditor"',
        },
    ]

    pattern_suggestions["implementation_guidance"] = [
        "Start with crackerjack-architect for overall planning",
        "Apply one pattern at a time to avoid complexity",
        "Validate each pattern with crackerjack quality checks",
        "Cache successful patterns for future use",
        "Document architectural decisions for team knowledge",
    ]

    if not pattern_suggestions["recommended_patterns"]:
        pattern_suggestions["recommended_patterns"] = [
            {
                "pattern": "standard_crackerjack_patterns",
                "description": "Apply standard crackerjack clean code patterns",
                "benefits": [
                    "Consistent code quality",
                    "Better maintainability",
                    "Team alignment",
                ],
            }
        ]

    return pattern_suggestions


def _add_complexity_patterns(
    pattern_suggestions: dict[str, t.Any], problem_context: str
) -> None:
    if any(
        keyword in problem_context.lower()
        for keyword in ("complex", "refactor", "cleanup")
    ):
        pattern_suggestions["recommended_patterns"].extend(
            [
                {
                    "pattern": "extract_method",
                    "description": "Break complex functions into smaller, focused methods",
                    "benefits": [
                        "Reduces cognitive complexity",
                        "Improves testability",
                        "Follows KISS principle",
                    ],
                },
                {
                    "pattern": "dependency_injection",
                    "description": "Use protocol interfaces for better decoupling",
                    "benefits": [
                        "Improves testability",
                        "Reduces coupling",
                        "Enables better mocking",
                    ],
                },
            ]
        )


def _add_dry_patterns(
    pattern_suggestions: dict[str, t.Any], problem_context: str
) -> None:
    if any(
        keyword in problem_context.lower() for keyword in ("duplicate", "repeat", "dry")
    ):
        pattern_suggestions["recommended_patterns"].extend(
            [
                {
                    "pattern": "common_base_class",
                    "description": "Extract shared functionality to base classes or mixins",
                    "benefits": [
                        "Reduces duplication",
                        "Centralizes common logic",
                        "Easier maintenance",
                    ],
                },
                {
                    "pattern": "utility_functions",
                    "description": "Create reusable utility functions for common operations",
                    "benefits": [
                        "Single source of truth",
                        "Reduces code duplication",
                        "Easier testing",
                    ],
                },
            ]
        )


def _add_performance_patterns(
    pattern_suggestions: dict[str, t.Any], problem_context: str
) -> None:
    if any(
        keyword in problem_context.lower()
        for keyword in ("slow", "performance", "optimize")
    ):
        pattern_suggestions["recommended_patterns"].extend(
            [
                {
                    "pattern": "list_comprehension",
                    "description": "Use list[t.Any] comprehensions instead of manual loops",
                    "benefits": [
                        "Better performance",
                        "More readable",
                        "Pythonic code",
                    ],
                },
                {
                    "pattern": "generator_pattern",
                    "description": "Use generators for memory-efficient processing",
                    "benefits": [
                        "Reduced memory usage",
                        "Lazy evaluation",
                        "Better for large datasets",
                    ],
                },
            ]
        )


def _add_security_patterns(
    pattern_suggestions: dict[str, t.Any], problem_context: str
) -> None:
    if any(
        keyword in problem_context.lower() for keyword in ("security", "safe", "secure")
    ):
        pattern_suggestions["recommended_patterns"].extend(
            [
                {
                    "pattern": "secure_temp_files",
                    "description": "Use tempfile module instead of hardcoded paths",
                    "benefits": [
                        "Prevents security vulnerabilities",
                        "Cross-platform compatibility",
                        "Automatic cleanup",
                    ],
                },
                {
                    "pattern": "input_validation",
                    "description": "Validate and sanitize all user inputs",
                    "benefits": [
                        "Prevents injection attacks",
                        "Better error handling",
                        "Data integrity",
                    ],
                },
            ]
        )


def _create_error_response(error: Exception, recommendation: str) -> str:
    import json

    return json.dumps(
        {
            "error": str(error),
            "fallback_patterns": [
                "clean_code",
                "single_responsibility",
                "dry_principle",
            ],
            "recommendation": recommendation,
        }
    )


def register_proactive_tools(mcp_app: t.Any) -> None:
    return _register_proactive_tools(mcp_app)


def _register_proactive_tools(mcp_app: t.Any) -> None:
    _register_plan_development_tool(mcp_app)
    _register_validate_architecture_tool(mcp_app)
    _register_suggest_patterns_tool(mcp_app)


def _register_plan_development_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()
    async def plan_development(args: str, kwargs: str) -> str:
        import json

        try:
            parsed_kwargs: dict[str, t.Any] = json.loads(kwargs) if kwargs else {}
            assessment = _create_architectural_assessment(args, parsed_kwargs)
            return json.dumps(assessment, indent=2)
        except Exception as e:
            return _create_error_response(e, "Use standard development approach")


def _register_validate_architecture_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()
    async def validate_architecture(args: str, kwargs: str) -> str:
        import json

        try:
            parsed_kwargs: dict[str, t.Any] = json.loads(kwargs) if kwargs else {}
            file_path = args or parsed_kwargs.get("file_path", "")
            validation = _create_validation_results(file_path)
            return json.dumps(validation, indent=2)
        except Exception as e:
            return _create_error_response(
                e, "Run standard crackerjack validation: python-m crackerjack"
            )


def _register_suggest_patterns_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()
    async def suggest_patterns(args: str, kwargs: str) -> str:
        import json

        try:
            json.loads(kwargs) if kwargs else {}
            problem_context = args or "General pattern suggestions"
            pattern_suggestions = _create_pattern_suggestions(problem_context)
            return json.dumps(pattern_suggestions, indent=2)
        except Exception as e:
            return _create_error_response(
                e,
                'Use Task tool with subagent_type ="crackerjack-architect" for expert guidance',
            )
