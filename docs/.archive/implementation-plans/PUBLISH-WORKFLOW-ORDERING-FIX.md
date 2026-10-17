# Publish Workflow Ordering Fix

## Issue

When running `--all` or `--publish`, the workflow needs three distinct stages with proper headers and correct ordering.

**Desired Flow:**

### Stage 1: VERSION BUMP (own header)

1. Bump version in pyproject.toml
1. Update CHANGELOG.md

### Stage 2: COMMIT & PUSH (existing header)

3. Stage changes (git add)
1. Git commit with message
1. Git push to remote
1. **NO git tag** (only for publish workflow)

### Stage 3: PUBLISH TO PYPI (own header)

7. Create git tag and push (**only in publish workflow**)
1. Build package
1. Publish to PyPI

## Key Requirements

1. **Three separate stage headers**: VERSION BUMP, COMMIT & PUSH, PUBLISH TO PYPI
1. **Git tags only in publish workflow**: Never create tags during `--commit` alone
1. **Proper ordering**: Version bump → Commit → Push → Tag → Publish

## Current State Analysis

**Current files:**

- `crackerjack/core/phase_coordinator.py:249-270` - `run_publishing_phase()` and `run_commit_phase()`
- `crackerjack/core/phase_coordinator.py:490-517` - `_execute_publishing_workflow()`
- `crackerjack/core/phase_coordinator.py:519-523` - `_display_commit_push_header()` exists

**Current workflow in `crackerjack/workflows/definitions.py:314-393`:**

```python
(
    WorkflowStep(
        step_id="commit",
        name="Git Commit & Push",
        action="run_commit_phase",
        depends_on=["comprehensive"],
    ),
)
(
    WorkflowStep(
        step_id="publish",
        name="Version Bump & PyPI Publish",
        action="run_publish_phase",
        depends_on=["commit"],
    ),
)
```

## Solution

### Step 1: Add Version Bump Stage Header

Add new method in `phase_coordinator.py`:

```python
def _display_version_bump_header(self) -> None:
    sep = make_separator("-")
    self.console.print("\n" + sep)
    self.console.print("[bold bright_cyan]📝 VERSION BUMP[/bold bright_cyan]")
    self.console.print(sep + "\n")
```

### Step 2: Add Publish Stage Header

Add new method in `phase_coordinator.py`:

```python
def _display_publish_header(self) -> None:
    sep = make_separator("-")
    self.console.print("\n" + sep)
    self.console.print("[bold bright_green]🚀 PUBLISH TO PYPI[/bold bright_green]")
    self.console.print(sep + "\n")
```

### Step 3: Refactor Publishing Workflow

Split `_execute_publishing_workflow` into three clear stages:

```python
def _execute_publishing_workflow(
    self, options: OptionsProtocol, version_type: str
) -> bool:
    # ========================================
    # STAGE 1: VERSION BUMP
    # ========================================
    self._display_version_bump_header()

    new_version = self.publish_manager.bump_version(version_type)
    if not new_version:
        self.session.fail_task("publishing", "Version bumping failed")
        return False

    self.console.print(f"[green]✅[/green] Version bumped to {new_version}")
    self.console.print(f"[green]✅[/green] Changelog updated for version {new_version}")

    # ========================================
    # STAGE 2: COMMIT & PUSH
    # ========================================
    self._display_commit_push_header()

    # Stage changes
    changed_files = self.git_service.get_changed_files()
    if not changed_files:
        self.console.print("[yellow]⚠️ No changes to stage[/yellow]")
        return False

    if not self.git_service.add_files(changed_files):
        self.session.fail_task("publishing", "Failed to stage files")
        return False
    self.console.print(f"[green]✅[/green] Staged {len(changed_files)} files")

    # Commit
    commit_message = f"chore: bump version to {new_version}"
    if not self.git_service.commit_files(commit_message):
        self.session.fail_task("publishing", "Failed to commit changes")
        return False
    self.console.print(f"[green]✅[/green] Committed: {commit_message}")

    # Push
    if not self.git_service.push_to_remote():
        self.session.fail_task("publishing", "Failed to push to remote")
        return False
    self.console.print("[green]✅[/green] Pushed to remote")

    # ========================================
    # STAGE 3: PUBLISH TO PYPI
    # ========================================
    self._display_publish_header()

    # Create and push git tag (ONLY in publish workflow)
    if not options.no_git_tags:
        if not self.publish_manager.create_git_tag(new_version):
            self.console.print(
                f"[yellow]⚠️ Failed to create git tag v{new_version}[/yellow]"
            )
        else:
            self.console.print(
                f"[green]✅[/green] Created and pushed tag v{new_version}"
            )

    # Build and publish package
    if not self.publish_manager.publish_package():
        self.session.fail_task("publishing", "Package publishing failed")
        return False

    self.session.complete_task("publishing", f"Published version {new_version}")
    return True
```

