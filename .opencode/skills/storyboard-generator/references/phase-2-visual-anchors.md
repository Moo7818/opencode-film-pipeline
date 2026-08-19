# 阶段二：episode_storyboard_images — 视觉锚点图绘制（visual_anchor 模式）

**默认阶段（当 `meta_query(scope=config)` 返回的 `config.reference_image_mode=visual_anchor` 或未设置时执行）**：此阶段在 `episode_storyboard_script`、`episode_character_ref`、`episode_prop_ref`、`episode_scene_ref` 之后执行，按角色阶段为每场生成视觉锚点图。`reference_image_mode=none` 时跳过此阶段，video-director 仅以角色/场景/道具参考图为参考素材。

> **独立 Agent session 执行**：本文档的所有工作必须在 fresh context 中完成。不得继承阶段一（分镜脚本创作）的对话上下文——阶段一的多轮创作思考会稀释对 prompt 模板格式的注意力。Agent 仅从磁盘读取：组{N}.json/md、参考图目录；配置（`reference_image_mode` 等）经 `meta_query(scope=config)` 读取。
>
> **两种模式均支持视觉锚点绘制**。详细模式从 `组{N}.json` 读取，精简模式从 `组{N}.md` 读取。
>
> **生成方式：sequential 模式** — 场内阶段串行（同场角色阶段按 `depends_on` 链串行，前阶段输出作为后阶段空间参考），场间并行。当一场中无具名角色入场/离场时，该场仅一张锚点图（等价于无阶段拆分）。
>
> 目标是为每个角色阶段锁定**场景空间、氛围基调、人物站位与关键动作神态**，使该阶段覆盖的镜头在后续视频生成阶段共享该锚点作为空间与视觉一致性参考。锚点图不是「帧级分镜」，而是「阶段级视觉定调」——但仍须保持影视级静帧质感，包含完整的角色动作与神态描述。
>
> | 规则 | 说明 |
> |------|------|
> | mode | `"sequential"`，场内阶段串行，场间并行 |
> | 场 | = 物理空间连续单元（与分镜脚本 `场号` 一致） |
> | 数量 | 每个角色阶段一张锚点图；无具名角色入场/离场时每场一张 |
> | 依赖 | 同场阶段间 `depends_on` 串行（前阶段输出→后阶段空间参考）；场间无依赖，可并行 |
> | 共享 | 同阶段覆盖的镜头在视频生成阶段引用同一张锚点图 |
>
> **目标模型**：`nano-banana-2`，2K 分辨率。画面比例固定 `16:9`。Prompt 使用 **English control shell + 中文 content layer**：英文只负责模型控制，中文保留分镜与设定的内容事实。

### 双语 Prompt 分工（visual_anchor 专用）

Prompt 不是“整体英文翻译”，而是用英文结构包裹中文叙事内容。以下分工必须贯穿 OPENING、SCENE CONTINUITY、REFERENCE IMAGE MAPPING、FRAME DETAIL、TEXT POLICY、CINEMATIC QUALITY 和 AVOID：

- **English control layer**：段落标题、`IDENTITY LOCK`、`Reference priority`、身份/连续性硬约束、优先级关系、单帧声明、构图/摄影/镜头/灯光/材质/画质/风格质感、技术质量要求、负面约束。
- **中文 content layer**：来自分镜和设定的角色名与角色关系、场景名与空间内容、动作、站位、神态、台词相关内容、道具内容、时代事实和剧情事实。不得为了“英文 prompt”翻译这些内容，也不得在翻译时顺便重写角色外貌。
- **绑定写法**：先写参考图，再写职责或角色名；例如 `Reference Image 1 character（掌柜角色）站在右侧柜台后擦拭茶杯。`。这表示动作施加在参考图中的已锁定人物上，不是新建一个 Shopkeeper。
- `Character Identity Anchor`、`Environment Anchor`、`Prop Detail Anchor`、`Visual Style Anchor` 及 `Highest/Second/Third/Fourth priority` 保持英文；Anchor 绑定的对象名称和描述仍使用中文。风格与质量描述使用英文。

**身份必须先于场景的原因**：角色参考图是脸部与人物本体的唯一可复用锚点。若先写场景、职业标签或剧情设定，模型容易把诸如 `Shopkeeper` 之类的通用词当成重新选角条件；先锁定每个有图角色，再描述空间、服饰与动作，文字就只会改变该人物的当前处境，不会生成另一个人。

---

## Step 1：收集参考图清单

视觉锚点图绘制前，**Agent 须列出各参考图目录下的具体文件**，供 Step 2 逐场引用。

| 参考图类型 | 来源路径 | 说明 |
|-----------|---------|------|
| 角色参考图 | `project/{项目名}/全局依赖/角色设定/角色参考图/*.png` | 全局角色参考图（含妆造匹配） |
| 场景参考图 | `project/{项目名}/{剧集号}/场景参考图/*.png` | 剧集级场景参考图（含本集场景变化） |
| 道具参考图 | `project/{项目名}/{剧集号}/道具参考图/*.png` | 剧集级道具参考图（含本集道具状态变化） |
| 风格参考图 | `project/{项目名}/前期采样/风格/*.png` | 全局视觉风格基准（色调、光影氛围、画面质感） |

> 如剧集级参考图目录不存在（无变化场景/道具），回退使用全局基准图：`全局依赖/场景设定/场景参考图/` 和 `全局依赖/道具设定/道具参考图/`。
>
> **道具全局基准文件名含出现场合**：回退引用全局道具基准图时，文件名格式为 `{道具名}_{出现场合}_基准.png`。需读取 `全局依赖/道具设定/具体设定/{道具名}.md` 中的 `出现场合` 字段，匹配正确的基准文件。仅引用该道具 `出现场合` 包含当前剧集号的基准图，**禁止**引用不属于本集的道具资产。
>
> **风格参考图缺失时硬终止**：未找到风格参考图时，不允许跳过风格参考，直接跳出并提示用户补充。

**Agent 执行**：用 LS 工具列出上述目录中的 `.png` 文件，记录完整路径。

---

## 参考图排序优先级（sequential 模式）

`images` 数组顺序决定模型注意力权重。视觉锚点采用：

1. **Highest priority — Referenced character identity images**：该阶段锚点时刻在场的每个有参考图角色一张，按 `cast` 顺序排列
2. **Previous Phase Anchor**（仅非首阶段）：`{{PREV_OUTPUT}}` 占位符，排在角色参考之后、场景参考之前。对应同场前一阶段锚点图的输出，作为后阶段的空间连续参考
3. **Second priority — Environment anchor**：本场物理空间的场景参考图，通常一张
4. **Third priority — Prop detail anchors**：每个重要道具一张
5. **Fourth priority — Visual style anchor**：一张，始终最后

> 首阶段锚点无 `{{PREV_OUTPUT}}`（同场第一个阶段无前序阶段输出）。非首阶段锚点的 `images` 数组中必须包含 `{{PREV_OUTPUT}}`，排在角色参考之后、场景参考之前。
>
> **映射契约**：`images[N-1]`、提示词中的 `Reference Image N`、`Image N:` 映射块必须指向同一张图。角色身份锁在提示词最前；前阶段空间参考、场景、道具和风格只能在身份锁之后构建画面。

**硬约束**：
- 角色参考必须在风格之前（锁脸优先于锁风格）
- `{{PREV_OUTPUT}}`（非首阶段）必须在角色参考之后、场景参考之前
- 禁止省略场景参考图（锚点图的核心职责之一就是锁定场景空间）

---

## Referenced characters 与 unreferenced/background characters

任务表必须把两类角色分开处理，不能用 `ALL characters` 把它们合并：

- **Referenced characters**：`cast` 中的每个具名角色都必须有且仅有一张对应角色参考图。每张图逐一绑定一个角色，分别写入角色段、`cast` 和 `Character Identity Anchor`；不得合并成一个总的“角色参考”。
- **Unreferenced/background characters**：没有参考图的无名背景人物不进 `cast`、`images` 或 `Character Identity Anchor`。无名侍者、信使、茶客等不属于 referenced characters；除时代服化与中文来源动作/站位外，必须在实际 prompt 中加入英文硬约束：`not a referenced character, background-only, smaller visual weight, secondary placement, not a main character, not a focal point, never become the visual focus`。他们只能作为远景/侧背/虚化的次要人物；禁止成为视觉中心、英雄式特写或抢占主角权重，也不能把他们称为某个有参考角色。
- **具名但无参考图**：硬终止。若剧本把 `Messenger`/“信使”等当作具名角色，不能靠文字开脸，必须补参考图或改分镜；只有“无名的信使/路人”这一类背景功能角色允许无图生成。

