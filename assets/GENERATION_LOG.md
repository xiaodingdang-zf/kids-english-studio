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

## 2026-11-20｜数字、动物、水果三集物体与背景（18 张）

- 来源清单：`episodes/ep_numbers_one-two-three_story/asset_plan.json`、`episodes/ep_animals_cat-dog-duck_story/asset_plan.json`、`episodes/ep_fruits_apple-banana-grape_story/asset_plan.json`；仅处理 `kind=object/background`。
- 生成工具：Codex 内置 `image_gen__imagegen`。最终保留 18 张；共调用 22 次，香蕉和葡萄各重生成 2 次，未采用的候选未写入项目。
- 风格参考：已定稿的 `assets/characters/ollie/idle.png` 与 `assets/backgrounds/colors_portrait.png`；物体按原清单提示词生成，背景在原提示词基础上分别细化数字草地、农场草地、果园草地。
- 后处理：仅将 15 张物体图中接近指定绿幕／品红的背景像素归一化为精确 RGB `#00FF00`／`#FF00FF`；不抠图、不生成透明通道；3 张背景图未后处理。

| 集数 | 类型 | 路径 | 尺寸（px） | 内容 |
|---|---|---|---:|---|
| 数字 | object | `assets/objects/numbers/one.png` | 1536×1024 | 1 个彩球 |
| 数字 | object | `assets/objects/numbers/two.png` | 1672×941 | 2 个彩球 |
| 数字 | object | `assets/objects/numbers/three.png` | 1774×887 | 3 个彩球 |
| 数字 | object | `assets/objects/numbers/four.png` | 1536×1024 | 4 个彩球 |
| 数字 | object | `assets/objects/numbers/five.png` | 1672×941 | 5 个彩球 |
| 数字 | background | `assets/backgrounds/numbers_portrait.png` | 941×1672 | 数字草地 |
| 动物 | object | `assets/objects/animals/cat.png` | 1312×1199 | 猫 |
| 动物 | object | `assets/objects/animals/dog.png` | 1536×1024 | 狗 |
| 动物 | object | `assets/objects/animals/duck.png` | 1312×1199 | 鸭 |
| 动物 | object | `assets/objects/animals/fish.png` | 1536×1024 | 鱼 |
| 动物 | object | `assets/objects/animals/bird.png` | 1536×1024 | 鸟 |
| 动物 | background | `assets/backgrounds/animals_portrait.png` | 941×1672 | 动物农场草地 |
| 水果 | object | `assets/objects/fruits/apple.png` | 1312×1199 | 苹果 |
| 水果 | object | `assets/objects/fruits/banana.png` | 1536×1024 | 单根香蕉 |
| 水果 | object | `assets/objects/fruits/grape.png` | 1221×1288 | 葡萄串 |
| 水果 | object | `assets/objects/fruits/pear.png` | 1312×1199 | 梨（#FF00FF 品红底） |
| 水果 | object | `assets/objects/fruits/peach.png` | 1312×1199 | 桃子 |
| 水果 | background | `assets/backgrounds/fruits_portrait.png` | 941×1672 | 水果果园草地 |

- 验收：18 个清单路径均存在且为 RGB PNG；15 张物体图四角已为指定纯色；3 张背景图均为 941×1672 竖版，留出中下方合成区域；未生成角色动作表或近景表。

## 2026-11-20｜Level 1 家人、身体部位、文具四集（13 张）

- 来源清单：`episodes/ep_level1_u02e1_mum-dad-baby_story/asset_plan.json`、`episodes/ep_level1_u03e1_head-hair-face_story/asset_plan.json`、`episodes/ep_level1_u03e2_eye-ear-nose_story/asset_plan.json`、`episodes/ep_level1_u05e2_book-pen-pencil_story/asset_plan.json`；仅补缺失的 `kind=object/background`。四集共用同一背景路径，按路径去重为 12 张物体图 + 1 张背景图。
- 生成工具：Codex 内置 `image_gen__imagegen`，每张独立调用一次，共 13 次；参考已定稿的 `assets/characters/ollie/idle.png` 与 `assets/backgrounds/colors_portrait.png` 的造型、材质、光线和构图。
- 后处理：仅将 12 张物体图中的近似绿色背景像素统一为精确 RGB `#00FF00`；不抠图、不生成透明通道；背景图未做色彩后处理。

