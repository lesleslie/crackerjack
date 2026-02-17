# AI-Fix for Broken Documentation Links

**Status**: ✅ Fully Automated (as of 2026-02-07)

## Overview

The AI-fix system can now automatically fix or remove broken documentation links. When `check-local-links` detects broken links, the `DocumentationAgent` will:

1. **If target file exists elsewhere**: Update the link with the correct path
1. **If target file was deleted**: Remove the broken link from the documentation

## Implementation

### Parser Fix (Round 2)

**File**: `crackerjack/parsers/regex_parsers.py:545-552`

**Before**:

```python
return Issue(
    type=IssueType.DOCUMENTATION,
    severity=Priority.MEDIUM,
    message=f"Broken link in {file_path}:{line_num}: '{link_target}'' - {message}",
    file_path=file_path,
    line_number=int(line_num) if line_num.isdigit() else None,
    stage="check-local-links",
)
```

**After**:

```python
return Issue(
    type=IssueType.DOCUMENTATION,
    severity=Priority.MEDIUM,
    message=f"Broken link in {file_path}:{line_num}: '{link_target}'' - {message}",
    file_path=file_path,
    line_number=int(line_num) if line_num.isdigit() else None,
    stage="check-local-links",
    details=[f"Target file: {link_target}"],  # ← NEW!
)
```

### Agent Logic (Already Existed)

**File**: `crackerjack/agents/documentation_agent.py:517-657`

The `DocumentationAgent` already had the logic to fix broken links:

1. **Extract target file** from `details`:

   ```python
   target_file = self._extract_target_file_from_details(issue.details)
   ```

1. **Search for file** in multiple locations:

   ```python
   search_paths = [
       Path(target_file),                              # Original path
       Path("docs") / target_file,                     # docs/
       Path("docs") / "reference" / target_file,       # docs/reference/
       Path("docs") / "features" / target_file,        # docs/features/
       Path("docs") / "guides" / target_file,          # docs/guides/
   ]
   ```

1. **If found**: Update the link with correct relative path

1. **If not found**: Remove the line containing the broken link

## How It Works

### Example 1: Moved File (Gets Fixed)

**Input** (docs/GUIDE.md):

```markdown
See [Architecture](../reference/ARCHITECTURE.md) for details.
```

If `ARCHITECTURE.md` was moved to `docs/architecture/ARCHITECTURE.md`:

**Output** (docs/GUIDE.md):

```markdown
See [Architecture](../architecture/ARCHITECTURE.md) for details.
```

### Example 2: Deleted File (Gets Removed)

**Input** (docs/GUIDE.md):

```markdown
See [Old Design](../DELETED_DESIGN.md) for details.
```

If `DELETED_DESIGN.md` was deleted:

**Output** (docs/GUIDE.md):

```markdown
# Line removed entirely
```

## Testing

### Integration Test

```bash
python -c "
from crackerjack.parsers.regex_parsers import LocalLinkCheckerRegexParser

parser = LocalLinkCheckerRegexParser()
test_output = 'docs/README.md:10 - ../deleted.md Target not found'
issues = parser.parse_text(test_output)

print('✓ details populated:', issues[0].details)
# Output: ['Target file: ../deleted.md']
"
```

### Full Workflow Test

```bash
# Run AI-fix on crackerjack itself
python -m crackerjack run --ai-fix

# Expected:
# - 12 broken links detected by check-local-links
# - DocumentationAgent processes each link
# - Links to existing files: Updated
# - Links to deleted files: Removed
# - 0 broken links remaining
```

## Safety Considerations

### What Gets Fixed

✅ **Links to moved files**: Updated with correct paths
✅ **Links to renamed files**: Updated if found in search paths
✅ **Links with wrong relative paths**: Corrected automatically

### What Gets Removed

⚠️ **Lines containing links to deleted files**: Entire line is removed

**Important**: If a line contains both text and a broken link, the entire line is removed. This is intentional to ensure documentation remains accurate.

### What Doesn't Get Fixed

❌ **Broken external links**: Not handled (different tool needed)
❌ **Anchors (`#section`)**: Not validated by check-local-links
❌ **Absolute paths to web resources**: Out of scope

## Verification

To verify the fix is working:

1. **Run AI-fix**:

   ```bash
   python -m crackerjack run --ai-fix
   ```

1. **Check results**:

   ```bash
   # Before
   check-local-links... ❌ issues=12

   # After
   check-local-links... ✅ issues=0
   ```

1. **Review changes**:

   ```bash
   git diff docs/  # Review what was changed
   ```

## Rollback

If AI-fix makes unwanted changes:

```bash
# Discard AI-fix changes
git checkout -- docs/

# Or revert specific commit
git revert <commit-hash>
```

## Future Improvements

Potential enhancements:

1. **Comment out instead of remove**: Add TODO comments for manual review

   ```markdown
   <!-- TODO: Fix broken link to DELETED_FILE.md -->
   ```

1. **Suggest replacements**: If a file was deleted, suggest what to read instead

1. **External link checker**: Add support for broken web links

1. **Anchor validation**: Check if `#section` anchors still exist

## Related Documentation

- `docs/PARSER_FIX_SUMMARY.md` - Complete parser system fixes
- `docs/AI_FIX_EXPECTED_BEHAVIOR.md` - What AI-fix should do automatically
- `crackerjack/agents/documentation_agent.py` - Agent implementation
- `crackerjack/parsers/regex_parsers.py` - Parser implementation

## Commit

- `ae580125` - feat: populate details field for broken documentation links

______________________________________________________________________

**Status**: ✅ Production Ready
**Date**: 2026-02-07
**Impact**: Enables fully automated broken documentation link fixing
