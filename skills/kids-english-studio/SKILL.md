---
name: kids-english-studio
description: 把一句话做成幼儿英语启蒙定格动画；先一次问齐，再生成原创故事化脚本、音频、预览、视频和 QC 报告。
---

# KES 宿主 agent 对话流程

项目根目录：插件安装后的根目录，或本仓库根目录（含 `pyproject.toml` 和 `PROJECT.md`）。在该目录执行以下 `uv run kes ...` 命令；先运行 `sh scripts/setup.sh` 安装本地依赖和 CC0 采样（会下载到 `~/kes-env/samples`，或 `KES_SAMPLE_DIR` 指定处）。只使用自研脚本和已登记素材，不复制出版教材台词。

## 1. 环境检查

读 `PROJECT.md`，运行 `uv run kes doctor` 确认 Python、`uv`、`ffmpeg` / `ffprobe`、字体与采样状态；开发时运行 `uv run pytest -q`。先检查目标 episode 路径：`kes script` 会写入同名 `episode.json`；若已存在用户修改过的文件，先保留副本并征求覆盖同意。**不要**在 `episodes/ep_colors_red-blue-yellow` 运行 `kes audio`，该目录含正式小何配音时间轴。测试使用新 episode 或测试假音频。环境受限导致 `uv` 缓存不可写时，可设置 `UV_CACHE_DIR="$PWD/.uv-cache"`。

## 2. 一次问齐

```sh
uv run kes questions "<用户的一句话>"
```

标准输出是一个 JSON 对象，含 `parsed`（解析值）、`questions`（尚需确认）、`defaults`（未明确字段的默认值）。每题 `options[0]` 是默认项。一次把所有 `questions` 列给用户，不分多轮追问：风格 clay/felt、时长 60/30/90/120 秒、画幅竖/横/方、旁白中英/纯英、英文音色 A 小何/B 母语、片头片尾有/无。用户可回复“全部默认”。若主题不在词库，命令报错；先请用户明确主题或扩词库，不猜测。

B 音色目前只有接口，没有可用的英文适配器和音色 ID；如用户选择 B，须告知此项尚未接通，不能承诺正式配音。

## 3. 写原创故事化教学脚本

```sh
uv run kes script "<原句>" --answers '全部默认'
uv run kes script "<原句>" --answers '{"style":"felt","duration_sec":90,"aspect":"square","narration":"english","en_voice":"a","opening_closing":false}'
```

答案键为 `style` (`clay|felt`)、`duration_sec` (`30|60|90|120`)、`aspect` (`portrait|landscape|square`)、`narration` (`bilingual|english`)、`en_voice` (`a|b`)、`opening_closing` (`true|false`)；可只传用户改动的键。`episode.json` 的 `options` 保存生效值。默认脚本含原创小情境：奥利遇到问题 → 每个目标词推进情节 → 解决问题；在此过程中保留引入、每词至少三次英文、跟读停顿、复习和片尾。`story` cue 可供宿主 agent 润色；只改 `cues[].text`，不删教学 cue，不改 ID、词索引和停顿结构。纯英文选项会去掉中文 cue；无片头片尾会去掉 intro/outro。

先检查生成脚本的词汇、故事连贯性和实际 cue 数；`target_duration_sec` 是目标，不是实测时长。脚本润色后需重新配音、渲染和 QC。

## 4. Live 素材门禁（mock 跳过）

```sh
uv run kes assets <episode_id>
uv run kes fill-assets <episode_id>
```

先向用户报告缺图项、预计生图张数、可能费用和素材权利状态。只有用户**明确批准该张数和计费**后，才运行 `uv run kes fill-assets <episode_id> --approve N`；`N` 不小于缺图项数。该命令会调用生图工具，不能在仅作预览或未获批准时运行。确认素材来源已在权利台账登记，未登记的素材不能当作可发布素材。

## 5. 配音与配乐

mock 预览：`uv run kes audio <episode_id>`。本地 macOS `say` 在沙盒可能产出静音；若报“静音保护”且指出 cue，停止，不拿无声片段继续出片。需要离线验证时用测试里的假音频；不将假音频作为交付。

