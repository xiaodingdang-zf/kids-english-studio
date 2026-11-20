#!/bin/sh
# 仅安装本地依赖和 CC0 VSCO 2 CE 采样；不触发 TTS、生图或付费 API。
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if ! command -v uv >/dev/null 2>&1; then
  printf '%s\n' '缺少 uv；macOS: brew install uv' >&2
  exit 1
fi
cd "$ROOT"
uv sync --locked
sh scripts/fetch_samples.sh
uv run --no-sync kes doctor
