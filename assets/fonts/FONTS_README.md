# 开源字体安装说明

本项目使用 SIL OFL 许可的开源字体，以支持商业用途。

## 所需字体

### 中文：思源黑体 Source Han Sans SC Bold
- 许可证：SIL Open Font License 1.1
- 下载地址：https://github.com/adobe-fonts/source-han-sans/releases/download/2.004R/SourceHanSansSC.zip
- 文件名：`zh.otf` 或 `zh.ttf`
- 安装步骤：
  1. 下载上述 ZIP 文件
  2. 解压，找到 `OTF/SimplifiedChinese/SourceHanSansSC-Bold.otf`
  3. 重命名为 `zh.otf` 并复制到本目录

### 英文：Nunito Bold
- 许可证：SIL Open Font License 1.1
- 下载地址：https://github.com/google/fonts/raw/main/ofl/nunito/static/Nunito-Bold.ttf
- 文件名：`en.ttf` 或 `en.otf`
- 安装步骤：
  1. 下载上述 TTF 文件
  2. 重命名为 `en.ttf` 并保存到本目录

## 验证安装

运行以下命令验证字体是否正确安装：

```bash
python3 << 'EOF'
from PIL import ImageFont
from pathlib import Path

fonts = {
    "zh": "zh.otf",
    "en": "en.ttf"
}

for name, file in fonts.items():
    path = Path(__file__).parent / file
    try:
        font = ImageFont.truetype(str(path), 32)
        print(f"✓ {name}: {file}")
    except Exception as e:
        print(f"✗ {name}: {e}")
EOF
```

## 备选方案

如果无法下载字体，系统将自动回退到系统字体，但质检（QC）报告可能会警告字体来源不可商用。

## 许可证

- Source Han Sans: https://github.com/adobe-fonts/source-han-sans/blob/master/LICENSE.txt
- Nunito: https://github.com/google/fonts/blob/main/ofl/nunito/OFL.txt
