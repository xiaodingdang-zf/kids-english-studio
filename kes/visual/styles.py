"""项目内风格包读取与验证。缺失或无效的风格直接报错，不静默回退。"""
from __future__ import annotations

from functools import lru_cache

import jsonschema

from ..core.common import ROOT, load_json

STYLES = ROOT / "styles"
STYLE_ORDER = ("clay", "felt", "papercraft", "tin", "cardboard", "wood", "crochet", "fabric")


@lru_cache(maxsize=16)
def load_style(style_id: str) -> dict:
    if not style_id or not all(c.isascii() and (c.islower() or c.isdigit() or c in "_-") for c in style_id):
        raise ValueError(f"无效风格 ID：{style_id!r}")
    path = STYLES / style_id / "style.json"
    if not path.is_file():
        raise ValueError(f"找不到风格包：{style_id}")
    style = load_json(path)
    jsonschema.validate(style, load_json(STYLES / "style.schema.json"))
    if style["style_id"] != style_id:
        raise ValueError(f"风格包 ID 与目录不一致：{style_id}")
    return style


def list_styles() -> list[dict]:
    found = {p.parent.name for p in STYLES.glob("*/style.json")}
    ordered = [s for s in STYLE_ORDER if s in found] + sorted(found - set(STYLE_ORDER))
    return [load_style(s) for s in ordered]
