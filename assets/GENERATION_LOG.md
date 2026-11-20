# 图片生成记录

- 来源清单：`episodes/ep_colors_red-blue-yellow/asset_plan.json`（13 项，各生成 1 张）。
- 生成工具：Codex 内置 `image_gen__imagegen`；每张独立调用一次，共 13 次。
- 角色参考：`assets/ollie/concepts/ollie_A.png`；除 `idle` 外的 6 个姿势还参考已生成的 `assets/characters/ollie/idle.png`。
- 后处理：仅用 Pillow 将 12 张角色/物体图中已生成的近似绿幕/品红背景像素归一化为指定 RGB 色值；不抠图、不生成透明通道，不处理背景图。清单 `post` 的抠图步骤按本次明确要求跳过。

| 路径 | 尺寸（px） | 提示词摘要 | 生成工具 |
|---|---:|---|---|
| `assets/characters/ollie/idle.png` | 1199×1312 | 设定稿 A 的奥利；新增红色粗针织围巾；全身三分之四视角，放松站姿、轻微微笑；#00FF00 绿幕 | 内置 `image_gen__imagegen` |
| `assets/characters/ollie/wave.png` | 1199×1312 | 同一奥利与围巾；右爪高举挥手、开心张嘴；全身留白、#00FF00 绿幕 | 内置 `image_gen__imagegen` |
| `assets/characters/ollie/jump.png` | 1199×1312 | 同一奥利与围巾；双爪上举、双脚离地跳跃；全身留白、#00FF00 绿幕 | 内置 `image_gen__imagegen` |
| `assets/characters/ollie/clap.png` | 1199×1312 | 同一奥利与围巾；胸前双爪拍手、欣喜表情；全身留白、#00FF00 绿幕 | 内置 `image_gen__imagegen` |
| `assets/characters/ollie/point.png` | 1199×1312 | 同一奥利与围巾；朝画面右侧伸爪指、看向右侧；全身留白、#00FF00 绿幕 | 内置 `image_gen__imagegen` |
| `assets/characters/ollie/nod.png` | 1199×1312 | 同一奥利与围巾；轻微点头、半闭眼、满足微笑；全身留白、#00FF00 绿幕 | 内置 `image_gen__imagegen` |
| `assets/characters/ollie/listen.png` | 1199×1312 | 同一奥利与围巾；右爪拢耳倾听、扬眉；全身留白、#00FF00 绿幕 | 内置 `image_gen__imagegen` |
| `assets/objects/colors/red.png` | 1536×1024 | 单个居中的红色圆形黏土团，顶部小滴状凸起；#00FF00 绿幕 | 内置 `image_gen__imagegen` |
| `assets/objects/colors/blue.png` | 1536×1024 | 单个居中的蓝色圆形黏土团，顶部小滴状凸起；#00FF00 绿幕 | 内置 `image_gen__imagegen` |
| `assets/objects/colors/yellow.png` | 1536×1024 | 单个居中的黄色圆形黏土团，顶部小滴状凸起；#00FF00 绿幕 | 内置 `image_gen__imagegen` |
| `assets/objects/colors/green.png` | 1536×1024 | 单个居中的绿色圆形黏土团，顶部小滴状凸起；#FF00FF 品红背景 | 内置 `image_gen__imagegen` |
| `assets/objects/colors/orange.png` | 1536×1024 | 单个居中的橙色圆形黏土团，顶部小滴状凸起；#00FF00 绿幕 | 内置 `image_gen__imagegen` |
| `assets/backgrounds/colors_portrait.png` | 941×1672 | 近 9:16 竖版黏土定格动画风格；晴朗草地、太阳与云；中下部留空供角色和词卡合成；无绿幕 | 内置 `image_gen__imagegen` |