这样既保留场级空间中的必要背景人物，又不会让无参考人物抢占或污染有参考角色的身份权重。

## 出场角色引用铁律

> **根因**：旧规则写「按需引用 / 未登场不引」，Agent 常只给**焦点角色**挂参考图。
> 视觉锚点图要的是**该阶段锚点时刻在场角色的空间站位定调**，不是「只锁主角」或「全场角色大杂烩」。
> 角色阶段拆分的核心目的：避免不应出现在某些镜头中的角色被画进锚点图，串场到下游视频生成。

### 何谓「锚点时刻在场」（必须挂参考）

扫描该阶段**锚点镜头**的 `场景描述`、`站位/调度`、`表演/微表情`、`台词` 后，下列任一成立即算该锚点时刻在场：

| 信号 | 示例 | 是否必须 `images` 含其角色参考 |
|------|------|-------------------------------|
| 正脸/侧脸可见 | 「抬眼望小二」 | 是 |
| 身体/半身/背影可见 | 「立于柜台后」 | 是 |
| 仅手/脚/局部入画 | 「执笔手从画右入画」 | **是**（局部也要锁身份与服装） |
| 站位里被点名在场 | 「小二立于掌柜右侧」「眼神看向掌柜」 | **双方都要引** |
| 台词归属角色 | `掌柜："…"` | 若该角同时在画面内则必须引 |
| 纯画外音、完全不在画内 | 画外 trans 音 | 否 |

**禁止**：只按「焦点角色/说话人」引参考；禁止因「只露手/背影」而省略角色参考。

### 阶段内在场角色引用

1. 编写任务表前，先为**每个角色阶段**确定锚点镜头，再列出该阶段的 `阶段在场表`：锚点镜头中在场的、且目录中有参考图的具名角色。
2. 对每个阶段锚点图：取「阶段出场集合」= **锚点镜头在场角色**（非全组扫描）。
3. 阶段出场集合中**每一个**有参考图的角色，都必须进入该 task 的 `images`（角色段）+ `cast` 字段 + Character Identity Anchor。
4. **cast 严格等于锚点镜头在场角色**：不在该锚点镜头中的角色不进 `cast`，即使该角色在该阶段的其他镜头中出场。
5. 仅当该角在该锚点镜头中明确在场（含局部/背影/站位点名）才计入 cast。

### `cast` 字段（任务表必填）

每个 task 增加：

```json
"cast": ["掌柜", "小二"]
```

- 这里只列**该阶段锚点镜头在场的、且有对应角色参考图的具名角色**；无参考背景人物不列入
- 中文名，与角色参考图文件名可匹配（文件名含该名，如 `掌柜_默认妆造.png`）
- `cast` 顺序 = `images` 中角色参考顺序 = REFERENCE IMAGE MAPPING 中 Character Identity Anchor 顺序
- 校验器会核对：`cast` 非空（有人在场时）、每个名字能在 `images` 角色路径中找到、Character Anchor 数量 = 角色图数量

### 无参考图龙套 / 路人（造型漂移与朝代错位闭环）

| 角色类型 | 有无参考图 | 处理 |
|----------|------------|------|
| 具名角色（掌柜/小二/赵胖等） | 有 | 必须引参考；禁止纯文字开脸 |
| 具名角色 | **无** | **硬终止**：不得开写该场任务；回报 orchestrator 补角色参考或改分镜去掉该角具名出场 |
| 无名龙套/路人（茶客甲、街人、无名信使） | 通常无 | 允许无图，但必须 **时代锚定描述**；禁止抢戏、禁止特写正脸当主角 |
| 群演占画面主体且无一人有参考 | — | 优先改调度（虚化/背影/远景）；仍不够则硬终止补「群演氛围参考」或具名化+出参考图 |

**时代锚定（无图龙套强制）**：

1. 从 `全局依赖/全局设定.md` 读取时代（如「唐朝/盛唐」），原样写入 SCENE CONTINUITY 的 `{period_description_zh}` 与 FRAME DETAIL。
2. 每个无图龙套在 FRAME DETAIL / 必要时在 REFERENCE 段用中文写死时代、服化、动作和站位（唐：圆领袍/襦裙/幞头等；**禁止**清辫、民国长衫、现代T恤等错代），随后追加英文权重锁：`not a referenced character, background-only, smaller visual weight, secondary placement, not a main character, not a focal point, never become the visual focus`。
3. AVOID 与 SCENE CONTINUITY 必须含：`no anachronistic costumes from other dynasties (Qing, Republican China, modern streetwear)`（按项目时代改写）。
4. 龙套默认：中远景、侧背、虚化；除非分镜明确要求，禁止无参考路人英雄特写。

---

## 单帧画布铁律（禁多宫格 / 禁烧字幕）

> 目标产物：**一张填满画布的电影单帧**，供后续视频生成作为场级视觉参考。不是分镜板、不是四宫格、不是带字幕条的宣传图。

| 禁止 | 说明 |
|------|------|
| multi-panel / grid / 2×2 / comic / collage / contact sheet / split-screen | 任一即失败 |
| 画面内字幕/台词条/caption/lower-third/title card | 台词只存在于音频与剧本，不烧进图 |
| 镜头号角标、水印、LOGO、UI 边框 | 锚点图保持干净 |
| prompt 含 `storyboard`、`frame N of M`、序列节拍总览 | 已验证会诱发宫格 |

OPENING 只负责单帧画布声明；TEXT POLICY 只负责烧字/字幕策略；AVOID 只保留末尾的少量布局、时代、背景人物权重和空洞姿态禁令。三段不得复制同一长串 `No multi-panel/No logos...`；字幕禁令只在 TEXT POLICY 中表达，风格文件 `avoid` 不能替代任务 prompt 的这些最小明确约束。

---

## Step 2：Agent 直接编写任务表 JSON

Agent 使用 Write 工具直接编写 `视觉锚点_任务表.json`，保存到 `project/{项目名}/{剧集号}/分镜/视觉锚点_任务表.json`。

### 2.1 读取分镜内容并提取场清单与角色阶段

读取 `{剧集号}/分镜/分组/` 目录下的组文件，提取**场清单**：
- **详细模式**：`组{N}.json` — 从 `场号`、`场名称` 获取场信息，从 `通用设定`、`镜头列表` 获取该场的角色站位、关键动作、氛围信息
- **精简模式**：`组{N}.md` — 从正文获取叙事概述和分镜描述

> **场号 = 物理空间标识**：从组文件读取 `场号` → 每个唯一场号对应一个物理空间。同一场号的多个组属于同一场。

#### 场清单提取规则

1. 遍历全部组文件，收集所有唯一 `场号` 及对应 `场名称`
2. 对每场，汇总该场全部组的以下信息：
   - **场景空间描述**：物理空间布局、建筑特征、家具陈设
   - **出场角色清单**：该场全部组中出现过的所有具名角色（去重）
   - **角色站位与调度**：角色在空间中的位置关系、朝向、关键走位
   - **关键动作与神态**：该场中最具代表性的角色动作与表情（选取能体现该场戏核的瞬间）
   - **氛围基调**：光线、色温、情绪氛围
   - **重要道具**：该场中出现的所有重要道具
3. 每场产出一条或多条锚点图任务（取决于角色阶段拆分结果）

#### 角色阶段拆分（关键步骤）

对每场执行角色阶段拆分，确定该场需要几张锚点图：

**扫描范围**：该场全部组全部镜头，按播放顺序逐镜头扫描。

**拆分条件**（满足任一即在角色变化点拆分新阶段）：
- 有具名角色（有角色参考图的具名角色）从「不在画面」变为「在画面」（角色入场）
- 有具名角色从「在画面」变为「离开」（角色离场）

**不拆分的情况**：
- 无名背景人物增减（茶客来去、路人经过）— 不触发新阶段
- 同一组角色只换站位/动作 — 不触发新阶段
- 角色短暂出画又入画（如转身取物）— 不触发新阶段

