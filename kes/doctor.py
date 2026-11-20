"""只读环境自检；采样可选，缺失时配乐回退程序合成。"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from .audio.music import SAMPLE_NAMES, sample_dir
from .core.common import ASSETS, ROOT


def inspect() -> dict:
    checks = []

    def add(name: str, ok: bool, required: bool, detail: str, fix: str) -> None:
        checks.append({"name": name, "status": "ok" if ok else "missing",
                       "required": required, "detail": detail, "fix": "" if ok else fix})

    version = sys.version_info
    py_ok = version.major == 3 and 11 <= version.minor <= 13
    add("python", py_ok, True, f"{version.major}.{version.minor}.{version.micro} (需 3.11–3.13)",
        "brew install python@3.13; uv python install 3.13")

    for name, fix in (("uv", "brew install uv"),
                      ("ffmpeg", "brew install ffmpeg"),
                      ("ffprobe", "brew install ffmpeg")):
        found = shutil.which(name)
        add(name, bool(found), True, found or "未找到可执行文件", fix)

    for kind in ("zh", "en"):
        fonts = [ASSETS / "fonts" / f"{kind}.{ext}" for ext in ("otf", "ttf")]
        found = next((path for path in fonts if path.is_file() and path.stat().st_size > 0), None)
        add(f"font:{kind}", found is not None, True,
            str(found) if found else "未找到非空的 OFL 字体文件",
            f"按 {ROOT / 'assets/fonts/FONTS_README.md'} 安装 {kind} 字体")

    directory = sample_dir()
    missing = [name for name in SAMPLE_NAMES.values()
               if not (directory / name).is_file() or (directory / name).stat().st_size == 0]
    add("vsco2_samples", not missing, False,
        f"{directory}；缺少 {', '.join(missing)}" if missing else f"{directory}；4/4 个采样齐备",
        "sh scripts/fetch_samples.sh  # 下载 CC0 采样；可设置 KES_SAMPLE_DIR")
    return {"ok": all(c["status"] == "ok" for c in checks if c["required"]), "checks": checks}


def render(report: dict, as_json: bool = False) -> str:
    if as_json:
        return json.dumps(report, ensure_ascii=False, indent=2)
    lines = [f"KES 环境自检：{'通过' if report['ok'] else '必需项缺失'}"]
    for check in report["checks"]:
        marker = "✓" if check["status"] == "ok" else ("✗" if check["required"] else "!")
        suffix = "（可选）" if not check["required"] else ""
        lines.append(f"{marker} {check['name']}{suffix}: {check['detail']}")
        if check["fix"]:
            lines.append(f"  修复：{check['fix']}")
    return "\n".join(lines)