### Step 4: Ensure Commit Phase Never Creates Tags

Verify `run_commit_phase()` does NOT call `create_git_tag()`:

```python
@handle_errors
def run_commit_phase(self, options: OptionsProtocol) -> bool:
    if not options.commit:
        return True

    # Display commit & push header
    self._display_commit_push_header()
    self.session.track_task("commit", "Git commit and push")
    changed_files = self.git_service.get_changed_files()
    if not changed_files:
        return self._handle_no_changes_to_commit()
    commit_message = self._get_commit_message(changed_files, options)
    # NO git tag creation here - only in publish workflow
    return self._execute_commit_and_push(changed_files, commit_message)
```

## Expected Output

### Running `python -m crackerjack --all patch`:

```
[... Fast hooks, tests, comprehensive hooks ...]

───────────────────────────────────────────────
📝 VERSION BUMP
───────────────────────────────────────────────

✅ Version bumped to 1.2.3
✅ Changelog updated for version 1.2.3

───────────────────────────────────────────────
📦 COMMIT & PUSH
───────────────────────────────────────────────

✅ Staged 2 files
✅ Committed: chore: bump version to 1.2.3
✅ Pushed to remote

───────────────────────────────────────────────
🚀 PUBLISH TO PYPI
───────────────────────────────────────────────

✅ Created and pushed tag v1.2.3
🔨 Building package...
✅ Package built successfully
🚀 Publishing to PyPI...
🎉 Package published successfully!
```

### Running `python -m crackerjack --commit` (NO publish):

```
[... Fast hooks, tests, comprehensive hooks ...]

───────────────────────────────────────────────
📦 COMMIT & PUSH
───────────────────────────────────────────────

✅ Staged 3 files
✅ Committed: fix: resolve bug in parser
✅ Pushed to remote

[NO VERSION BUMP stage]
[NO PUBLISH stage]
[NO git tag creation]
```

## Files to Modify

**`crackerjack/core/phase_coordinator.py`:**

1. Add `_display_version_bump_header()` method (~line 519)
1. Add `_display_publish_header()` method (~line 524)
1. Refactor `_execute_publishing_workflow()` with three stages (~line 490-517)
1. Verify `run_commit_phase()` never creates tags (~line 258-269)

## Testing

```bash
# Test commit alone (should NOT create tags)
python -m crackerjack --commit
git tag  # Verify no new tags created

# Test publish workflow (should create tags)
python -m crackerjack --all patch
git tag  # Verify tag v1.2.3 was created

# Test with no-git-tags flag
python -m crackerjack --all patch --no-git-tags
git tag  # Verify no tag created, but still publishes
```

## Summary of Changes

| Stage | Header | Operations | Git Tag? |
|-------|--------|------------|----------|
| VERSION BUMP | 📝 VERSION BUMP | Bump version, update changelog | No |
| COMMIT & PUSH | 📦 COMMIT & PUSH | Stage, commit, push | **Never** (even in publish) |
| PUBLISH TO PYPI | 🚀 PUBLISH TO PYPI | Create tag, build, publish | **Only in publish workflow** |

This ensures:

- ✅ Three distinct stages with clear headers
- ✅ Git tags only created during publish workflow
- ✅ `--commit` alone never creates tags
- ✅ Proper ordering: bump → commit → push → tag → publish