**阶段编号**：同场阶段按播放顺序编号 A、B、C...（如场1拆分为 1A、1B；无拆分时仍为场1，不带字母后缀）。

**每个阶段选定一个锚点镜头**：
- 锚点镜头 = 该阶段中**戏核最匹配、站位最完整**的单个镜头
- 优先选取能体现该阶段戏剧核心的瞬间
- 站位最完整 = 该阶段在场角色在该镜头中位置关系最清晰
- 不是该阶段的第一个镜头，而是该阶段视觉信息最丰富的瞬间

**阶段间依赖**：
- 同场阶段按播放顺序串行：阶段 A → 阶段 B → 阶段 C...
- 非首阶段锚点的 `images` 中增加 `{{PREV_OUTPUT}}`，引用前一阶段锚点图输出作为空间参考
- 首阶段锚点无 `{{PREV_OUTPUT}}`
- 不同场的锚点图之间无依赖，可并行

> **锚点时刻选择**：锚点图应选取该阶段中**最能体现戏核、角色站位最清晰**的时刻。通常选取：
> - 该阶段第一个全景/建立镜头的时刻（锁定空间全貌）
> - 或该阶段角色站位最完整、互动最关键的时刻
> - 不是该阶段的第一个镜头，而是该阶段视觉信息最丰富的瞬间

### 2.2 风格匹配

从通用设定的 `风格` / `风格质感` 字段提取关键词，匹配风格参考文件：

#### 真人/实拍类

| 风格名 | 关键词 | 参考文件 |
|--------|--------|---------|
| LiveAction | 真人实拍、真人摄影、照片级真实、live-action、historical drama、电影级质感、真人影视剧 | `references/styles/LiveAction.md` |

#### 2D 动画类

| 风格名 | 关键词 | 参考文件 |
|--------|--------|---------|
| InkAnimation | 水墨、水墨风、水墨动画、国画、ink-wash、Chinese ink painting、水墨风人物动画 | `references/styles/InkAnimation.md` |
| Anime2D | 日系动漫、二次元、anime、新海诚、京阿尼、吉卜力2D、番剧、日漫、Japanese animation、cel animation | `references/styles/Anime2D.md` |
| Western2D | 欧美卡通、美式动画、Cartoon Network、Adventure Time、Rick and Morty、Western cartoon、2D cartoon、flat cartoon | `references/styles/Western2D.md` |
| FlatIllustration | 扁平插画、矢量插画、flat design、vector illustration、UI插画、极简插画、flat art、minimalist illustration | `references/styles/FlatIllustration.md` |

#### 3D CGI 类

| 风格名 | 关键词 | 参考文件 |
|--------|--------|---------|
| 3DCartoon | 3D卡通、皮克斯、迪士尼、Pixar、Disney、3D动画、3D拟人化、3D喜剧 | `references/styles/3DCartoon.md` |
| Realistic3DCGI | 写实3D、电影特效、CGI、realistic 3D、VFX、photoreal CGI、3D写实、电影级3D、3D特效 | `references/styles/Realistic3DCGI.md` |
| Stylized3DCGI | 风格化3D、蜘蛛侠平行宇宙、Spider-Verse、3D混合2D、hybrid 3D、stylized CGI、美漫风3D、3D漫画风 | `references/styles/Stylized3DCGI.md` |
| GameCinematic | 游戏CG、游戏过场、最终幻想、GTA、Rockstar、FF、game cinematic、game cutscene、游戏预告片、3A游戏、AAA game | `references/styles/GameCinematic.md` |

> 无明确匹配时默认使用 `LiveAction.md`。

匹配后读取风格参考文件的 front-matter，提取以下参数用于 prompt 构建：

| 参数 | 注入段落 |
|------|---------|
| `production_type` | OPENING DECLARATION |
| `neg_1` / `neg_2` / `neg_3` | OPENING DECLARATION |
| `style_anchor` | CINEMATIC QUALITY 段头部 |
| `style_footer` | CINEMATIC QUALITY 段尾部 |
| `camera_language` | CINEMATIC QUALITY 段（摄影原则子段） |
| `quality` | CINEMATIC QUALITY 段（画质要求子段） |
| `avoid` | AVOID 段 |

### 2.3 文字元素检测

Agent 扫描**当前场**对应的分镜内容，检测画面中可能出现的文字元素。扫描范围：

| 扫描字段 | 关注信号 |
|---------|---------|
| `场景描述` | 招牌、门匾、墙面文字、屏幕界面 |
| `站位/调度` | 角色走向写有文字的物体 |
| 道具设定 | 会员牌、书信、票据、包装、容器标签 |
| `台词` | 角色在阅读/书写时，台词内容需出现在画面中 |

检测到文字后，按三层分类法处理：

| 类型 | 判定条件 | 处理方式 |
|------|---------|---------|
| **A：必须准确的文字** | 招牌、品牌名、票据、书信、手机界面、产品包装 | 显式指定中文字符，要求准确呈现 |
| **B：装饰性文字** | 远处店铺招牌、背景书法、环境文字 | 不指定内容，仅描述质感和时代感 |
| **C：道具文字** | 会员牌、木牌、容器标签 | 按剧情重要性分级：决定剧情则保留，纯视觉元素则仅生成材质 |

> **关键风险**：模型常将中文字符替换为拼音或拉丁字母（如"春生"→"chunsheng"）。类型 A 和类型 C（重要道具文字）必须显式约束 `Do not replace Chinese characters with Latin letters or pinyin.`

未检测到特定文字元素时，TEXT POLICY 段仍保留默认策略（防止模型自行生成假汉字/拼音），仅省略精确文字内容。

### 2.4 构建 Prompt

Prompt 使用 **English control shell + 中文 content layer**，由以下 **7 段**按固定顺序组成。每场一个独立的 prompt，生成一张锚点图。为避免身份被场景语义覆盖，`OPENING DECLARATION` 的第一段必须是 `IDENTITY LOCK — HIGHEST PRIORITY`；这是 prompt 的第一项实质内容，必须先于任何空间、镜头、动作或氛围描述。

> **编译器铁律**：Prompt 编译器的职责是把英文模型控制层与中文分镜内容组装起来，**不是编剧，也不是翻译器**。角色名、角色关系、场景空间、动作、站位、神态、台词相关内容、道具内容、时代/剧情事实必须保留原中文；不得为了英文结构翻译这些事实，也不得借翻译重写角色外貌。只复述原分镜已有的视觉信息，禁止新增道具、时间、动作、情绪事件、光线条件或场景。

### 提示词净化规范（元约束净化 · 硬规则）

> 所有最终写入 `prompt` 字段、提交给生图模型的文本必须为**纯画面描述语言**。
> 凡是"本应属于智能体编写规范、而非最终发送给生图模型的内容"（元约束/元语言）一律禁止出现在 prompt 中——它们会稀释画面描述权重、降低生成质量（EP11 实测：删除此类内容后生成质量正常）。
> 净化在**组装 prompt 时**由编写 Agent 完成；本文档中的编写指引、注释、校验说明是给 Agent 阅读的材料，**不属于** prompt 内容。

**必删 11 类（prompt 中出现即违规）**：

| # | 类别 | 示例（原文） | 处理 |
|---|------|-------------|------|
| 1 | 段落放置/编排指令 | `write this block after the heading and before any SCENE...`、`in cast/images order` | 删除整句，保留其后的实质约束 |
| 2 | Decision rule 决策说明 | `Decision rule: facial identity and actor continuity take priority over...` | 删除（已由身份锁的 `identity wins every conflict` / `modify only wardrobe, hairstyle, and setting` 覆盖） |
| 3 | 括号标签机制解释 | `The Chinese role names in parentheses are binding content labels for the referenced persons, not casting instructions` | 删除 |
| 4 | 编写者脑补禁令 | `Do not let the role labels or prose infer new faces, ages, hairstyles, smiles, or body types` | 删除（编写环节约束，模型不接收） |
| 5 | 编译器/流水线说明 | `The prompt compiler assembles control language around source content...`、`Source fidelity rule:` 整块 | 删除 |
| 6 | 中文事实保留指令 | `Keep Chinese character names... in Chinese. Do not translate or rewrite them.` | 删除（翻译/改写风险在编写环节，模型不需要此指令） |
| 7 | 占位符机制解释 | `The PREV_OUTPUT placeholder — the output from the previous phase serves as...` | 删除；仅保留 `Image N: Previous Phase/Frame Anchor` 标签 |
| 8 | 锚点职责定位从句 | `This is a visual anchor frame for {场景名} — a single establishing image that locks the scene's spatial layout...` | 保留 `This is a visual anchor frame for {场景名}.`，删职责从句 |
| 9 | 锚点职责块 | `Anchor frame responsibilities:` 整块 | 删除 |
| 10 | Mapping 内机制解释 | `The Chinese role name describes duty and source content only.` | 删除；可保留具体的中文绑定内容（如「茶客坐在左侧茶桌旁」） |
| 11 | 道具配对说明括号 | `same props (每个道具必须匹配对应参考图；道具名称、状态和剧情用途保留中文)` | 仅保留 `same props` |

