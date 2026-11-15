"""The frontmatter vocabulary — the words a document's metadata may use.

This module holds the *vocabulary* and nothing else: the lifecycle
statuses a document may declare, the roles it may claim, and the
statuses that permit a governed document to be auto-archived.

It lives here rather than beside the frontmatter *parser* because the
config package needs the vocabulary and must not depend on the
services layer to get it: a configuration that imports a service is a
layering edge that runs the wrong way, and it is the only such edge
the config package had. The parser stays where it is; the words it
validates against live with the other neutral defaults.

This package is the neutral one: ``crackerjack.core.__init__`` is
empty, so importing a module from it pulls in no configuration and no
services. ``crackerjack.models`` is not — its ``config`` module reads
the settings, so a vocabulary module there would close the loop the
config package is trying to avoid.

See docs/plans/2026-11-15-archive-lifecycle-gate.md.
"""

from __future__ import annotations

LIFECYCLE_VALUES = {"draft", "active", "partial", "shipped", "complete"}
ROLE_VALUES = {"canonical", "implementation", "umbrella", "historical", "superseded"}
RESERVED_WORDS = LIFECYCLE_VALUES | ROLE_VALUES

# Lifecycle statuses that permit a governed document (one carrying YAML
# frontmatter) to be auto-archived by the documentation cleanup. ``shipped``
# is the only status that means "delivered and verified; closed" — a
# document at ``complete`` may still have open verification or follow-up.
#
# This is the single source for the default; both
# ``crackerjack.config.settings.DocumentationSettings.archivable_statuses``
# and ``crackerjack.services.doc_categorizer`` read it. A repo with a
# different vocabulary overrides the setting rather than editing code.
#
# See docs/plans/2026-11-15-archive-lifecycle-gate.md.
ARCHIVABLE_STATUSES: frozenset[str] = frozenset({"shipped"})
