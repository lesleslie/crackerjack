from __future__ import annotations


class Anthropic:
    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs
        self.messages = _Messages()


class _Messages:
    def create(self, *args, **kwargs):
        raise NotImplementedError("Anthropic client shim does not implement create()")
