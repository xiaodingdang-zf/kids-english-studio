# Kids English Studio (KES)

一句话生成原创幼儿英语启蒙定格动画短片：问卷 → 故事化脚本 → 配音与配乐 → 画面 → QC。工作流程与计费门禁见 [SKILL.md](SKILL.md)，架构见 [PROJECT.md](PROJECT.md)。

## 本地准备

需要 Python 3.11–3.13、[`uv`](https://docs.astral.sh/uv/)、`ffmpeg`/`ffprobe`。在项目根目录运行：

```sh
sh scripts/setup.sh
uv run kes doctor
```

`setup.sh` 幂等同步 `uv.lock` 依赖，并在缺失时从 VSCO 2 CE 官方仓库下载 CC0 竖琴采样到 `~/kes-env/samples`；可用 `KES_SAMPLE_DIR` 改路径。脚本不调用 TTS、生图或付费 API。若只想检查、不下载，直接运行 `uv run kes doctor`；缺采样只会让配乐回退程序合成。开源字体放在 `assets/fonts/`，具体文件和来源见 [字体说明](assets/fonts/FONTS_README.md)。

## Codex 插件

项目根目录同时是插件根目录。克隆或复制本项目后，在项目根目录运行（会登记/安装到本机插件配置，请自行执行）：

```sh
codex plugin marketplace add "$PWD" && codex plugin add kids-english-studio@kes-local
```

插件元数据是 `plugin.json` 和 `.codex-plugin/plugin.json`；Codex 兼容读取 `.claude-plugin/marketplace.json`。新会话中说“用 kids-english-studio 给 4 岁孩子做一支认识红蓝黄的 60 秒方形定格动画”，宿主 agent 会按技能流程先问齐参数并执行；正式素材与计费步骤须另行批准。插件安装不会自动执行 `setup.sh`。

## Claude Code 插件

在项目根目录运行：

```sh
claude plugin marketplace add "$PWD" && claude plugin install kids-english-studio@kes-local
```

`.claude-plugin/plugin.json` 与 `.claude-plugin/marketplace.json` 符合 Claude Code 的本地插件布局。新会话可用 `/kids-english-studio:kids-english-studio`，或自然语言说“用 kids-english-studio 做一支幼儿英语颜色词定格动画”。仅做格式检查可运行 `claude plugin validate .`；无需登录或安装。

## 许可证与素材

KES 代码和提示词为自研；**本仓库目前未指定代码开源许可证**，不能据此推定有再分发或商用授权。素材分别遵循自己的许可：VSCO 2 CE 采样为 CC0-1.0，开源字体为 SIL OFL 1.1；每类素材的来源、商用状态与凭证以 [`legal/rights_registry.json`](legal/rights_registry.json) 为准。`mock` 系统语音、未登记素材和未完成 QC 的产物不等于可发布成片。不要照搬出版教材内容。

开发验证：`uv run pytest -q`。不要对 `episodes/ep_colors_red-blue-yellow` 运行 `kes audio`，以免覆盖正式配音时间轴。
