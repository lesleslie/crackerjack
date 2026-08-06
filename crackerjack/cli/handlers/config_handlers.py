from typing import Never


def handle_config_updates(options, console=None) -> Never:
    msg = "handle_config_updates needs to be properly implemented in the modular structure"
    raise NotImplementedError(
        msg,
    )


__all__ = ["handle_config_updates"]
