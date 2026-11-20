"""kes 命令行：一句话 → 幼儿英语定格动画短视频。"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

from .core.common import ASSETS, EPISODES, ROOT, dump_json, load_json, validate
from .core.script_generator import ParseError, generate, ask_questions


def _ep_dir(ref: str) -> Path:
    p = Path(ref)
    if p.is_file():
        return p.parent
    if p.is_dir():
        return p
    if (EPISODES / ref).is_dir():
        return EPISODES / ref
    raise SystemExit(f"找不到这一集：{ref}（可传 episode 目录、episode.json 路径或 episode_id）")


def cmd_questions(a) -> dict:
    try:
        result = ask_questions(a.prompt)
    except ParseError as e:
        raise SystemExit(f"❌ {e}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def cmd_doctor(a) -> dict:
    from .doctor import inspect, render
    report = inspect()
    print(render(report, a.json))
    return report


def cmd_script(a) -> Path:
    try:
        ep = generate(a.prompt, getattr(a, "answers", None))
    except ParseError as e:
        raise SystemExit(f"❌ {e}")
    validate(ep, "episode")
    out = dump_json(EPISODES / ep["episode_id"] / "episode.json", ep)
    print(f"✅ 脚本：{out}（{len(ep['words'])} 个词，{len(ep['cues'])} 句台词）")
    return out


def cmd_audio(a) -> Path:
    from .audio.pipeline import synthesize_audio
    from .audio.tts_adapter import PaidCallBlocked
    d = _ep_dir(a.episode)
    try:
        tl = synthesize_audio(d / "episode.json", d, a.mode, a.allow_paid, not a.no_bgm, a.en_voice)
    except PaidCallBlocked as e:
        raise SystemExit(f"⛔ {e}")
    except ValueError as e:
        raise SystemExit(f"❌ {e}")
    t = load_json(tl)
    print(f"✅ 音频：{d / t['master']}（{t['total_duration_ms'] / 1000:.1f}s，{t['lufs']} LUFS）")
    return tl


def cmd_frames(a) -> Path:
    from .visual.render import render_video
    d = _ep_dir(a.episode)
    frames = [int(x) for x in a.frames.split(",")] if a.frames else [0, 120, 360, 600, 900]
    out = render_video(d / "episode.json", d, preview_frames=frames)
    print(f"✅ 预览帧：{out}")
    return out


def cmd_render(a) -> Path:
    from .visual.render import render_video
    d = _ep_dir(a.episode)
    t0 = time.time()
    out = render_video(d / "episode.json", d)
    print(f"✅ 视频：{out}（渲染 {time.time() - t0:.0f}s）")
    return out


def cmd_qc(a) -> Path:
    from .qc.checker import run_qc
    d = _ep_dir(a.episode)
    rep = load_json(run_qc(d / "episode.json", d))
    print(f"{'✅' if rep['status'] == 'PASS' else '⚠️'} QC：{rep['status']}，可发布={rep['publishable']}")
    for c in rep["checks"]:
        if c["status"] != "PASS":
            print(f"   [{c['status']}] {c['rule_id']}: 期望 {c['expected']}，实际 {c['actual']}")
    return d / "qc_report.json"


def cmd_assets(a) -> list[dict]:
    from .visual.assets_plan import asset_plan, missing_assets
    d = _ep_dir(a.episode)
    plan = asset_plan(load_json(d / "episode.json"))
    out = dump_json(d / "asset_plan.json", {"items": plan})
    missing = missing_assets(plan)
    print(f"📋 生图清单：{out}（共 {len(plan)} 张，缺 {len(missing)} 张）")
    for i in missing:
        print(f"   - {i['kind']}: {i['path']}")
    return missing


def cmd_cutout(a) -> None:
    """去掉纯绿 (#00FF00) 或品红 (#FF00FF) 背景，裁到主体边界，输出透明 PNG。"""
    from .visual.sheets import cutout
    for p in a.images:
        with Image.open(p) as source:
            out = cutout(source, a.key)
        out.save(a.out or p)
        print(f"✅ 抠图：{a.out or p}  {out.size}")


def cmd_slice(a) -> list[Path]:
    from .visual.sheets import EXPRESSIONS, slice_sheet
    names = [f"{name}.png" for name in EXPRESSIONS] if a.grid == "2x2" else None
    paths = slice_sheet(Path(a.sheet), a.grid, Path(a.out), names)
    with Image.open(paths[0]) as first:
        size = first.size
    print(f"✅ 切帧：{len(paths)} 张透明 PNG → {a.out}（{size}，脚底对齐）")
    return paths


def cmd_fill_assets(a) -> list[dict]:
    from .visual.assets_plan import asset_plan, missing_assets
    from .visual.sheets import EXPRESSIONS, cutout, slice_sheet
    d = _ep_dir(a.episode)
    missing = missing_assets(asset_plan(load_json(d / "episode.json")))
    to_generate = [item for item in missing if not Path(item["path"]).exists()]
    print(f"📋 缺图 {len(missing)} 项；预计生图 {len(to_generate)} 张（动作表/近景表各计 1 张）")
    for item in missing:
        print(f"   - {item['kind']}: {item['path']}")
    if a.approve is None:
        print(f"预览模式；确认后运行 uv run kes fill-assets {a.episode} --approve {len(missing)}")
        return missing
    if a.approve < len(missing):
        raise SystemExit(f"⛔ --approve {a.approve} 小于缺图数 {len(missing)}；未调用生图")
    if not missing:
        return []
    registry_path = ASSETS / "ASSET_SOURCES.json"
    registry = load_json(registry_path) if registry_path.exists() else {}
    concept = ASSETS / "ollie" / "concepts" / "ollie_A.png"
    idle = ASSETS / "characters" / "ollie" / "idle.png"
    for item in missing:
        path = Path(item["path"])
        if not path.resolve().is_relative_to(ASSETS.resolve()):
            raise ValueError(f"素材路径超出 assets/: {path}")
        generated = not path.exists()
        if generated:
            refs = [concept] + ([idle] if idle.exists() and idle != path else [])
            if not concept.exists():
                raise FileNotFoundError(f"缺少造型参考图：{concept}")
            path.parent.mkdir(parents=True, exist_ok=True)
            prompt = (f"Use the OpenAI image generation tool and the reference images to create "
                      f"exactly one original PNG at {path}. "
                      f"{item['prompt']} Save the image file to that path; do not change other files.")
            env = os.environ.copy()
            env["KES_OUTPUT_PATH"] = str(path)  # deterministic local test double; Codex uses the prompt
            subprocess.run(["codex", "exec", "--skip-git-repo-check",
                            *(arg for ref in refs for arg in ("-i", str(ref))), prompt],
                           cwd=ROOT, env=env, check=True)
        if not path.exists():
            raise RuntimeError(f"生图命令完成但没有输出：{path}")
        with Image.open(path) as image:
            image.verify()
        source = "openai:image_gen" if generated else registry.get(str(path.relative_to(ASSETS)), "image:unregistered")
        if "frames" in item:
            names = [f"{name}.png" for name in EXPRESSIONS] if item["grid"] == "2x2" else None
            frames = slice_sheet(path, item["grid"], Path(item["frames"][0]).parent, names)
            for frame in frames:
                registry[str(frame.relative_to(ASSETS))] = source
        elif item["kind"] != "background":
            with Image.open(path) as image:
                cutout(image, "magenta" if "--key magenta" in item["post"] else "green").save(path)
        registry[str(path.relative_to(ASSETS))] = source
        dump_json(registry_path, registry)
        print(f"✅ 已补：{path}")
    return missing


def cmd_make(a) -> None:
    t0 = time.time()
    ep_path = cmd_script(a)
    ns = argparse.Namespace(episode=str(ep_path.parent), mode=a.mode, allow_paid=a.allow_paid,
                            no_bgm=a.no_bgm, en_voice=a.en_voice)
    if a.mode == "live":
        missing = cmd_assets(ns)
        if missing:
            raise SystemExit(f"⛔ live 素材缺 {len(missing)} 项；先运行 uv run kes fill-assets {ep_path.parent}，确认数量后加 --approve N")
    cmd_audio(ns)
    video = cmd_render(ns)
    cmd_qc(ns)
    print(f"🎬 完成：{video}（总用时 {time.time() - t0:.0f}s）")


def cmd_review(a) -> None:
    from .review.server import ReviewState, run_review_server, get_review_html
    d = _ep_dir(a.episode)
    if a.register_version:
        version = ReviewState(d).register_version(a.register_version)
        print(f"✅ 已登记新版 {version['version']}：{version['reason']}")
        return
    if a.export_html:
        out = Path(a.export_html)
        out.parent.mkdir(parents=True, exist_ok=True)
        html = get_review_html(d, out)
        out.write_text(html, encoding="utf-8")
        print(f"✅ 导出纯静态 HTML：{out}")
        return
    exit_code = run_review_server(d, a.port, a.timeout, a.no_open)
    if exit_code == 2:
        comments = ReviewState(d).comments
        print(f"\n📝 待改意见（{d / 'review' / 'comments.json'}）：")
        for c in comments:
            print(f"- 帧 {c['frame']} / {c['cue_id'] or '-'}：{c['text']}")
    elif exit_code == 0:
        print(f"\n✅ 审片通过")
    else:
        print("\n⌛ 审片超时")
    sys.exit(exit_code)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="kes", description="一句话 → 幼儿英语定格动画短视频")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("doctor", help="只读环境自检（不下载、不调用计费 API）")
    s.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    s.set_defaults(fn=cmd_doctor)

    def ep_cmd(name, help_, fn):
        s = sub.add_parser(name, help=help_)
        s.add_argument("episode", help="episode 目录 / episode.json / episode_id")
        s.set_defaults(fn=fn)
        return s

    s = sub.add_parser("questions", help="一句话 → 问卷（字段识别 + 待确认项）")
    s.add_argument("prompt")
    s.set_defaults(fn=cmd_questions)

    s = sub.add_parser("script", help="一句话 → episode.json")
    s.add_argument("prompt")
    s.add_argument("--answers", help="问卷答案 JSON 对象或‘全部默认’")
    s.set_defaults(fn=cmd_script)

    for name, fn in (("make", cmd_make), ("audio", cmd_audio)):
        s = sub.add_parser(name, help="一键出片" if name == "make" else "配音 + 配乐 → audio_timeline.json")
        s.add_argument("prompt" if name == "make" else "episode")
        if name == "make":
            s.add_argument("--answers", help="问卷答案 JSON 对象或‘全部默认’")
        s.add_argument("--mode", choices=["mock", "live"], default="mock")
        s.add_argument("--allow-paid", action="store_true", help="允许计费 TTS（live 必须）")
        s.add_argument("--no-bgm", action="store_true")
        s.add_argument("--en-voice", choices=["a", "b"], default=None,
                       help="live 英文音色方案；B 需填写音色 ID 并接入英文适配器")
        s.set_defaults(fn=fn)

    s = ep_cmd("frames", "渲染几张预览帧", cmd_frames)
    s.add_argument("--frames", help="逗号分隔的帧号")
    ep_cmd("render", "按 audio_timeline 合成视频", cmd_render)
    ep_cmd("qc", "自动质检 + 权利门禁", cmd_qc)
    ep_cmd("assets", "输出 live 模式生图清单", cmd_assets)
    s = ep_cmd("fill-assets", "统计缺图并在明确批准后逐张生图", cmd_fill_assets)
    s.add_argument("--approve", type=int, metavar="N", help="批准的缺图项上限；省略时仅报告")
    s = sub.add_parser("cutout", help="绿幕抠图为透明 PNG")
    s.add_argument("images", nargs="+")
    s.add_argument("--out")
    s.add_argument("--key", choices=["green", "magenta"], default="green")
    s.set_defaults(fn=cmd_cutout)
    s = sub.add_parser("slice", help="2x4 动作表或 2x2 近景表切帧、抠图、对齐")
    s.add_argument("sheet", help="网格 PNG")
    s.add_argument("--grid", choices=["2x4", "2x2"], required=True)
    s.add_argument("--out", required=True, help="透明 PNG 输出目录")
    s.set_defaults(fn=cmd_slice)

    s = ep_cmd("review", "本地审片台：视频播放 + 意见反馈", cmd_review)
    s.add_argument("--port", type=int, default=0, help="HTTP 服务端口（0 = 自动分配）")
    s.add_argument("--timeout", type=int, default=1800, help="超时秒数（0 = 无限）")
    s.add_argument("--no-open", action="store_true", help="不自动打开浏览器")
    s.add_argument("--export-html", metavar="PATH", help="导出纯静态 HTML（不启动服务）")
    s.add_argument("--register-version", metavar="REASON", help="改片后登记新版与当前意见快照（不启动服务）")

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main(sys.argv[1:])
