# Templates

Use these as default output shapes. Compress or expand as needed, but keep the same logic.

## 1. Sequence Drama Map

```md
## Sequence X: [Name]

戏核：
- ...

这段结束后改变了什么：
- ...

观众站位：
- ...

主要压力来源：
- ...

镜头总策略：
- ...

不要怎么拍：
- ...
```

## 2. Scene Dramatic Core + Shot Flow

```md
## Scene X: [Name]

戏核：
- ...

观众站位：
- ...

shot flow：
- `... -> ... -> ...`

开场景别：
- ...

第一刀 close-up：
- ...

高潮镜头职责：
- ...

reaction owner：
- ...

连续性锚点：
- ...

最容易犯的错：
- ...
```

## 3. Rough Thumbnail Execution

```md
### SX-P1

- 画面：
- 景别：
- 任务：
- cut 动机：
- hold：
- 声音 / 台词：（情绪）"台词内容"
- 台词时长：[字数]字 / [语速] chars/s = 朗读[基础]s + 停顿[停顿]s = 需时[总]s / hold [hold]s [✅/⚠️]
```

> **情绪标注**：括号中为 8 种情绪之一，决定语速系数和停顿：
> 悲恸(0.50x) | 犹豫(0.60x) | 沉重(0.75x) | 低语(0.85x) | 正常(1.00x) | 急促(1.15x) | 激昂(1.25x) | 爆发(1.30x)
>
> **台词时长由 Agent 自主计算**，无需脚本。计算规则：
> - 朗读时间 = 中文字数 ÷ 情绪语速（基础 4.0 × 情绪系数）
> - 标点停顿：逗号 0.3s / 句号·感叹号·问号 0.5s / 省略号 0.8s / 破折号 0.5s
> - 情绪停顿：悲恸每分句 +0.5s / 犹豫 +0.4s / 沉重 +0.3s / 低语 +0.2s / 爆发 +0.1s
> - 校验：需时 ≤ hold（严格容纳）
>
> 无台词面板填：`- 声音 / 台词：`（留空），`- 台词时长：` 留空。

## 4. Shot-Language Refinement

```md
## Scene X

这一场真正要讲的是：

`...`

镜头语言：
- ...

第一刀该不该近：
- ...

cut 动机：
1. ...
2. ...

节奏：
- ...

绝对不要：
- ...
```

## 5. Key Panel

```md
### SX-K1 [Name]

- 画面：
- 景别：
- 构图：
- 作用：
- 进 cut：
- 出 cut：
- hold：
```

## 6. Shot-By-Shot Scene Board

```md
### X-1

- 景别 / 画面：
- 动作 / 表演：
- 声音 / 台词：（情绪）"台词内容"
- 台词时长：[字数]字 / [语速] chars/s = 朗读[基础]s + 停顿[停顿]s = 需时[总]s / hold [hold]s [✅/⚠️]
- 切换职责：
```

> 台词时长由 Agent 自主计算，计算规则同 Template 3。

## 7. Full Rough Board Summary

```md
## 一、全片镜数分配
- ...

## 二、全片板序
- Scene 1 ...

## 三、核心节奏
- 起
- 承
- 转
- 合

## 四、review 只看这几件事
- ...
```

## 8. Clean-Pass Rules

```md
## 一、clean 能改什么
- ...

## 二、clean 绝对不能乱改什么
- ...

## 三、优先 clean 的镜头
- ...

## 四、最终检查
- ...
```

## 9. Final Delivery

```md
# [Project] 最终分镜总稿 v1

说明：
- this file is produced after clean-pass rules are locked
- this is the single source of truth
- process files become appendices

## 一、全片硬锁
- ...

## 二、最终分镜
### 1-1
- 景别：
- 画面 / 构图：
- 动作 / 表演：
- 机位 / 运动：
- 声音 / 台词：
- cut / hold / 连续性：

## 三、最终版本使用规则
- ...
```

```md
# [Project] 最终交付说明 v1

主交付物：
- ...

附录用途：
- ...

硬锁项：
- ...

说明：
- final master is not a rough-board summary
- final master must already absorb clean-pass constraints
- if a collaborator can continue production by reading only the master plus this note, the delivery is complete
```

## Naming Convention

When the user wants files, use stage-explicit names such as:

- `project_sequence戏剧地图_v1.md`
- `project_scene戏核与shot_flow_v1.md`
- `project_rough_thumbnails_pass2.md`
- `project_关键场次key_panel_v1.md`
- `project_全片rough_board总稿_v1.md`
- `project_clean_pass执行规范_v1.md`
- `project_最终分镜总稿_v1.md`
- `project_最终交付说明_v1.md`

## 10. Dialogue Timing Validation

Agent 在 A5 步骤中逐面板计算台词时长，超时面板就地修复。此表为校验汇总，嵌入分镜稿末尾。

```md
## Scene X Timing Validation

| Panel | 台词字数 | 情绪 | 语速 | 朗读 | 停顿 | 需时 | hold | 填充率 | 状态 |
|-------|---------|------|------|------|------|------|------|--------|------|
| X-Y   | xx      | 情绪  | x.x  | x.xs | x.xs | x.xs | x.xs | xxx%   | ✅/⚠️ |

跨面板连续（如有）：
- 关联 panel：X-Y → X-Z
- 台词总需时：xx.xs
- 面板总时长：xx.xs
- 状态：✅/⚠️

超时面板修复优先级：
1. 压缩台词 — 删减修饰词和重复
2. 调整情绪 — 检查情绪标注是否过重
3. 延长 hold — 增加面板时长
4. 拆分面板 — 拆为连续面板
```

> 校验原则：台词需时 ≤ 面板 hold（严格容纳，无溢出容忍）
> 总需时 = 朗读时间（字数 ÷ 情绪语速）+ 标点停顿 + 情绪停顿
> Agent 自主计算，无需脚本

## 11. Spatiotemporal Story Node Map

Agent 在 A2 步骤中通过分场手段将剧情分解为不同时间流逝状态下的故事节点。戏剧不是物理时空的 1:1 复现——银幕几秒可能对应故事世界数小时/数天/数年，只有剧情点才回归实时。

```md
## 时空故事节点表

| 节点 | 时间流逝 | 故事世界时长 | 银幕预估时长 | 关键信息 | 分场依据 |
|------|---------|-------------|-------------|---------|---------|
| N1   | 压缩    | 三年        | 3s          | 交代背景与人物关系 | 跨越大段时间，非剧情点 |
| N2   | 实时    | 数分钟      | 7s          | 主角对峙与转折 | 剧情转折点，回归物理时空 |
| N3   | 膨胀    | 一瞬        | 4s          | 关键揭晓的微表情 | 放大决定性瞬间 |

时间跳跃点识别：
- 显式标记：{剧本中"三日后""翌日""半年后"等时间词}
- 隐式流逝：{场景切换隐含的时间跨度}

分场原则：
- 时间流逝类型变化处即为分场边界
- 实时节点对应剧情点（转折/对峙/揭晓），银幕时间 ≈ 故事时间
- 压缩节点用于快速交代，可用蒙太奇/跳切/旁白带过
- 膨胀节点用于放大关键瞬间，银幕时间 > 故事时间
```

> 此表作为 A3 场次戏剧地图的分场依据，每个故事节点对应至少一个戏剧段落。

## Writing Rule

Templates are there to keep the work executable.

Do not let them become dead bureaucracy.
If a section does not help the board artist, tighten it or remove it.
