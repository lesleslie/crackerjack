"""Canonical input for the unsafe-fix golden-diff test.

B006 (mutable-argument-default) is a stable unsafe-fixable rule. Touching
this file changes the golden diff and requires a human-bless step.
"""


def add_item(item: int, items: list[int] = []) -> list[int]:
    items.append(item)
    return items
