"""离线检查 doctor 输出和双宿主插件清单。"""
import json

from kes import doctor
from kes.cli import main
from kes.core.common import ROOT


def test_doctor_json_and_text(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(doctor, "sample_dir", lambda: tmp_path)
    main(["doctor", "--json"])
    report = json.loads(capsys.readouterr().out)
    checks = {item["name"]: item for item in report["checks"]}
    assert {"python", "uv", "ffmpeg", "ffprobe", "font:zh", "font:en", "vsco2_samples"} <= checks.keys()
    assert checks["vsco2_samples"]["status"] == "missing"
    assert checks["vsco2_samples"]["required"] is False
    assert "scripts/fetch_samples.sh" in checks["vsco2_samples"]["fix"]

    main(["doctor"])
    output = capsys.readouterr().out
    assert "KES 环境自检" in output
    assert "vsco2_samples（可选）" in output
    assert "修复：" in output


def test_doctor_required_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(doctor, "sample_dir", lambda: tmp_path)
    original = doctor.shutil.which
    monkeypatch.setattr(doctor.shutil, "which", lambda name: None if name == "ffprobe" else original(name))
    report = doctor.inspect()
    assert report["ok"] is False
    assert next(c for c in report["checks"] if c["name"] == "ffprobe")["fix"] == "brew install ffmpeg"


def test_plugin_manifests_and_skill():
    portable = json.loads((ROOT / "plugin.json").read_text())
    codex = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
    claude = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
    marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
    assert portable["$schema"] == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    assert portable["name"] == codex["name"] == claude["name"] == "kids-english-studio"
    assert portable["version"] == codex["version"] == claude["version"]
    assert codex["skills"] == "./skills/"
    assert marketplace["name"] == "kes-local" and marketplace["owner"]["name"]
    entry, = marketplace["plugins"]
    assert entry["name"] == portable["name"]
    assert entry["source"] == "./"
    skill = ROOT / "skills/kids-english-studio/SKILL.md"
    assert skill.is_file()
    assert skill.read_text() == (ROOT / "SKILL.md").read_text()
    assert "name: kids-english-studio" in skill.read_text()