**必须保留（禁止因净化误删）**：

- 画面描述全部内容：场景/动作/表演/构图/光影/氛围（English control + 中文 content）
- 身份锁短语：`Reference priority`、`identity wins every conflict`、`actor continuity`
- 逐角色身份锁句：`must remain recognizable as the same actor/person`、`sole identity source`、`face identity has absolute priority`、`Do not alter facial identity / facial structure / skin features / body proportions`、`modify only wardrobe, hairstyle, and setting` 等
- `Image N:` 标签与优先级语义（`Highest/Second/Third/Fourth priority`）——校验器按此计数
- 单帧声明：`exactly one image` / `single frame only` / `fills the entire canvas`
- TEXT POLICY 禁字幕块、AVOID 负面清单、背景人物降权句（`not a referenced character, background-only, ...`）
- 场景名（保留在定位句内，仅删职责从句）

```
┌─ 1. OPENING DECLARATION（第一行先写 IDENTITY LOCK）
├─ 2. SCENE CONTINUITY
├─ 3. REFERENCE IMAGE MAPPING
├─ 4. FRAME DETAIL
├─ 5. TEXT POLICY
├─ 6. CINEMATIC QUALITY
└─ 7. AVOID
```

---

#### 段落 1：OPENING DECLARATION

> **禁用 "storyboard" 一词**：生图 prompt 中严禁出现 "storyboard"。图像模型将这个词理解为多格分镜板布局，即使有单帧指令也会生成宫格图。使用 "cinematic film frame" 替代。

```
IDENTITY LOCK — HIGHEST PRIORITY:
Reference priority (highest to lowest): Highest priority = referenced character identity and actor continuity; Second priority = environment; Third priority = props; Fourth priority = visual style. Identity wins every conflict: environment, props, style, historical appearance, and occupational archetype may serve the locked person, but may never replace that person's face or actor identity.

Actor continuity lock — for each referenced character:
Reference Image {N} character（{role_name_zh}角色） must remain recognizable as the same actor/person after all costume, hairstyle, pose, lighting, and environment changes.
Reference Image {N} character（{role_name_zh}角色） is the sole identity source for this referenced person; it is the same specific person shown in the image, not a newly generated interpretation.
Do not generate a generic {period_role_archetype}; do not use a historical or occupational archetype as a replacement casting.
If historical appearance conflicts with reference identity, preserve the reference identity and modify only wardrobe, hairstyle, and setting.
The face identity has absolute priority over role archetype, age description, or historical styling.
Referenced characters must look like the same people from the reference images, not similar-looking replacements.
Do not alter facial identity, facial structure, skin features, or body proportions.
Change only clothing and hairstyle required by the historical setting; wardrobe, hairstyle, and environment changes must not create a new person.

Create a professional cinematic film frame for {film_context}.

This is a visual anchor frame for {scene_name_zh}.
Generate exactly one image for this single frame only.
One single photographic still that fills the entire canvas.

This is {production_type},
not {neg_1},
not {neg_2},
not {neg_3}.
```

> **具体示例（仅用于理解，写入实际 prompt 时要按任务替换）**：如果 `images[0]` 是掌柜参考图，身份/动作/站位第一次绑定应写成 `Reference Image 1 character（掌柜角色）...`，而不是以 `Shopkeeper` 开头。唐代掌柜场景须在逐角色身份锁后写入 `Do not generate a generic Tang Dynasty female shopkeeper.`（`{period_role_archetype}` 按角色替换）；该句是防止职业原型重新选角的硬约束，不是新角色描述。

| 占位符 | 来源 | 示例 |
|--------|------|------|
| `{film_context}` | 通用设定.风格 → English control term | a historical drama film / a Chinese ink-wash animation film |
| `{scene_name_zh}` | 场名称原文 | 春生茶肆·日/内 / 现代厨房 |
| `{role_name_zh}` | `cast` 中的角色名、角色职责和关系原文 | 掌柜 / 小二 |
| `{period_role_archetype}` | 为防止重新选角而使用的 English generic archetype；不是角色命名 | Tang Dynasty female shopkeeper |
| `{production_type}` | 风格参考文件 | a live-action film pre-production cinematic frame |
| `{neg_1/2/3}` | 风格参考文件 | concept art / illustration / a fantasy painting |

> **实际编写要求**：`{N}` 必须替换为 `images` 中的实际序号，`{role_name_zh}` 必须保留角色中文名。每个有参考角色都先写 `Reference Image N character（中文角色名/职责）` 的绑定式句子，再写动作、站位或神态；不得把 `Shopkeeper`、`Waiter` 等职业词作为首次选角标签。若本场 `cast=[]`，省略角色身份锁的逐角色行，但仍保留场景/风格参考和单帧声明。

---

#### 段落 2：SCENE CONTINUITY

```
SCENE CONTINUITY:

This is a visual anchor for {scene_name_zh} — the definitive spatial and atmospheric reference for this physical location.

Maintain strict continuity with reference materials:
- same identity for each referenced `cast` member, bound one-to-one to its paired character reference image
- the explicit current-scene costume and period context for each referenced person, without changing that person's identity
- same {environment_description_zh}
- same props
- same lighting atmosphere
- same {period_description_zh}
- no anachronistic costumes from other eras or dynasties
- unreferenced/background people remain unnamed, secondary, and period-appropriate; they are not identity anchors
- every unreferenced/background character is not a referenced character, background-only, smaller visual weight, secondary placement, not a main character, not a focal point, never become the visual focus
```

| 占位符 | 来源 | 示例 |
|--------|------|------|
| `{scene_name_zh}` | 场名称原文 | 春生茶肆·日/内 |
| `{environment_description_zh}` | 通用设定.场景名称与空间内容原文 | 茶肆内，木柜台靠右，后墙为层架 |
| `{period_description_zh}` | 项目时代背景、时代/剧情事实原文 | 唐朝盛世 / 现代城市 |

> **反二次创作约束（编写环节）**：禁止添加分镜中不存在的视觉元素、禁止在翻译时重写角色外貌、禁止把中文事实改成英文——这些约束由编写 Agent 在组装 prompt 时执行，属于**编写规范**，不是 prompt 内容（见「提示词净化规范」；原 `Source fidelity rule` 段已从模板移除，不得再写回 prompt）。

---

#### 段落 3：REFERENCE IMAGE MAPPING

为 `images` 数组中的每张参考图写一个映射块，**顺序与数组严格一致**。每个映射块必须以 `Image {N}:` 开头，N 从 1 递增。使用 **Anchor 类型**明确告知模型每张参考图的用途，并在类型名中写出优先级。

> **双语映射规则**：映射块的 Anchor 类型和优先级保持英文；角色名、角色关系、场景名、空间描述、道具名、道具状态和剧情用途使用中文原文。中文绑定对象不是新选角标签，英文只包裹模型控制要求。

> **多角色多道具是常态**：一场中出场多个角色、使用多个道具是正常情况。**每个 `cast` 成员（含非焦点、局部入画、站位被点名）都必须有独立的 Character Identity Anchor 映射块**；无参考背景人物不写 Character Identity Anchor。每个重要道具都必须有独立的 Prop Detail Anchor 映射块。

