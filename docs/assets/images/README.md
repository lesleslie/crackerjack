# Image assets

Tracked images referenced from `docs/**/*.md` files live here.

## Layout

```
images/
├── README.md            # this file
├── dag-overview.png     # tracked example (replace with real assets as docs grow)
└── .scratch/            # gitignored — session iteration outputs
```

## Conventions

- **One image, one purpose.** Don't co-locate dashboard screenshots with
  architecture diagrams — split into subdirectories when types diverge.
- **Reference by relative path from the doc that uses it:**
  `![DAG overview](./dag-overview.png)`
- **Never reference `.scratch/`** from any `.md` file. The scratch directory
  is local-only; if a scratch image becomes canonical, **promote** it by
  `git mv` from `.scratch/` into the parent and update the reference.

## What goes in `.scratch/`

Iteration outputs from diagram-generation sessions (Claude Code, Excalidraw,
Mermaid renders) that are not yet committed to a doc. The directory exists
so generation tools have a stable location that won't pollute `git status`.

Scratch files are **never** committed. Clean up with:

```bash
git clean -fd docs/assets/images/.scratch/
```

## Promoting scratch to tracked

When a scratch image is ready for a doc:

```bash
git mv docs/assets/images/.scratch/foo.png docs/assets/images/foo.png
# then update the markdown that references it
```

The `.scratch/` directory name is load-bearing — the leading dot is what
keeps the gitignore rule matching. Do not rename it to `scratch/`.
