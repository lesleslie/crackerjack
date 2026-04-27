from __future__ import annotations

from typing import NamedTuple


class ImportSpec(NamedTuple):
    module_name: str
    symbol_name: str | None
    import_line: str


SAFE_IMPORT_SPECS: dict[str, ImportSpec] = {
    "Any": ImportSpec("typing", "Any", "from typing import Any"),
    "Callable": ImportSpec("typing", "Callable", "from typing import Callable"),
    "Dict": ImportSpec("typing", "Dict", "from typing import Dict"),
    "Iterator": ImportSpec("typing", "Iterator", "from typing import Iterator"),
    "List": ImportSpec("typing", "List", "from typing import List"),
    "Mapping": ImportSpec("typing", "Mapping", "from typing import Mapping"),
    "Optional": ImportSpec("typing", "Optional", "from typing import Optional"),
    "Path": ImportSpec("pathlib", "Path", "from pathlib import Path"),
    "PathLike": ImportSpec("os", "PathLike", "from os import PathLike"),
    "Sequence": ImportSpec("typing", "Sequence", "from typing import Sequence"),
    "Union": ImportSpec("typing", "Union", "from typing import Union"),
    "operator": ImportSpec("operator", None, "import operator"),
    "suppress": ImportSpec("contextlib", "suppress", "from contextlib import suppress"),
}


def get_safe_import_spec(undefined_name: str) -> ImportSpec | None:
    return SAFE_IMPORT_SPECS.get(undefined_name)