**角色参考**（**每个 `cast` 成员一个映射块**，顺序与 `cast`/`images` 一致，主要角色在前）：
```
Image {N}: Character Identity Anchor — Highest priority
Reference Image {N} character（{role_name_zh}角色） is the sole identity source for this referenced person. This is the same specific person shown in the image, not a new casting.
Identity comes from the image only. Preserve facial identity, facial structure, skin features, and body proportions; do not add a text-derived replacement face.
Apply only the current-scene clothing, hairstyle, blocking, and action, without changing identity.
Even if only a hand, shoulder, or back is visible, keep the same referenced person; do not substitute a newly invented character.
```

> **不要写外貌重述段**：不要把 `Shopkeeper`、`Waiter` 等英文职业词，或年龄、脸型、发型、微笑、“现代穿越者”等通用语义扩写成新人物。只写参考图绑定、中文来源明确要求的服饰/职责/动作、关系，以及可见部位（`full body` / `face` / `hands only`）。后文若为可读性使用 `Shopkeeper (the same referenced person)`，必须明确它只是已绑定参考人物的简称，不能重新选角。

**场景参考**（通常一个，组内场景切换时可多个）：
```
Image {N}: Environment Anchor — Second priority
{scene_name_zh} — {场景空间中文描述：建筑、家具、材质、氛围与空间关系}。
Preserve: architecture, spatial layout, materials, atmosphere.
```

**道具参考**（**每个重要道具一个映射块**，按剧情重要性排序）：
```
Image {N}: Prop Detail Anchor — Third priority
{prop_name_zh} — {道具内容中文描述：材质、形状、纹理、工艺、当前状态与剧情用途}。
Preserve: shape, texture, craftsmanship, material.
```

**风格参考**：
```
Image {N}: Visual Style Anchor — Fourth priority
{brief English style description}.
Preserve: color palette, lighting mood, visual style.
```

> **硬约束**：每个映射块的 `Image {N}:` 编号必须与 `images` 数组位置严格一一对应（Image 1 = images[0]，Image 2 = images[1]，...）。编号不连续或顺序错乱将导致模型无法正确关联参考图。
>
> **角色映射块数量 = `images` 中角色参考图数量**：如果该场有 3 个角色出场，`images` 数组中就有 3 张角色参考图，REFERENCE IMAGE MAPPING 段就有 3 个 Character Identity Anchor 映射块。不得合并或省略。

---

#### 段落 4：FRAME DETAIL

单帧描述。**必须包含 Purpose 和 Feeling 字段**——Purpose 告诉模型这个锚点图为什么存在，Feeling 告诉模型这个场景应该让观众感受到什么情绪。

> **影视级静帧质感要求**：锚点图虽为场级定调，但仍须包含完整的角色动作与神态描述。缺乏角色动作和神态的锚点图会对后续视频生成流程造成不良影响——视频导演依赖锚点图理解角色的表演基调和空间关系。
>
> **身份不在此处重建**：`IDENTITY LOCK` 已先锁定有参考角色。`Scene`、`Action`、`Performance` 只补充原分镜明确的中文空间、当前服饰、动作、站位、关系和表演；不得新增年龄、脸型、发型、微笑或“现代穿越者”等外貌/身份设定。无参考背景人物只写为无名、次要、符合时代的背景人物，并附英文视觉权重硬约束：`not a referenced character, background-only, smaller visual weight, secondary placement, not a main character, not a focal point, never become the visual focus`。

```
FRAME DETAIL:

Purpose:
{锚点图戏剧功能 → 中文，一句话说明此锚点图存在的理由}
{如：建立茶肆空间布局并锁定掌柜与茶客的站位。}

Feeling:
{情绪氛围与剧情感受 → 中文，一句话描述观众应感受到的情绪}
{如：重要消息宣布前短暂而安静的期待。}

Scene:
{场景空间描述 + 角色站位/调度 → 中文叙事，仅复述原分镜内容}
{必须描述完整的物理空间布局：建筑结构、家具陈设、道具摆放位置}
{必须描述每个 referenced cast 成员在空间中的位置关系：谁站在哪里、朝向谁、与其他角色的距离}
{每个 unreferenced/background character 除中文时代服化与动作/站位外，必须追加：not a referenced character, background-only, smaller visual weight, secondary placement, not a main character, not a focal point, never become the visual focus。无名侍者/信使等不得成为视觉中心、英雄式特写或主角权重。}
{这是锚点图的核心职责——锁定空间关系}

Action:
{角色动作 → 中文叙事，可使用自然句式；第一次出现角色时先写 Reference Image N character（中文角色名/职责）}
{多角色场景须按 cast 分角色描述动作，格式：Reference Image N character（角色名/职责）: 中文动作描述；无参考背景人物只写必要的远景/侧背动作，并附 not a referenced character... 硬约束}
{选取该场最具代表性的时刻的动作——能体现戏核的瞬间}
{禁止留空或仅写“站着”——须有具体中文动作姿态}

Performance:
{表演/微表情 → 中文叙事，可使用自然句式}
{多角色场景须按 cast 分角色描述表演，格式：Reference Image N character（角色名/职责）: 中文表演描述；只使用原分镜明确的表演信息}
{必须为每个 referenced cast 成员写明源自分镜的表演状态；无参考背景人物不写主角式表情}
{禁止留空或仅写“面无表情”——须有具体且有来源的中文情绪状态}

Composition:
{景别 + 摄影机角度 → 英文电影语义}
{锚点图通常采用全景或中景，以展示完整空间和角色站位}

Camera feeling:
{摄影机运动 → 英文电影语义}
{锚点图通常为固定机位或缓慢推进}

Lighting:
{光线 → 英文}
{锚点图须锁定该场的光线基调}

Atmosphere:
{场级氛围与剧情感受 → 中文}
{如：重要但仍扎根于日常街市生活的仪式性揭示。}
```

> **Purpose 字段**回答“这个锚点图为什么存在”（如“建立茶肆空间与角色站位”）。**Feeling 字段**回答“观众应该感受到什么”（如“重要消息宣布前的安静期待”）。两者使用中文内容，互补且缺一不可。
>
> **禁止焦距参数**：不写入 35mm / 50mm / 85mm 等焦距数值。仅保留景别（wide shot / close-up 等）和角度（eye-level / low angle 等）。
>
> **叙事句式允许**：Action 和 Performance 段允许使用中文自然叙事句式，但仅限复述原分镜内容，禁止二次创作。英文只保留绑定式前缀和视觉控制约束。
>
> **多角色场景编写指引**：当一场中有 2 个及以上角色时，Action 和 Performance 段**必须为每个角色分别描述**。遗漏任一角色的动作/表演描述会导致该角色在画面中无动作或表情僵硬。
>
> **Action 段不可省略**：锚点图不是静物照，角色必须有具体动作姿态。即使角色处于“等待”状态，也要用中文描述具体身体语言（如“靠在柜台边、双臂交叠”而非“站着”）。
>
> **Performance 段不可省略**：每个在场角色都必须有神态描述。这是保证影视级静帧质感的关键——缺乏神态描述的锚点图会导致后续视频生成中角色表情空洞。

##### 景别转换表

| 中文 | 英文电影语义 |
|------|------------|
| 大全景 | extreme wide shot |
| 全景 | wide shot / establishing shot |
| 中景 | medium shot |
| 近景 | medium close-up |
| 特写 | close-up |
| 大特写 | extreme close-up |

##### 运镜转换表

| 中文 | 英文电影语义 |
|------|------------|
| 固定 | static camera, locked-off |
| 缓慢推镜头 | slow push-in |
| 快速推镜头 | fast push-in |
| 缓慢拉镜头 | slow pull-out |
| 横摇 | pan / horizontal sweep |
| 竖摇 | tilt |
| 跟拍 | tracking shot |
| 环绕 | orbit shot |
| 手持 | handheld |
| 升降 | crane shot |

##### 角度转换表

| 中文 | 英文电影语义 |
|------|------------|
| 平视 | eye-level |
| 微仰视 | low angle |
| 微俯视 | high angle |
| 俯视 | top-down / bird's eye view |
| 仰视 | extreme low angle |

##### 精简模式（MD）处理

精简模式下镜头信息融入叙事段落（一段一镜）。Agent 需要：

