"""Shared helpers: paths, JSON IO, schema validation, subprocess."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import jsonschema

PKG = Path(__file__).resolve().parents[1]
ROOT = PKG.parent
SCHEMAS = PKG / "schemas"
EPISODES = ROOT / "episodes"
ASSETS = ROOT / "assets"
LEGAL = ROOT / "legal"


def load_json(path: Path | str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump_json(path: Path | str, obj: dict) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def validate(obj: dict, schema_name: str) -> None:
    schema = load_json(SCHEMAS / f"{schema_name}.schema.json")
    jsonschema.validate(obj, schema)


def episode_dir(episode_id: str) -> Path:
    return EPISODES / episode_id


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def ffprobe_duration_ms(path: Path | str) -> int:
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]).stdout
    return int(round(float(out.strip()) * 1000))