live 正式音频：先核对未缓存的句数、实际服务价格与本次预算，取得用户**明确计费同意**后才运行 `uv run kes audio <episode_id> --mode live --allow-paid`。英文音色默认读 `episode.options.en_voice`，命令行 `--en-voice a|b` 可覆盖；B 目前不可用。`audio_timeline.json` 是唯一实测时长源；不要以目标时长冒充成片时长。配乐/拟音自动加入，仍须核对版权台账。

## 6. 预览帧与审片确认

配音成功后运行 `uv run kes frames <episode_id> --frames 0,120,360`。检查人物、单词卡、字幕是否完整可读，尤其方形 1080×1080；把预览路径和观察结果发给用户确认。发现问题先修脚本或素材，不直接进入正式渲染。

## 6b. 本地审片台（可选）

先运行 uv run kes render <episode_id> 出片，再用 uv run kes review <episode_id> 启动本地审片台。服务仅监听 127.0.0.1；--port 0 自动分配端口，--timeout 1800 为默认秒数（0 表示无限），--no-open 不自动打开浏览器。

播放器支持空格播放/暂停、左右键逐帧定位，显示时间码、帧号和 cue_id / 镜头。胶片时间轴按 frames_manifest.json 的实际镜头帧界排列，从本地视频抓缩略图；点击跳转，有意见的镜头显示图钉。意见框回车添加当前帧意见，Shift+回车换行；可编辑、删除并查看 agent 回复。

宿主 agent 与用户的闭环：
1. 用户提意见，点「提交给 agent」；进程退出码 2，并在终端列出待改意见。comments.json 保存当前意见，versions.json 保存提交时的意见快照与视频元数据，review/versions/ 保存旧版视频副本。
2. 宿主 agent 读取 review/comments.json，逐条处理；保留原意见 ID，在对应对象下填 agent_reply，说明实际改动或未改理由。
3. 仅重跑受影响的步骤；台词改变才重跑音频、渲染和 QC。不得对 episodes/ep_colors_red-blue-yellow 运行 kes audio；若该集需要改台词，先复制为新 episode 并遵守计费门禁。
4. 新片生成后，运行 uv run kes review <episode_id> --register-version '改动说明'。这会登记当前视频与意见快照，状态变为「可刷新看新版」。
5. 重新运行 uv run kes review <episode_id>，用户复审；可继续提交（退出码 2），或点「通过」（退出码 0）。超时退出码 1。

--export-html <path> 导出离线 HTML：内嵌当前脚本、镜头及意见数据，视频用相对路径。离线新增/修改意见仅在当前页面内，须点「复制意见」把 JSON 交给 agent；离线页面的提交与通过按钮不可用。

## 7. 渲染

`uv run kes render <episode_id>` 生成 MP4。竖屏 1080×1920、横屏 1920×1080、方形 1080×1080；24fps 视频、12fps 动作。实际时长按 `audio_timeline.json`。不要上传或发布。

## 8. QC

`uv run kes qc <episode_id>` 读取 `qc_report.json`。检查分辨率、音画时轴、音量、黑场、每词三次英文、复习和权利登记。`status=PASS` 不等于可发布，仍须看 `publishable` 和 `blockers`；技术检查、权利检查、人工听感/审片分别报告。失败时针对具体 rule 修复并重跑受影响的步骤。

## 9. 交付与修改

交付 `episode.json`、预览帧路径、MP4 路径、实测时长、QC 结论、权利/审片未完成项。请用户审片；修改台词后重新跑 audio → render → qc。审片时推荐用 `kes review` 本地审片台进行逐帧反馈和迭代（见 6b）；若用户需离线或静态导出，可用 `--export-html` 生成纯 HTML。不得声称已发布或已通过人工试听。`kes make` 会串联脚本到 QC，但**不能替代**问卷确认、生图计费批准、live TTS 计费批准和审片，默认不用它跳过门禁。

## 红线

不读取 `~/.codex/plugins/cache/lemomo-ai/`；不读取或打印密钥文件；未经批准不做计费 TTS、生图或付费 API 调用；不覆盖正式小何配音；不照搬教材；不把 mock/假音频宣称为正式成片。