1. 将同一物理场的全部叙事段落汇总为一条锚点图任务
2. 从散文中提取该场的空间布局、角色站位、关键动作、神态、光线等关键词
3. 叙事内容继续使用中文；仅将景别、机位、运镜等摄影控制词按转换表写成英文电影语义
4. 选取该场最具代表性的瞬间作为锚点图的"定格时刻"

---

#### 段落 5：TEXT POLICY

**常驻段**——无论是否检测到特定文字元素，此段始终存在。默认策略防止模型自行生成假汉字/拼音；精确文字内容根据 2.3 检测结果条件注入。

**默认策略（无特定文字时）**——**始终包含禁字幕块**：
```
TEXT POLICY:

Hard ban on burned-in graphics (non-negotiable):
- No subtitles, captions, lower-thirds, or title cards
- No on-screen dialogue text or lyric text
- No watermarks, logos, shot numbers, timecode, or UI chrome
- Spoken lines exist only as audio in the final edit — never as text painted onto this frame

Diegetic in-world text only (shop signs, book pages, packaging) when the scene itself contains them:
- Preserve original Chinese characters
- Do not translate into English
- Do not generate pinyin
- Do not replace Chinese characters with Latin letters

If exact typography cannot be guaranteed, preserve material and visual shape only.
Leave all editorial text for post-production.
```

**类型 A — 必须准确出现的文字**（在默认策略后追加）：
```
Required readable text: "{Chinese text content}"
Prioritize accurate Chinese typography.
```

**类型 B — 装饰性文字**（在默认策略后追加）：
```
Decorative text: traditional Chinese handwritten signs, unreadable but authentic.
Do not specify exact text content.
```

**类型 C — 道具文字**（在默认策略后追加）：

文字决定剧情时：
```
Prop text — {prop_name_zh}:
Exact text: "{Chinese text content}"
Do not replace Chinese characters with English letters or pinyin.
```

文字仅为视觉元素时：
```
Prop text — {prop_name_zh}:
Generate material texture only. Do not render readable characters.
```

> 多种类型同时存在时，在同一个 TEXT POLICY 段内分列，共享默认策略头部。

---

#### 段落 6：CINEMATIC QUALITY

合并视觉风格、摄影语言原则和画质要求为单段。从风格参考文件提取 English control terms：`style_anchor`、`style_footer`、`camera_language`、`quality`。风格、色彩、摄影、灯光、材质和画质描述使用英文；分镜特有的空间、动作、神态、道具、时代/剧情事实仍放在前面的中文内容段，不要在这里翻译或重写。

```
CINEMATIC QUALITY:

{style_anchor}

{全局风格氛围基调 → English style/quality terms}
{全局色彩调性 → English color/lighting terms}
{全局光线基调 → English lighting terms}

{style_footer}

Camera principles:
{camera_language}

{quality}
```

> 只有属于模型控制层的风格、摄影、灯光和画质词使用英文电影语义；角色、场景、动作、道具及时代/剧情事实不得翻译。各风格参考文件附带对应的 English control terms。
>
> **关键词精简原则**：避免在 quality 中反复堆砌 cinematic / film / professional / realistic 等词。模型已通过 `production_type` 和 `style_anchor` 理解风格基调，重复关键词会稀释注意力。

---

#### 段落 7：AVOID

从风格参考文件 front-matter 提取 `avoid`，去重后只保留与单帧布局、时代、背景人物权重和空洞姿态相关的必要项，过滤字幕/烧字类条目，并**放在 prompt 末尾**。不要把长篇负面清单放在身份锁前，也不要在 AVOID 重复身份锁；脸部身份与演员连续性已经在最前的 `IDENTITY LOCK` 中完成，字幕/烧字禁令由 TEXT POLICY 负责。

```
AVOID:

{style_avoid}

Compact final bans:
- No multi-panel, grid, collage, contact sheet, or split-screen layout; one clean frame only.
- No anachronistic costumes for the period or background people.
- No unreferenced/background character becomes a main character or focal point.
- No empty or lifeless character poses; every referenced character needs a source-backed action and expression.
```

---

### 2.5 逐场匹配参考图

对每场，按「出场角色引用铁律」与道具/场景规则，从 Step 1 清单选取文件：

#### 步骤 A：建场在场表

读完整场全部组全部镜头 → 列出本场出现过的具名角色 → 与 `角色参考图/` 文件名匹配。
缺参考的具名角色 → **硬终止**（见上节龙套表）。

#### 步骤 B：逐场 `cast`

对本场用「何谓出场」表得到**有参考图的具名角色** `cast`（中文名列表）。
**不是**「焦点角色列表」——站位里提到的在场角色、只露手的角色全部计入；无名背景人物不计入。

#### 步骤 C：组装 `images`

1. **Highest priority / 角色**：`cast` 中每个有参考图的角色各一张，戏剧重要性排序。局部入画也要挂。
2. **Second priority / 场景**：本场物理空间场景图。
3. **Third priority / 道具**：本场重要道具。优先剧集级，否则全局基准（`出现场合` 含本集）。
4. **Fourth priority / 风格**：一张，**始终最后**。

写入顺序：`角色… → 场景 → 道具… → 风格`

#### 步骤 D：无图龙套

`cast` 只列有参考的具名角色。无名路人或无名信使**不进** `cast`/`images`，但必须在 FRAME DETAIL 用中文时代服化、动作和站位描写，并追加 `not a referenced character, background-only, smaller visual weight, secondary placement, not a main character, not a focal point, never become the visual focus`；具名但无参考的角色仍然硬终止。

prompt 中 REFERENCE IMAGE MAPPING 与 `images` **一一对应**；Character Identity Anchor 个数 = 角色图个数 = `cast` 长度。

> **同场场景一致**：锚点图引用本场场景参考图。
>
> **角色增减（修订）**：
> - 完全不在画内且站位未提及 → 不引
> - 在场（含局部/背景/被点名）→ **必须引**
> - 已离场 → 后续可不引
> - 新登场 → 从该场起引角色参考锁脸

---

### 2.6 任务表 JSON 格式

任务表使用 sequential 模式，场内阶段串行、场间并行。一场一个或多个 task（取决于角色阶段拆分结果）：

