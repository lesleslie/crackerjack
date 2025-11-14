"""Docstring parsing and manipulation patterns.

This module provides regex patterns for working with docstrings in various formats
including triple-quoted strings, Google-style, and Sphinx-style documentation.
"""

import re

from ..core import ValidatedPattern

PATTERNS = {
    "docstring_triple_double": ValidatedPattern(
        name="docstring_triple_double",
        pattern=r'^\s*""".*?"""\s*$',
        replacement=r"",
        flags=re.MULTILINE | re.DOTALL,
        description="Remove triple-quoted docstrings with double quotes",
        test_cases=[
            (' """This is a docstring""" ', ""),
            ('"""Module docstring"""', ""),
            (' """\n Multi-line\n docstring\n """', ""),
            (
                'regular_code = "not a docstring"',
                'regular_code = "not a docstring"',
            ),
        ],
    ),
    "docstring_triple_single": ValidatedPattern(
        name="docstring_triple_single",
        pattern=r"^\s*'''.*?'''\s*$",
        replacement=r"",
        flags=re.MULTILINE | re.DOTALL,
        description="Remove triple-quoted docstrings with single quotes",
        test_cases=[
            (" '''This is a docstring''' ", ""),
            ("'''Module docstring'''", ""),
            (" '''\n Multi-line\n docstring\n '''", ""),
            (
                "regular_code = 'not a docstring'",
                "regular_code = 'not a docstring'",
            ),
        ],
    ),
    "extract_docstring_returns": ValidatedPattern(
        name="extract_docstring_returns",
        pattern=r"(?:Returns?|Return):\s*(.+?)(?=\n\n|\n\w+:|\Z)",
        replacement=r"\1",
        description="Extract return descriptions from docstrings",
        flags=re.MULTILINE | re.DOTALL,
        test_cases=[
            ("Returns: Simple value", "Simple value"),
            ("Return: Another form", "Another form"),
            ("Returns: Multi-line\n    description", "Multi-line\n    description"),
            ("Returns: Simple value\n\nArgs:", "Simple value\n\nArgs:"),
        ],
    ),
    "extract_google_docstring_params": ValidatedPattern(
        name="extract_google_docstring_params",
        pattern=r"^\s*(\w+)(?:\s*\([^)]+\))?\s*:\s*(.+)$",
        replacement=r"\1: \2",
        description="Extract parameter names and descriptions from Google-style docstrings",
        flags=re.MULTILINE,
        test_cases=[
            ("name (str): Description here", "name: Description here"),
            ("count (int): Number of items", "count: Number of items"),
            (
                "complex_param (Optional[Dict[str, Any]]): Complex type",
                "complex_param: Complex type",
            ),
            ("simple: Simple desc", "simple: Simple desc"),
        ],
    ),
    "extract_sphinx_docstring_params": ValidatedPattern(
        name="extract_sphinx_docstring_params",
        pattern=r":param\s+(\w+)\s*:\s*(.+)$",
        replacement=r"\1: \2",
        description="Extract parameter names and descriptions from Sphinx-style docstrings",
        flags=re.MULTILINE,
        test_cases=[
            (":param name: Description here", "name: Description here"),
            (":param count: Number of items", "count: Number of items"),
            (":param my_var: Simple description", "my_var: Simple description"),
            (
                ":param complex_var: Multi-word description here",
                "complex_var: Multi-word description here",
            ),
        ],
    ),
}