| 类型 | 路径 | 尺寸（px） | 内容 |
|---|---|---:|---|
| object | `assets/objects/curriculum/mum.png` | 1254×1254 | 青绿色围巾的黏土水獭妈妈 |
| object | `assets/objects/curriculum/dad.png` | 1312×1199 | 黄色围巾的黏土水獭爸爸 |
| object | `assets/objects/curriculum/baby.png` | 1254×1254 | 紫色围巾的黏土水獭宝宝 |
| object | `assets/objects/curriculum/head.png` | 1536×1024 | 水獭头部图标 |
| object | `assets/objects/curriculum/hair.png` | 1536×1024 | 棕色黏土发束图标 |
| object | `assets/objects/curriculum/face.png` | 1536×1024 | 水獭面部图标 |
| object | `assets/objects/curriculum/eye.png` | 1536×1024 | 单只眼睛图标 |
| object | `assets/objects/curriculum/ear.png` | 1312×1199 | 单只耳朵图标 |
| object | `assets/objects/curriculum/nose.png` | 1536×1024 | 鼻子图标 |
| object | `assets/objects/curriculum/book.png` | 1312×1199 | 无字封面的黏土书本 |
| object | `assets/objects/curriculum/pen.png` | 1536×1024 | 蓝色圆珠笔 |
| object | `assets/objects/curriculum/pencil.png` | 1536×1024 | 黄色木铅笔 |
| background | `assets/backgrounds/curriculum_portrait.png` | 941×1672 | 共用晴朗黏土草地，中央与下方留白 |

- 验收：13 个唯一清单路径均存在且为 RGB PNG；12 张物体图四边为精确 `#00FF00`，主体完整居中；背景比例接近 9:16，目视无角色或文字；未生成动作表或近景表，也未覆盖既有图片。

## 2026-11-20｜Level 1 嘴与身体、教室、食物、房间四集物体（12 张）

- 来源：用户指定的 4 份 `asset_plan.json`；仅补 12 个此前不存在的 `kind=object` 路径。共用背景已存在，未生成背景、角色动作表或近景表。
- 工具：Codex 内置 `image_gen__imagegen`，每个物体独立生成一次，共 12 次；参照已定稿的奥利与黏土草地风格，柔和暖光、手工黏土纹理。
- 后处理：仅将近似绿幕像素统一为精确 RGB `#00FF00`；保留不透明 RGB PNG，未抠图、未生成透明通道。清单中的抠图 `post` 按本次明确要求跳过。

| 路径 | 尺寸（px） | 内容 |
|---|---:|---|
| `assets/objects/curriculum/mouth.png` | 1536×1024 | 红色微笑嘴唇与牙齿 |
| `assets/objects/curriculum/tooth.png` | 1536×1024 | 白色臼齿 |
| `assets/objects/curriculum/hand.png` | 1312×1199 | 张开的五指手掌 |
| `assets/objects/curriculum/bag.png` | 1312×1199 | 黄蓝色儿童书包 |
| `assets/objects/curriculum/desk.png` | 1536×1024 | 木色儿童书桌 |
| `assets/objects/curriculum/chair.png` | 1312×1199 | 红色儿童椅 |
| `assets/objects/curriculum/bread.png` | 1536×1024 | 露出面包瓤的整条面包 |
| `assets/objects/curriculum/rice.png` | 1536×1024 | 蓝碗白米饭 |
| `assets/objects/curriculum/cake.png` | 1312×1199 | 粉白糖霜生日蛋糕 |
| `assets/objects/curriculum/bed.png` | 1536×1024 | 蓝被褥木床 |
| `assets/objects/curriculum/door.png` | 1312×1199 | 木质拱形门 |
| `assets/objects/curriculum/window.png` | 1312×1199 | 四格玻璃窗 |


