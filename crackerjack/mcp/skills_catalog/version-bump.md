---
name: version-bump
description: Use ONLY when the user explicitly types `/crackerjack:version-bump` or selects this Skill from the picker to bump the Crackerjack version. Do not auto-trigger. Routes through `mcp__crackerjack__crackerjack_run -p {major,minor,patch}` after explicit user confirmation of the bump level. Use when the user says "bump version", "cut a release", or "tag vX.Y.Z".
allowed-tools: mcp__crackerjack__crackerjack_run, mcp__crackerjack__suggest_patterns, Read
---

# version-bump

## When to use

This Skill is the right entry point when the user wants to cut a
new Crackerjack release:

- "Bump the patch version"
- "Cut a minor release"
- "Tag v1.2.0"
- "Release this"

The Skill does NOT auto-trigger — version bumps are a public, durable
operation that should only happen with explicit user intent.

## What the tool does

The Skill calls `mcp__crackerjack__crackerjack_run -p {level}` where
`level` is one of `major`, `minor`, `patch`. The crackerjack CLI
handles the full lifecycle per CLAUDE.md:

1. Update version in `pyproject.toml`
2. Run quality checks (skip if `--no-verify`)
3. Commit with conventional-commits message
4. Tag with `vX.Y.Z`
5. Push (ONLY if user has explicitly authorized — per
   `feedback-bodai-push-is-user-controlled.md` memory note)

The user must confirm the bump level BEFORE the Skill fires. Phrasing:
"I'm about to bump the patch version (0.78.0 → 0.78.1). Confirm?"

## When NOT to use

- For snapshot/dev releases, bump manually in `pyproject.toml`.
- For pre-release qualifiers (`-alpha.1`), use the `crackerjack-cli-run-subcommand`
  memory note's caveats.
- For PyPI publishing, that's a separate step after the tag lands.

## Failure modes and how to handle them

- **Quality check fails**: pre-bump gates fail. Surface the failing
  stage output verbatim. The Skill halts before tagging.
- **Tag collision**: a tag `vX.Y.Z` already exists. The CLI returns
  `error="tag exists"`. Surface verbatim; suggest either delete the
  remote tag or bump further.
- **Push denied by user**: per `feedback-bodai-push-is-user-controlled.md`,
  NEVER auto-push. The Skill stops after the tag is locally created.

## Example flow

User: "Bump the patch version."

Skill action:

```python
# First, confirm
print("About to bump 0.78.0 → 0.78.1 (patch). Confirm? (yes/no)")
# On yes:
result = await mcp__crackerjack__crackerjack_run(
    args=["-p", "patch"],
)
print(result["output"])
# NOTE: do NOT auto-push; surface "tag created locally; review with git log".
```

The user must explicitly invoke `git push` (per bodai pre-1.0 policy).
