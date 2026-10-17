"""templates/<種類>.md を読み、{{名前}} を埋める。"""

import re
from functools import lru_cache

from . import SbError
from .paths import REPO_ROOT

TEMPLATE_DIR = REPO_ROOT / "templates"


@lru_cache(maxsize=None)
def load(name):
    path = TEMPLATE_DIR / f"{name}.md"
    if not path.exists():
        raise SbError(5, f"テンプレートが無い: {name}")
    return path.read_text(encoding="utf-8")


def render(name, **values):
    def fill(m):
        key = m.group(1)
        if key not in values:
            raise SbError(5, f"テンプレート {name} の {{{{{key}}}}} に値が無い")
        return str(values[key])
    return re.sub(r"\{\{(\w+)\}\}", fill, load(name))
