#!/usr/bin/env python3
"""生成作品画廊 HTML 页面：列出 episodes/ 下所有已发布的集数。

输出：gallery/index.html（静态页面，风格温暖、适合幼儿家长）
"""
from pathlib import Path
import json
from datetime import datetime

ROOT = Path(__file__).parent.parent
EPISODES = ROOT / "episodes"
GALLERY = ROOT / "gallery"
GALLERY.mkdir(exist_ok=True)

def get_episode_info(ep_dir: Path) -> dict | None:
    """读取单个 episode 的信息。"""
    try:
        episode = json.loads((ep_dir / "episode.json").read_text())
        timeline = json.loads((ep_dir / "audio_timeline.json").read_text())
        qc = json.loads((ep_dir / "qc_report.json").read_text())

        # 获取视频文件
        video_path = None
        for f in ep_dir.glob("*.mp4"):
            video_path = f.name
            break

        return {
            "id": episode["episode_id"],
            "theme_zh": episode.get("theme_zh", ""),
            "theme_en": episode.get("theme_en", ""),
            "character": episode.get("character", ""),
            "words": episode.get("words", []),
            "duration_sec": round(timeline.get("total_duration_ms", 0) / 1000, 2),
            "target_duration_sec": episode.get("target_duration_sec", 60),
            "status": qc.get("status", "UNKNOWN"),
            "publishable": qc.get("publishable", False),
            "video": video_path,
            "aspect": episode.get("aspect", "portrait"),
            "preview_frame": f"{ep_dir.name}/preview/frame_00000.png" if (ep_dir / "preview" / "frame_00000.png").exists() else None,
        }
    except Exception as e:
        print(f"⚠ 读取 {ep_dir.name} 失败: {e}")
        return None

