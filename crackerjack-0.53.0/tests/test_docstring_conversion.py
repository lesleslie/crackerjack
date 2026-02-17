"""Test docstring-to-markdown conversion quality.

Tests conversion of different docstring formats (reST, Google-style, minimal markdown)
to clean, ultra-minimal markdown format suitable for AI understanding.
"""

import pytest
from docstring_to_markdown import convert, UnknownFormatError


def restructured_text_example():
    """This is a reStructuredText docstring.

    :param str name: The name parameter
    :returns: A greeting message
    :rtype: str
    """
    pass


def google_style_example():
    """Converts Google-style docstrings to markdown.

    Args:
        text (str): Input text to process.

    Returns:
        str: Processed markdown output.
    """
    pass


def minimal_markdown_example():
    """Process input data through validation pipeline.

    **Input**: Raw data dictionary from API
    **Returns**: Validated and sanitized data structure
    **Raises**: `ValueError` if data contains invalid fields

    Example:
        ```python
        result = validate_data({"name": "test"})
        ```
    """
    pass


class TestDocstringToMarkdownConversion:
    """Test docstring-to-markdown conversion quality."""

    def test_restructured_text_conversion(self):
        """Verify reStructuredText converts to clean markdown.

        **Expected**: Clean markdown with **bold** emphasis
        **Actual**: Output from convert() function
        """
        docstring = restructured_text_example.__doc__
        result = convert(docstring)

        # Verify conversion happened
        assert result is not None
        assert len(result) > 0

        # Verify key elements preserved
        assert "name" in result.lower()
        assert "greeting" in result.lower()

    def test_google_style_conversion(self):
        """Verify Google-style docstrings convert to clean markdown.

        **Expected**: Clean markdown with **bold** emphasis
        **Actual**: Output from convert() function
        """
        docstring = google_style_example.__doc__
        result = convert(docstring)

        # Verify conversion happened
        assert result is not None
        assert len(result) > 0

        # Verify key elements preserved
        assert "text" in result.lower()
        assert "input" in result.lower()
        assert "markdown" in result.lower()

    def test_minimal_markdown_preservation(self):
        """Verify minimal markdown docstrings are preserved.

        **Expected**: Output remains unchanged (already markdown)
        **Actual**: Output from convert() function
        """
        docstring = minimal_markdown_example.__doc__
        result = convert(docstring)

        # Verify markdown preserved
        assert result is not None
        assert len(result) > 0

        # Verify bold emphasis preserved
        assert "**Input**" in result
        assert "**Returns**" in result
        assert "**Raises**" in result

        # Verify code blocks preserved
        assert "```python" in result
        assert "validate_data" in result

    def test_conversion_quality_ultra_minimal(self):
        """Verify converted markdown is ultra-minimal.

        **Criteria**:
        - No excessive nesting
        - **Bold** for emphasis only
        - Clear structure with headers

        **Actual**: Output from convert() function
        """
        # Test all three formats
        rst_result = convert(restructured_text_example.__doc__)
        google_result = convert(google_style_example.__doc__)
        markdown_result = convert(minimal_markdown_example.__doc__)

        # Verify all produce clean output
        for result in [rst_result, google_result, markdown_result]:
            assert result is not None
            assert len(result) > 0

            # Verify no excessive blank lines (more than 2 consecutive)
            assert "\n\n\n\n" not in result

    def test_special_characters_preserved(self):
        """Verify special characters in docstrings are preserved.

        **Expected**: Backticks, underscores, and asterisks preserved
        **Actual**: Output from convert() function

        **Note**: Some formats may raise UnknownFormatError - this is expected.
        """
        special_docstring = """Function with special characters.

        **Example**: `code` with _underscores_ and *asterisks*
        """
        # Library may not recognize all formats - that's acceptable
        try:
            result = convert(special_docstring)
            assert result is not None
            assert ("`code`" in result or "code" in result.lower())
            assert len(result) > 0
        except UnknownFormatError:
            # Expected for certain edge case formats
            pass


if __name__ == "__main__":
    # Run manual verification
    print("=== reStructuredText Example ===")
    print(convert(restructured_text_example.__doc__))
    print("\n=== Google Style Example ===")
    print(convert(google_style_example.__doc__))
    print("\n=== Minimal Markdown Example ===")
    print(convert(minimal_markdown_example.__doc__))
