"""自动 QC：技术指标 + 时轴一致性 + 素材权利门禁。只读，不联网，不计费。"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from ..core.common import LEGAL, dump_json, load_json, run, validate
from ..visual.render import LAYOUTS


def _probe(video: Path) -> dict:
    out = run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)]).stdout
    return json.loads(out)


def _loudness(video: Path) -> tuple[float | None, float | None]:
    err = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(video), "-map", "0:a", "-af",
               "ebur128=peak=true", "-f", "null", "-"]).stderr
    s = err[err.rfind("Summary:"):]
    i = re.search(r"I:\s+(-?[\d.]+) LUFS", s)
    p = re.search(r"Peak:\s+(-?[\d.]+) dBFS", s)
    return (float(i.group(1)) if i else None, float(p.group(1)) if p else None)


def _black_segments(video: Path) -> list[str]:
    err = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(video), "-vf",
               "blackdetect=d=0.5:pix_th=0.10", "-an", "-f", "null", "-"]).stderr
    return re.findall(r"black_start:[\d.]+ black_end:[\d.]+", err)


def check(rule_id, ok, expected, actual, evidence="", warn=False):
    return {"rule_id": rule_id, "status": "PASS" if ok else ("WARN" if warn else "FAIL"),
            "expected": expected, "actual": actual, "evidence": evidence}


def run_qc(episode_path: Path, out_dir: Path, video: Path | None = None) -> Path:
    episode = load_json(episode_path)
    timeline = load_json(out_dir / "audio_timeline.json")
    manifest = load_json(out_dir / "frames_manifest.json")
    video = video or out_dir / f"{episode['episode_id']}_{timeline['mode']}.mp4"
    checks = []

    exp_w, exp_h = LAYOUTS[episode["aspect"]]["size"]
    probe = _probe(video)
    v = next(s for s in probe["streams"] if s["codec_type"] == "video")
    a = next((s for s in probe["streams"] if s["codec_type"] == "audio"), None)
    checks.append(check("video.resolution", (v["width"], v["height"]) == (exp_w, exp_h),
                        f"{exp_w}x{exp_h}", f"{v['width']}x{v['height']}"))
    num, den = map(int, v["r_frame_rate"].split("/"))
    fps = num / den
    checks.append(check("video.fps", abs(fps - 24) < 0.01 or abs(fps - 30) < 0.01, "24 或 30", round(fps, 3)))
    checks.append(check("audio.present", a is not None, "有音轨", bool(a)))

    dur = float(probe["format"]["duration"])
    target = episode["target_duration_sec"]
    checks.append(check("duration.target", abs(dur - target) <= target * 0.25,
                        f"{target}s ±25%", round(dur, 2), warn=True))
    tl_s = timeline["total_duration_ms"] / 1000
    vdur = float(v.get("duration", dur))
    adur = float(a.get("duration", dur)) if a else 0
    checks.append(check("sync.av_duration", abs(vdur - adur) <= 0.1, "音视频时长差 ≤100ms",
                        f"{abs(vdur - adur) * 1000:.0f}ms"))
    checks.append(check("sync.timeline", abs(vdur - tl_s) <= 0.1, "视频时长 = audio_timeline ±100ms",
                        f"{abs(vdur - tl_s) * 1000:.0f}ms"))

    ep_ids = [c["cue_id"] for c in episode["cues"]]
    tl_ids = [c["cue_id"] for c in timeline["cues"]]
    mf_ids = [s["cue_id"] for s in manifest["shots"]]
    checks.append(check("timeline.cues_match", ep_ids == tl_ids == mf_ids, "episode/timeline/manifest 句子一致",
                        f"{len(ep_ids)}/{len(tl_ids)}/{len(mf_ids)}"))
    overlaps = [c["cue_id"] for p, c in zip(timeline["cues"], timeline["cues"][1:]) if c["start_ms"] < p["end_ms"]]
    checks.append(check("timeline.no_overlap", not overlaps, "无重叠", overlaps or "无"))

    lufs, peak = _loudness(video)
    checks.append(check("audio.loudness", lufs is not None and abs(lufs + 16) <= 1.0, "-16±1 LUFS", lufs))
    checks.append(check("audio.peak", peak is not None and peak <= -1.0, "≤ -1.0 dBFS", peak))
    blacks = _black_segments(video)
    checks.append(check("video.black_frames", not blacks, "无 ≥0.5s 黑场", blacks or "无"))

    # 每个词出现 3 次英文（教学结构）
    for i, w in enumerate(episode["words"]):
        n = sum(1 for c in episode["cues"] if c["lang"] == "en" and c["word_index"] == i and c["section"] == "word")
        checks.append(check(f"pedagogy.repeat.{w['en']}", n >= 3, "≥3 次英文", n))
        practice = [c for c in episode["cues"] if c["lang"] == "en" and c["word_index"] == i
                    and c["section"] == "word" and c["repeat_prompt"] and c["pause_after_ms"] >= 1200]
        checks.append(check(f"pedagogy.pause.{w['en']}", bool(practice), "有 ≥1200ms 跟读停顿", bool(practice)))
    checks.append(check("pedagogy.review", any(c["section"] == "review" for c in episode["cues"]), "有复习段", True))

    # 素材权利门禁
    registry = load_json(LEGAL / "rights_registry.json")
    validate(registry, "rights_registry")
    reg = {s["asset_source"]: s for s in registry["sources"]}
    used = {c["asset_source"] for c in timeline["cues"]}
    used |= {s["asset_source"] for s in timeline.get("sfx", [])}
    if timeline.get("bgm"):
        used.add(timeline["bgm"]["asset_source"])
    used |= {a["asset_source"] for a in manifest["assets"]}
    blockers = []
    for src in sorted(used):
        entry = reg.get(src)
        ok = bool(entry and entry["commercial_ok"])
        checks.append(check(f"rights.{src}", ok, "台账登记且可商用",
                            (entry or {}).get("license", "未登记"), (entry or {}).get("notes", "")))
        if not ok:
            blockers.append(f"素材来源 {src} 未登记或不可商用")

    status = "FAIL" if any(c["status"] == "FAIL" for c in checks) else (
        "WARN" if any(c["status"] == "WARN" for c in checks) else "PASS")
    tech_fail = [c["rule_id"] for c in checks if c["status"] == "FAIL" and not c["rule_id"].startswith("rights.")]
    blockers = [f"技术检查未通过：{r}" for r in tech_fail] + blockers
    report = {
        "schema_version": "1.0", "episode_id": episode["episode_id"], "status": status,
        "publishable": not blockers, "checked_on": date.today().isoformat(),
        "video": str(video), "checks": checks, "blockers": blockers,
    }
    validate(report, "qc_report")
    return dump_json(out_dir / "qc_report.json", report)