## 2026-11-20｜Level 1 四集物体词汇（12 张）

- 来源：`ep_level1_u03e4`、`ep_level1_u05e4`、`ep_level1_u06e3`、`ep_level1_u08e4` 的 `asset_plan.json` 中此前缺失的 `kind=object` 条目，共 12 张。
- 工具：Codex 内置 `image_gen__imagegen`；每个物体独立生成一次。参照已定稿奥利及黏土草地的手作黏土定格风格、柔和暖光。
- 后处理：只将近似绿幕色统一为精确 RGB `#00FF00`；保留不透明 RGB PNG，未抠图。按用户本次要求跳过清单中的透明抠图 `post`，未生成背景、角色动作表或近景表。
- 验收：12 张均存在，主体完整居中、无文字水印、无地面阴影；PNG 为 RGB，全部四边像素均为精确 `#00FF00`。

| 路径 | 尺寸（px） | 内容 |
|---|---:|---|
| `assets/objects/curriculum/arm.png` | 1536×1024 | 屈肘的手臂与手掌 |
| `assets/objects/curriculum/leg.png` | 1199×1312 | 带脚的弯曲腿部 |
| `assets/objects/curriculum/foot.png` | 1536×1024 | 单只赤脚与脚趾 |
| `assets/objects/curriculum/ball.png` | 1254×1254 | 红蓝黄拼色球 |
| `assets/objects/curriculum/doll.png` | 1312×1199 | 粉裙棕发玩偶 |
| `assets/objects/curriculum/toy.png` | 1536×1024 | 红色黏土玩具车 |
| `assets/objects/curriculum/tiger.png` | 1536×1024 | 橙黑条纹小老虎 |
| `assets/objects/curriculum/lion.png` | 1312×1199 | 圆鬃毛小狮子 |
| `assets/objects/curriculum/elephant.png` | 1536×1024 | 蓝灰色小象 |
| `assets/objects/curriculum/hat.png` | 1536×1024 | 黄帽红丝带 |
| `assets/objects/curriculum/shoes.png` | 1536×1024 | 一双红色儿童鞋 |
| `assets/objects/curriculum/clothes.png` | 1312×1199 | 蓝色上衣和橙色短裤 |

## 2026-11-20｜Level 1 新增 10 个物体词汇

- 工具：Codex 内置 `image_gen__imagegen`，每张独立调用一次，共 10 次；参考已定稿的奥利角色与 `curriculum_portrait.png` 的手作黏土质感、柔和暖光。
- 后处理：仅将生成图中近似绿色的背景像素归一化为精确 RGB `#00FF00`；保留不透明 RGB PNG，未抠图、未制作透明通道。
- 范围：只新增下列 10 张图；未生成 fish、pear、背景或角色动作表，未改动代码与 episode 文件。

| 路径 | 尺寸（px） | 内容 |
|---|---:|---|
| `assets/objects/curriculum/rabbit.png` | 1046×1504 | 小白兔，粉色内耳 |
| `assets/objects/curriculum/monkey.png` | 1199×1312 | 棕色小猴子，卷尾 |
| `assets/objects/curriculum/egg.png` | 1046×1504 | 单个完整鸡蛋 |
| `assets/objects/curriculum/milk.png` | 1145×1374 | 蓝白色牛奶盒，无文字 |
| `assets/objects/curriculum/table.png` | 1536×1024 | 四腿圆木桌 |
| `assets/objects/curriculum/sofa.png` | 1536×1024 | 粉紫色双人小沙发 |
| `assets/objects/curriculum/coat.png` | 1312×1199 | 珊瑚橘色儿童外套 |
| `assets/objects/curriculum/sister.png` | 1046×1504 | 粉紫蝴蝶结与背心的水獭姐姐 |
| `assets/objects/curriculum/brother.png` | 1046×1504 | 蓝色领巾的水獭哥哥 |
| `assets/objects/curriculum/grandma.png` | 1046×1504 | 圆眼镜与针织披肩的水獭奶奶 |

