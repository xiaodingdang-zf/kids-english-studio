# kids-english-studio（KES）项目说明

一句话 → 自动产出一支幼儿英语定格动画短视频。自研，代码与提示词全部原创（未参考 lemo-animi 的代码/提示词）。

## 架构

```
一句话 ──kes script──▶ episode.json
                         │
                ┌────────┴─────────┐
        kes audio (mock|live)   kes assets → kes fill-assets（批准后生图）
                │
        audio_timeline.json（唯一实测时长源） + master.wav
                │
        kes render ──▶ frames_manifest.json ──▶ <id>_<mode>.mp4
                │
        kes qc ──▶ qc_report.json（技术 + 教学结构 + 权利门禁）
```

- **宿主 agent（Codex/Claude，经 SKILL.md）**：需要大模型的部分——润色台词、生图。
- **Python CLI**：确定性部分——解析、配音调度、排帧、合成、混音、质检。

## 模块与分工（群聊定稿）

| 模块 | 路径 | 负责 |
|---|---|---|
| CLI / 编排 / 脚本生成 / SKILL.md | `kes/cli.py`, `kes/core/` | Claude |
| 生图清单 / 黏土绘制 / 渲染引擎 | `kes/visual/` | Codex |
| 配音适配 / 配乐音效 / 混音 | `kes/audio/` | Gemini |
| 自动 QC / 权利台账 / 合规 | `kes/qc/`, `legal/`, `compliance/` | Minimax |

v0.1 由 Antigravity 按以上接口一次性实现，后续迭代按模块分给各 agent（Agent Team Hub 开发模式，project_dir 填本目录）。

## 接口（JSON Schema 在 `kes/schemas/`）
- `episode.json`：`episode_id, theme, character, aspect, style（缺省 clay）, target_duration_sec, words[], cues[{cue_id, section, lang, text, pause_after_ms, action, word_index, show_card, repeat_prompt}]`。不含实测时长。
- `audio_timeline.json`：`total_duration_ms, master, lufs, peak_db, bgm, sfx[], cues[{cue_id, lang, voice_id, start_ms, end_ms, pause_after_ms, asset_source}]`。
- `frames_manifest.json`：`width, height, fps=24, anim_fps=12, total_frames, shots[{camera: static|push_in|pull_out|pan, ...}], assets[]`。
- `qc_report.json`：`status, publishable, checks[{rule_id, status, expected, actual, evidence}], blockers[]`。
- `legal/rights_registry.json`：每个 `asset_source` 的许可、是否可商用、凭证。

## 门禁
- live 配音必须 `--allow-paid`（否则 `PaidCallBlocked`）。KES 不读密钥，密钥由 wanwu-pipeline 在计费请求路径中读取。
- `kes fill-assets <episode>` 默认只报告缺图项数与预计生图张数；传入足额 `--approve N` 后才通过 `codex exec` 逐张补图。live 缺图时 `kes make` 停止，不静默用占位图。
- QC：权利未登记或不可商用 → FAIL / 不可发布。mock 语音、系统字体默认不可发布。

## 风格包与镜头（K4）
- 风格配置位于 `styles/<style_id>/style.json`，由 `styles/style.schema.json` 校验；现有 `clay` 与 `felt`。一句话含“羊毛毡”或 `felt` 时选 `felt`，其他默认 `clay`。非 clay 的 episode ID 带风格后缀，避免覆盖已有同词集。
- `kes assets` 的提示词与资源路径按风格切换；clay 沿用旧资源路径，felt 使用 `assets/styles/felt/`。配乐使用风格包的 `music_config`，拟音按 `cue.action` 触发。
- mock 的 felt 为程序化颗粒/短绒毛占位。镜头按 12fps 离散步进；单词卡镜头轻微物体近景，整帧使用风格包调色参数与暗角。

## 动作表与近景表（K3）
- 每个角色动作可用 2×4 绿幕连续帧表，`kes slice` 生成 `characters/<角色>/<动作>/000.png`–`007.png`；2×2 近景表生成 `closeup/happy.png` 等四种表情。切帧会抠绿幕、统一透明尺寸并对齐底部。
- 渲染优先在 12fps 动作帧间循环；单词卡/跟读优先近景；缺序列时回退单张素材。`assets/ASSET_SOURCES.json` 记录每张切出帧的来源。

## 采样配乐与拟音（K5b）
- `styles/*/style.json` 的 `music_config` 指定调式、BPM、乐器；`kes/audio/music.py` 用 VSCO 2 CE 竖琴真实录音编排原创和弦、旋律、低音，按人声能量自动闪避。采样不全或损坏时回退 `kes/audio/synth.py`，时轴如实登记来源。
- VSCO 2 Community Edition 官方下载：https://github.com/sgossner/VSCO-2-CE ，许可证 [CC0-1.0](https://github.com/sgossner/VSCO-2-CE/blob/master/LICENSE)，允许商用。下载脚本 `scripts/fetch_samples.sh` 默认存到 `~/kes-env/samples`（不进仓库）；受限开发环境可设 `KES_SAMPLE_DIR="$PWD/samples"`，项目内 `samples/` 已 gitignore。
- `kes/audio/foley.py` 按 `cue.action` 加卡片、跳起落地、拍手、物体出现等代码合成拟音；没有外部拟音库。配乐及拟音权利来源见 `legal/rights_registry.json`。
- 英文音色 B 的配置位在 `kes/audio/voices.json` 的 `live_en_b`，接口 `EnglishNativeAdapter`；须填写真实音色 ID 并接入支持 `explicit_language=en` 的提供方后才能运行。`--en-voice b` 只在 live 有意义，live 仍需 `--allow-paid`；现有 wanwu 固定 zh，不会被误作 B。

## 测试
```sh
uv run pytest -q
```

## 环境与插件
- `uv run kes doctor`（或 `--json`）只读检查 Python 3.11–3.13、uv、ffmpeg/ffprobe、OFL 字体与可选 VSCO 2 CE 采样；不下载或调用计费 API。
- `sh scripts/setup.sh` 幂等同步锁定依赖并在缺失时下载 CC0 采样；默认写入 `~/kes-env/samples`，可用 `KES_SAMPLE_DIR` 覆盖。
- 根目录是 Codex/Claude Code 插件包；`plugin.json`、`.codex-plugin/plugin.json`、`.claude-plugin/plugin.json` 与 `.claude-plugin/marketplace.json` 提供本地 marketplace 元数据，`skills/kids-english-studio/SKILL.md` 是可安装技能副本。安装命令与许可边界见 `README.md`。

## 已知局限 / 待办（v0.1）
1. mock 画面是代码绘制的黏土/毛毡占位；正式质感依赖 live 生图素材（`kes assets`）。
2. wanwu tts 固定 `explicit_language=zh`；英文 B 已预留配置和适配器接口，真实音色 ID 与英文适配器仍待接入。
3. OFL 字体已放入 `assets/fonts/zh.otf`、`en.ttf`；移动或重新打包时需保持字体文件及其许可记录完整。
4. 主题词库目前 4 个；新增主题在 `kes/core/wordbank.py` 加。
5. 本地审片台已提供逐帧意见、版本视频与意见快照；浏览器实际播放/听感仍需人工验收。离线 HTML 需复制意见交回宿主 agent，不能自动提交。
