# Refurb Refactoring Fixes - Implementation Plan

## Summary
Fixing all 17 refurb suggestions to modernize Python code across 4 service files.

## Issues by Category

### FURB109: Replace `in [x, y, z]` with `in (x, y, z)` (3 instances)
**Reason**: Tuples are more efficient for membership testing than lists.

**Locations:**
1. `config_cleanup.py:290` - `elif filename in [".codespell-ignore", ".codespellrc"]:`
2. `config_cleanup.py:518` - `if value.lower() in ["true", "yes", "on"]:`
3. `config_cleanup.py:520` - `if value.lower() in ["false", "no", "off"]:`

**Fix:** Replace list literals with tuple literals.

---

### FURB107: Replace `try: ... except Exception: pass` with `with suppress(Exception): ...` (3 instances)
**Reason**: `contextlib.suppress()` is more idiomatic for ignoring exceptions.

**Locations:**
1. `config_cleanup.py:311` - Try/except block around git_service.get_changed_files()
2. `config_cleanup.py:523` - Try/except block around int() conversion
3. `doc_update_service.py:234` - Try/except block around regex matching
4. `documentation_cleanup.py:273` - Try/except block around git_service.get_changed_files()

**Fix:** Import `suppress` from `contextlib` and use context manager pattern.

---

### FURB117: Replace `open()` with `Path.open()` (6 instances)
**Reason**: Path objects have their own `open()` method which is more consistent with pathlib usage.

**Locations:**
1. `config_cleanup.py:405` - `with open(pyproject_path, "rb") as f:`
2. `config_cleanup.py:468` - `with open(pyproject_path, "w") as f:`
3. `config_cleanup.py:536` - `with open(pattern_file) as f:`
4. `config_cleanup.py:567` - `with open(json_file) as f:`
5. `config_cleanup.py:606` - `with open(ignore_file) as f:`

**Fix:** Use `path.open()` instead of `open(path)`.

---

### FURB103: Replace file write with `Path.write_text()` (1 instance)
**Reason**: `Path.write_text()` is simpler and more idiomatic for writing text files.

**Locations:**
1. `config_cleanup.py:468` - `with open(pyproject_path, "w") as f: f.write(toml_content)`

**Fix:** Replace with `pyproject_path.write_text(toml_content)`.

---

### FURB138: Use list comprehension (1 instance)
**Reason**: List comprehensions are more Pythonic than loops with append().

**Locations:**
1. `config_service.py:212` - For loop building dict items list

**Fix:** Replace loop with list comprehension.

---

### FURB188: Use `str.removesuffix()` instead of slicing (1 instance)
**Reason**: `str.removesuffix()` (Python 3.9+) is more explicit and safer.

**Locations:**
1. `git_cleanup_service.py:227` - `if pattern.endswith("/"): pattern = pattern[:-1]`

**Fix:** Use `pattern.removesuffix("/")` directly.

---

### FURB113: Use `lines.extend()` instead of multiple append() (2 instances)
**Reason**: `extend()` is cleaner when adding multiple items.

**Locations:**
1. `git_cleanup_service.py:391` - Two sequential `lines.append()` calls
2. `git_cleanup_service.py:413` - Two sequential `lines.append()` calls

**Fix:** Use `lines.extend((item1, item2))` instead.

---

## Implementation Order

1. **config_cleanup.py** (10 fixes)
   - Lines 290, 311, 405, 468, 518, 520, 523, 536, 567, 606

2. **config_service.py** (1 fix)
   - Line 212

3. **doc_update_service.py** (1 fix)
   - Line 234

4. **documentation_cleanup.py** (1 fix)
   - Line 273

5. **git_cleanup_service.py** (4 fixes)
   - Lines 227, 391, 413

## Verification

After fixes, run:
```bash
uv run refurb crackerjack
```

Expected: No refurb warnings.