```json
{
  "mode": "sequential",
  "model": "nano-banana-2",
  "output_path": "project/{项目名}/{剧集号}/分镜/视觉锚点",
  "tasks": [
    {
      "id": "anchor-1A",
      "scene": "1",
      "group": "1A",
      "scene_name": "{场名称}",
      "shot_range": "1-3",
      "filename": "锚点_场1A_{阶段名}.png",
      "cast": ["角色A", "角色B"],
      "prompt": "...",
      "aspectRatio": "16:9",
      "imageSize": "2K",
      "images": [
        "project/.../角色参考图/角色A_默认妆造.png",
        "project/.../角色参考图/角色B_默认妆造.png",
        "project/.../场景参考图/场景.png",
        "project/.../道具参考图/道具A.png",
        "project/.../道具参考图/道具B.png",
        "project/.../风格/风格参考.png"
      ]
    },
    {
      "id": "anchor-1B",
      "scene": "1",
      "group": "1B",
      "scene_name": "{场名称}",
      "shot_range": "4-7",
      "depends_on": "anchor-1A",
      "filename": "锚点_场1B_{阶段名}.png",
      "cast": ["角色A"],
      "prompt": "...",
      "aspectRatio": "16:9",
      "imageSize": "2K",
      "images": [
        "project/.../角色参考图/角色A_默认妆造.png",
        "{{PREV_OUTPUT}}",
        "project/.../场景参考图/场景.png",
        "project/.../风格/风格参考.png"
      ]
    }
  ]
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `mode` | 是 | 固定 `"sequential"`（场内阶段串行、场间并行） |
| `model` | 是 | 固定 `"nano-banana-2"` |
| `output_path` | 是 | 输出目录 |
| `tasks[].id` | 是 | `"anchor-{场号}{阶段}"`，如 `"anchor-1A"`、`"anchor-1B"`、`"anchor-2"` |
| `tasks[].scene` | 是 | **物理场**号字符串 |
| `tasks[].group` | 是 | 阶段标识：同场阶段按播放顺序编号 A、B、C...（如 `"1A"`、`"1B"`）；无阶段拆分时等于场号（如 `"2"`） |
| `tasks[].scene_name` | 是 | 场名称（中文，用于文件名和记录） |
| `tasks[].shot_range` | 是 | 该阶段锚点覆盖的镜头范围，如 `"1-3"`；同场各阶段范围不得重叠、按播放顺序递增 |
| `tasks[].depends_on` | 否* | 同场前一阶段任务 id（*首阶段无；非首阶段必填），如 `"anchor-1A"`。运行时其成图 URL 替换本任务 `images` 中的 `{{PREV_OUTPUT}}` |
| `tasks[].filename` | 是 | `"锚点_场{场号}{阶段}_{阶段名/场景名}.png"`，如 `"锚点_场1A_断供报信.png"`；无阶段拆分时如 `"锚点_场2_茶肆门口.png"` |
| `tasks[].cast` | 是* | 本阶段锚点镜头在场且有角色参考图的具名角色中文名列表（*纯空镜/无角色帧可为 `[]`）；顺序=角色参考顺序 |
| `tasks[].prompt` | 是 | 7 段单帧 prompt：English control shell + 中文角色/关系/场景/动作/站位/神态/道具/时代/剧情内容；OPENING 第一项为 actor continuity `IDENTITY LOCK`，随后才是场景/动作；含单帧画布声明、禁字幕 TEXT POLICY、精简 AVOID |
| `tasks[].aspectRatio` | 是 | 固定 `"16:9"` |
| `tasks[].imageSize` | 是 | `"2K"` |
| `tasks[].images` | 是 | 见排序规则；顺序为 Highest priority 角色→Previous Phase Anchor（仅非首阶段，`{{PREV_OUTPUT}}`）→Second 场景→Third 道具→Fourth 风格 |

> **场级锚点图完整规则**：
> 1. 每场按角色阶段拆分生成一条或多条 task（阶段拆分见上文「角色阶段拆分」）
> 2. 同场阶段按播放顺序 `depends_on` 串行：非首阶段 `images` 含 `{{PREV_OUTPUT}}`，运行时替换为前一阶段锚点图成图 URL；首阶段无 `depends_on`、无 `{{PREV_OUTPUT}}`
> 3. 场间无依赖，可并行提交
> 4. 无阶段拆分时该场仅一个 task（等价于旧 batch 的单场一张锚点图，向后兼容）

---

### 2.7 完整示例

以下为 2 场任务表示例（LiveAction 风格，16:9）：场1 拆分为双阶段（1A、1B，经 `depends_on` 串行，非首阶段 `images` 含 `{{PREV_OUTPUT}}`），场2 无阶段拆分（单阶段，等价旧 batch 单场一张）：

```json
{
  "mode": "sequential",
  "model": "nano-banana-2",
  "output_path": "project/荼荼茶业-古装/EP04/分镜/视觉锚点",
  "tasks": [
    {
      "id": "anchor-1A",
      "scene": "1",
      "group": "1A",
      "scene_name": "春生茶肆·日/内",
      "shot_range": "1-3",
      "filename": "锚点_场1A_断供报信.png",
      "cast": ["掌柜", "茶客"],
      "prompt": "<双语 7 段 prompt：English control shell + 中文内容；须包含 actor continuity lock 与下方示例的绑定式角色写法>",
      "aspectRatio": "16:9",
      "imageSize": "2K",
      "images": [
        "project/荼荼茶业-古装/全局依赖/角色设定/角色参考图/掌柜_默认妆造.png",
        "project/荼荼茶业-古装/全局依赖/角色设定/角色参考图/茶客_默认妆造.png",
        "project/荼荼茶业-古装/EP04/场景参考图/茶馆.png",
        "project/荼荼茶业-古装/EP04/道具参考图/茶罐.png",
        "project/荼荼茶业-古装/EP04/道具参考图/账簿.png",
        "project/荼荼茶业-古装/前期采样/风格/风格参考-繁花.png"
      ]
    },
    {
      "id": "anchor-1B",
      "scene": "1",
      "group": "1B",
      "scene_name": "春生茶肆·日/内",
      "shot_range": "4-7",
      "depends_on": "anchor-1A",
      "filename": "锚点_场1B_立规交锋.png",
      "cast": ["掌柜"],
      "prompt": "<双语 7 段 prompt：先锁 Reference Image 1 character（掌柜角色），再写中文场景/动作/神态；SCENE CONTINUITY 说明空间继承自前一阶段锚点>",
      "aspectRatio": "16:9",
      "imageSize": "2K",
      "images": [
        "project/荼荼茶业-古装/全局依赖/角色设定/角色参考图/掌柜_默认妆造.png",
        "{{PREV_OUTPUT}}",
        "project/荼荼茶业-古装/EP04/场景参考图/茶馆.png",
        "project/荼荼茶业-古装/前期采样/风格/风格参考-繁花.png"
      ]
    },
    {
      "id": "anchor-2",
      "scene": "2",
      "group": "2",
      "scene_name": "春生茶肆门口·日/外",
      "shot_range": "1-2",
      "filename": "锚点_场2_茶肆门口.png",
      "cast": ["掌柜"],
      "prompt": "<双语 7 段 prompt：先锁 Reference Image 1 character（掌柜角色），再写中文场景/动作/神态>",
      "aspectRatio": "16:9",
      "imageSize": "2K",
      "images": [
        "project/荼荼茶业-古装/全局依赖/角色设定/角色参考图/掌柜_默认妆造.png",
        "project/荼荼茶业-古装/EP04/场景参考图/茶肆门口.png",
        "project/荼荼茶业-古装/前期采样/风格/风格参考-繁花.png"
      ]
    }
  ]
}
```

**双语占位 prompt 示例（仅展示编写结构，不可原样提交）**：

```text
IDENTITY LOCK — HIGHEST PRIORITY:
Reference priority (highest to lowest): Highest priority = referenced character identity and actor continuity; Second priority = environment; Third priority = props; Fourth priority = visual style. Identity wins every conflict: environment, props, style, historical appearance, and occupational archetype serve the locked person and never replace the face.
Reference Image 1 character（掌柜角色） must remain recognizable as the same actor/person after all costume, hairstyle, pose, lighting, and environment changes.
Reference Image 1 character（掌柜角色） is the sole identity source for this referenced person; it is the same specific person shown in the image, not a newly generated interpretation.
Reference Image 2 character（茶客角色） must remain recognizable as the same actor/person after all costume, hairstyle, pose, lighting, and environment changes.
Reference Image 2 character（茶客角色） is the sole identity source for this referenced person; it is the same specific person shown in the image, not a newly generated interpretation.
Do not generate a generic Tang Dynasty female shopkeeper. Do not use a historical or occupational archetype as a replacement casting.
For Reference Image 2 character（茶客角色）, do not generate a generic Tang Dynasty tea guest; use the referenced person instead.
If historical appearance conflicts with reference identity, preserve the reference identity and modify only wardrobe, hairstyle, and setting.
The face identity has absolute priority over role archetype, age description, or historical styling.
Referenced characters must look like the same people from the reference images, not similar-looking replacements.
Do not alter facial identity, facial structure, skin features, or body proportions.
Change only clothing and hairstyle required by the historical setting; wardrobe, hairstyle, and environment changes must not create a new person.
Create a professional cinematic film frame for a historical drama film.
This is a visual anchor frame for 春生茶肆·日/内. Generate exactly one image for this single frame only. One single photographic still that fills the entire canvas.

SCENE CONTINUITY:
This is a visual anchor for 春生茶肆·日/内 — the definitive spatial and atmospheric reference for this physical location.
Maintain strict continuity with reference materials: same identity for the referenced cast member; same 茶肆内、右侧木柜台和后墙层架; same props; same lighting atmosphere; same 唐朝盛世. Every unreferenced/background character is not a referenced character, background-only, smaller visual weight, secondary placement, not a main character, not a focal point, never become the visual focus.

REFERENCE IMAGE MAPPING:
Image 1: Character Identity Anchor — Highest priority
Reference Image 1 character（掌柜角色） is the sole identity source.
Image 2: Character Identity Anchor — Highest priority
Reference Image 2 character（茶客角色） is the sole identity source. 茶客坐在左侧茶桌旁。
Image 3: Environment Anchor — Second priority
春生茶肆·日/内 — 茶肆空间，右侧木柜台，茶桌与层架。
Image 4: Prop Detail Anchor — Third priority
茶罐 — 青瓷圆腹罐，釉面裂纹，罐内盛放新茶。
Image 5: Visual Style Anchor — Fourth priority
Live-action historical drama style, controlled cinematic lighting, realistic material texture, high image quality.