## 2026-11-27｜账号品牌图（2 张）

- 工具：Codex 内置 `image_gen__imagegen`；头像、横幅各独立生成一次，共 2 次，未生成其他候选。
- 参考：`assets/characters/ollie/idle.png` 为奥利定稿造型；`assets/backgrounds/colors_portrait.png` 为横幅黏土草地风格参考。
- 验收：已目视核对奥利造型、红围巾、白肚皮、胡须、挥手姿态、横幅留白与无可见文字/水印；已检查 PNG 格式和尺寸。未添加后期标题文字。

| 路径 | 尺寸（px） | 内容 |
|---|---:|---|
| `assets/branding/avatar_raw.png` | 1254×1254 | 暖黄黏土底、奥利胸像挥手头像，圆形裁切安全留白 |
| `assets/branding/banner_raw.png` | 1536×1024 | 黏土草地横幅；奥利位于右侧，含苹果、蓝书、彩球、小猫，左侧留白 |

## 2026-11-27｜颜色、数字与课程物体（12 张）

- 工具：Codex 内置 `image_gen__imagegen`；12 张各独立生成一次。颜色球参照已有红色黏土球，数字球参照已有数字素材的黏土球纹理与排列，课程物体参照奥利的手作黏土风格。
- 后处理：仅将生成图的近似绿色背景统一为不透明 RGB `#00FF00`；未抠图、未生成透明通道，未改代码或 episode 文件。
- 验收：逐张目视检查主体完整居中、无可见文字或水印、无地面阴影；检查 12 张 PNG 四角均为精确 `#00FF00`。数字球逐张计数如下。

| 路径 | 尺寸（px） | 内容／目视计数 |
|---|---:|---|
| `assets/objects/colors/purple.png` | 1536×1024 | 1 颗紫色圆形黏土球，顶端小水滴尖 |
| `assets/objects/colors/pink.png` | 1536×1024 | 1 颗粉色圆形黏土球，顶端小水滴尖 |
| `assets/objects/colors/brown.png` | 1536×1024 | 1 颗棕色圆形黏土球，顶端小水滴尖 |
| `assets/objects/colors/white.png` | 1536×1024 | 1 颗白色圆形黏土球，顶端小水滴尖 |
| `assets/objects/colors/black.png` | 1536×1024 | 1 颗黑色圆形黏土球，顶端小水滴尖 |
| `assets/objects/numbers/six.png` | 1536×1024 | 目视 6 颗：上排 3、下排 3；无绿色球 |
| `assets/objects/numbers/seven.png` | 1672×941 | 目视 7 颗：上排 3、下排 4；无绿色球 |
| `assets/objects/numbers/eight.png` | 1672×941 | 目视 8 颗：上排 4、下排 4；无绿色球 |
| `assets/objects/numbers/nine.png` | 1536×1024 | 目视 9 颗：上中下各 3；无绿色球 |
| `assets/objects/numbers/ten.png` | 1672×941 | 目视 10 颗：上排 5、下排 5；无绿色球 |
| `assets/objects/curriculum/box.png` | 1536×1024 | 1 个黏土礼物盒 |
| `assets/objects/curriculum/watch.png` | 1672×941 | 1 块黏土儿童手表，表盘无数字 |

## Batch 7 Curriculum Clay Objects (18 items, 2026-11-27)
- Generator: `openai:image_gen` via Codex (`assets/_raw/objects/curriculum/*.png` -> `kes cutout`)
- Files:
  - `assets/objects/curriculum/hello.png`, `hi.png`, `goodbye.png`
  - `assets/objects/curriculum/friend.png`, `boy.png`, `girl.png`
  - `assets/objects/curriculum/grandpa.png`, `family.png`, `love.png`
  - `assets/objects/curriculum/school.png`, `classroom.png`, `teacher.png`
  - `assets/objects/curriculum/water.png`, `eat.png`, `drink.png`
  - `assets/objects/curriculum/home.png`, `house.png`, `room.png`