def build_html(episodes: list[dict]) -> str:
    """生成 HTML 页面。"""
    html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>奥利的英语课堂 - 作品集</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
            background: linear-gradient(135deg, #f9f4ef 0%, #fdf9f5 100%);
            color: #4a3728;
            line-height: 1.6;
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        header {
            text-align: center;
            margin-bottom: 50px;
            padding-top: 30px;
        }
        header h1 {
            font-size: 2.5em;
            color: #c8694c;
            margin-bottom: 10px;
            text-shadow: 1px 1px 2px rgba(200, 105, 76, 0.1);
        }
        header .tagline {
            font-size: 1.1em;
            color: #8b6f47;
            font-weight: 300;
        }
        .episodes-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 25px;
            margin-bottom: 40px;
        }
        .episode-card {
            background: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
            transition: transform 0.2s, box-shadow 0.2s;
            cursor: pointer;
        }
        .episode-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 8px 16px rgba(0, 0, 0, 0.12);
        }
        .episode-preview {
            width: 100%;
            aspect-ratio: 9/16;
            background: #f0e8e0;
            overflow: hidden;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.9em;
            color: #c8694c;
        }
        .episode-preview img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        .episode-info {
            padding: 20px;
        }
        .episode-id {
            font-size: 0.85em;
            color: #a67c52;
            margin-bottom: 8px;
            font-weight: 500;
        }
        .episode-title {
            font-size: 1.3em;
            color: #4a3728;
            margin-bottom: 12px;
            font-weight: 600;
        }
        .episode-meta {
            display: flex;
            gap: 15px;
            font-size: 0.95em;
            margin-bottom: 12px;
            flex-wrap: wrap;
        }
        .meta-item {
            display: flex;
            align-items: center;
            gap: 4px;
        }
        .meta-label {
            color: #8b6f47;
            font-weight: 500;
        }
        .meta-value {
            color: #6b5a3d;
        }
        .words-list {
            margin-bottom: 12px;
        }
        .words-title {
            font-size: 0.9em;
            color: #8b6f47;
            font-weight: 500;
            margin-bottom: 6px;
        }
        .words-items {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }
        .word-badge {
            background: linear-gradient(135deg, #fff4e6 0%, #ffebd5 100%);
            border: 1px solid #f0d9c4;
            padding: 4px 10px;
            border-radius: 16px;
            font-size: 0.85em;
            color: #c8694c;
            font-weight: 500;
        }
        .status-badge {
            display: inline-block;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 600;
            margin-bottom: 12px;
        }
        .status-pass {
            background: #e8f5e9;
            color: #2e7d32;
        }
        .status-warn {
            background: #fff3e0;
            color: #e65100;
        }
        .status-fail {
            background: #ffebee;
            color: #c62828;
        }
        .watch-button {
            display: block;
            width: 100%;
            padding: 10px;
            background: linear-gradient(135deg, #f0a89e 0%, #d9816d 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 0.95em;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.1s;
            text-decoration: none;
            text-align: center;
        }
        .watch-button:hover {
            transform: scale(1.02);
        }
        .watch-button:disabled {
            background: #ccc;
            cursor: not-allowed;
            opacity: 0.6;
        }
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #8b6f47;
        }
        .empty-state-icon {
            font-size: 4em;
            margin-bottom: 20px;
        }
        footer {
            text-align: center;
            padding: 30px 20px;
            color: #8b6f47;
            border-top: 1px solid #e8dfd5;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🦦 奥利的英语课堂</h1>
            <p class="tagline">一句话 → 一支幼儿英语定格动画短视频</p>
        </header>

        <div class="episodes-grid">
'''

    for ep in episodes:
        status_class = "status-pass" if ep["publishable"] else ("status-warn" if ep["status"] == "WARN" else "status-fail")
        status_text = "可发布" if ep["publishable"] else ("需改进" if ep["status"] == "WARN" else "待修改")

        words_html = ""
        if ep["words"]:
            words_html = f'''
            <div class="words-list">
                <div class="words-title">词汇（{len(ep["words"])}个）</div>
                <div class="words-items">
'''
            for word in ep["words"][:5]:  # 只显示前5个
                words_html += f'                    <span class="word-badge">{word.get("en", "?")}</span>\n'
            if len(ep["words"]) > 5:
                words_html += f'                    <span class="word-badge">+{len(ep["words"]) - 5}</span>\n'
            words_html += '                </div>\n            </div>'

        watch_btn = ""
        if ep["video"]:
            watch_btn = f'<a href="/{ep["id"]}/{ep["video"]}" class="watch-button" target="_blank">▶ 观看视频</a>'
        else:
            watch_btn = '<button class="watch-button" disabled>尚无视频</button>'

        preview_html = ""
        if ep["preview_frame"]:
            preview_html = f'<img src="/{ep["preview_frame"]}" alt="{ep["theme_zh"]}">'
        else:
            preview_html = '<div style="display: flex; align-items: center; justify-content: center; height: 100%; color: #c8694c;">🎬 预览图</div>'

        html += f'''        <div class="episode-card">
            <div class="episode-preview">
                {preview_html}
            </div>
            <div class="episode-info">
                <div class="episode-id">Episode #{ep["id"].split("_")[1] if "_" in ep["id"] else "1"}</div>
                <div class="episode-title">{ep["theme_zh"]} · {ep["theme_en"].capitalize()}</div>
                <div class="status-badge {status_class}">{status_text}</div>
                <div class="episode-meta">
                    <div class="meta-item">
                        <span class="meta-label">⏱</span>
                        <span class="meta-value">{ep["duration_sec"]}s</span>
                    </div>
                    <div class="meta-item">
                        <span class="meta-label">🎯</span>
                        <span class="meta-value">{ep["target_duration_sec"]}s 目标</span>
                    </div>
                </div>
                {words_html}
                {watch_btn}
            </div>
        </div>
'''

    html += '''        </div>

        <footer>
            <p>🦦 由 KES（Kids English Studio）自动生成 | 最后更新：{}</p>
        </footer>
    </div>
</body>
</html>
'''.format(datetime.now().strftime("%Y-%m-%d %H:%M"))

    return html

if __name__ == "__main__":
    # 扫描 episodes 目录
    episodes = []
    for ep_dir in sorted(EPISODES.iterdir()):
        if ep_dir.is_dir() and not ep_dir.name.startswith("_"):
            info = get_episode_info(ep_dir)
            if info:
                episodes.append(info)

    # 生成 HTML
    html = build_html(episodes)
    output = GALLERY / "index.html"
    output.write_text(html)
    print(f"✓ 生成 {output}，包含 {len(episodes)} 集作品")