FRAME DETAIL:
Purpose:
建立茶肆空间布局并锁定角色站位。
Feeling:
重要消息宣布前短暂而安静的期待。
Scene:
茶肆内，右侧为木柜台，后墙是层架；Reference Image 1 character（掌柜角色）站在右侧柜台后，茶客坐在左侧茶桌旁，两人保持分镜规定的相对位置。
Action:
Reference Image 1 character（掌柜角色）站在右侧柜台后擦拭茶杯。Reference Image 2 character（茶客角色）坐在左侧茶桌旁端起茶杯。
Performance:
Reference Image 1 character（掌柜角色）嘴角带着分镜规定的克制笑意。Reference Image 2 character（茶客角色）抬眼望向掌柜，保持分镜规定的神态。
Composition:
Wide shot, eye-level, balanced spatial blocking.
Camera feeling:
Static camera, locked-off.
Lighting:
Soft directional cinematic lighting, controlled color temperature, realistic material response.
Atmosphere:
茶肆日常中即将发生重要宣布的安静期待。

TEXT POLICY:
Hard ban on burned-in graphics (non-negotiable): No subtitles, captions, lower-thirds, or title cards. No on-screen dialogue text or lyric text. No watermarks, logos, shot numbers, timecode, or UI chrome. Spoken lines exist only as audio in the final edit.
Diegetic in-world text only when the scene itself contains it; preserve original Chinese characters, do not generate pinyin, and do not replace Chinese characters with Latin letters.

CINEMATIC QUALITY:
Live-action historical drama, restrained cinematic color palette, controlled lighting, realistic wood and porcelain material texture, high-resolution image quality.
Camera principles: grounded composition, natural depth, clean photographic detail.

AVOID:
No multi-panel, grid, collage, contact sheet, or split-screen layout; one clean frame only.
No anachronistic costumes for the period or background people.
No unreferenced/background character becomes a main character or focal point.
No empty or lifeless character poses; every referenced character needs a source-backed action and expression.
```

> **示例要点说明**：
> - **场1 阶段 1A（断供报信，shot_range 1-3）**：2 角色 + 场景 + 2 道具 + 风格，无 `depends_on`，无 `{{PREV_OUTPUT}}`（首阶段）
> - **场1 阶段 1B（立规交锋，shot_range 4-7）**：1 角色 + 场景 + 风格，`depends_on: "anchor-1A"`，`images` 在角色之后、场景之前含 `{{PREV_OUTPUT}}`（引用前一阶段锚点成图作为空间连续参考）
> - **场2（茶肆门口，shot_range 1-2）**：单阶段（无角色入场/离场拆分），1 角色 + 场景 + 风格，无 `depends_on`
> - **阶段链**：同场 1A → 1B 按 `depends_on` 串行（后阶段等前阶段成图后再提交）；不同场（场1 与场2）无依赖可并行
> - **shot_range 同场不重叠**：场1 两阶段范围 `1-3` / `4-7` 连续不重叠
> - **cast 长度 = 角色图数 = Character Identity Anchor 数**
> - **Action/Performance 段必须为每个角色写明动作与神态**——这是影视级静帧质感的必要条件

---

## Step 3：执行视觉锚点图生成

任务表编写完成后，加载 art-director 技能，以 sequential 模式执行：

1. **校验**：运行 `python validate_task_table.py --check "视觉锚点_任务表.json"`
2. **路径解析**：任务表中的 `images` 路径为相对路径，Agent 调用 MCP tool 前必须解析为绝对路径（MCP server 的 CWD 与 Agent 不同，相对路径无法解析）
3. **执行（sequential 模式）**：按 art-director sequential 执行
   - 场内阶段串行：同场非首阶段锚点在 `depends_on` 指向的前一阶段成图后提交，其 `{{PREV_OUTPUT}}` 由运行时替换为前阶段成图 URL（空间连续参考）
   - 场间并行：不同场的锚点图无依赖，可并行提交
   - 任一帧 `failed`：不影响其他场，记录事件
4. **下载**：每帧完成后下载到 `output_path`，文件名与 `filename` 一致

> 详细策略见 art-director「执行模式 > 模式二：sequential（场内阶段串行、场间并行）」。无阶段拆分的单阶段场（该场仅一个 task、无 `depends_on`）在 sequential 模式下等价于独立任务，可与其他场并行提交。

---

## Step 4：校验

运行校验器确保任务表格式正确：

```bash
python .opencode/skills/storyboard-generator/scripts/validate_task_table.py \
  --check "project/{项目名}/{剧集号}/分镜/视觉锚点_任务表.json" --verbose
```

校验项：
1. JSON 语法正确性
2. 模型必须在允许集合内（`nano-banana-2` / `nano-banana-pro`）
3. 分辨率必须在允许集合内（`2K` / `4K`）
4. 画面比例必须为 `16:9`
5. `mode` 必须为 `sequential`（场内阶段串行、场间并行）
6. 每个任务 `id`、`scene`、`scene_name`、`group`（阶段标识）、`shot_range` 必填
7. **`depends_on` 仅限同场阶段链**：非首阶段锚点 `depends_on` 必须指向同场前一阶段任务 id；首阶段无 `depends_on`
8. **非首阶段 `images` 必须含 `{{PREV_OUTPUT}}`**（排在角色参考之后、场景参考之前）；首阶段不得含 `{{PREV_OUTPUT}}`
9. **`shot_range` 必填且同场不重叠**：同场多阶段范围按播放顺序递增、禁止重叠（如场1 阶段 1A `1-3`、1B `4-7`）
10. 参考图顺序：Highest priority 角色→Previous Phase Anchor（仅非首阶段）→Second 场景→Third 道具→Fourth 风格
11. images 为具体文件（非目录）或 `{{PREV_OUTPUT}}`
12. Image N: 映射块数量与 images 一致
13. 必需段落标题齐全
14. FRAME DETAIL 含 Purpose 与 Feeling
15. FRAME DETAIL 的 Action 段不得为空（每个 cast 角色须有动作描述）
16. FRAME DETAIL 的 Performance 段不得为空（每个 cast 角色须有神态描述）
17. 禁止焦距 / storyboard / frame N of M / 宫格·拼贴词 / 未解析 `{...}`
18. **`cast` 必填**（可为 `[]`）；每个 cast 名必须出现在对应角色参考路径文件名中
19. 角色参考图数量 = Character Identity Anchor 数量 = `cast` 长度
20. prompt 必须含单帧画布声明（`single` + `fills the entire canvas` 或等价 `exactly one image` + 禁 multi-panel）
21. TEXT POLICY 必须含禁字幕（`subtitle`/`No subtitles` 等）
22. AVOID 保留 multi-panel/layout、时代错位、背景人物降权与 empty/lifeless pose 等必要禁令；字幕仅由 TEXT POLICY 检查，不要求 AVOID 重复
23. AVOID 必须含 empty poses 禁令（`empty or lifeless character poses` 或等价表述）
24. 有角色参考时，`IDENTITY LOCK — HIGHEST PRIORITY` 必须位于 `SCENE CONTINUITY` 之前，并逐一写明对应 `Reference Image N character（中文角色名/职责）` 是该角色的 `sole identity source` 与 actor continuity lock；必须包含脸部身份绝对优先、历史冲突只改 wardrobe/hairstyle/setting、同一 actor/person 和非替换人物语义；不得用 `ALL characters` 混合 referenced 与 unreferenced/background characters
25. 每个 unreferenced/background character 除时代服化与中文来源动作/站位外，必须包含 `not a referenced character, background-only, smaller visual weight, secondary placement, not a main character, not a focal point, never become the visual focus`
26. 元约束净化：prompt 不得含「提示词净化规范」11 类必删元约束残留（段落放置/编排指令、Decision rule、括号标签机制解释、编写者脑补禁令、编译器/流水线说明、中文事实保留指令、占位符机制解释、锚点职责定位从句、锚点职责块、Mapping 内机制解释、道具配对说明括号）；校验器对此类残留输出告警（不阻塞通过，但须修正后重提）
