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

## 11. Spatiotemporal Story Node Map + Physical Scene Map

A2 分两层：**故事节点**（时间流逝）与 **物理场**（连续空间）。节点 ≠ 场。戏剧不是物理时空 1:1 复现，但**分镜的「场」必须按物理空间划分**，以便下游串行参考帧链在同空间内连续。

```md
## 时空故事节点表

| 节点 | 物理空间 | 日夜/时段 | 时间流逝 | 故事世界时长 | 银幕预估 | 关键信息 |
|------|---------|----------|---------|-------------|---------|---------|
| N1   | 春生茶肆·内 | 日 | 实时 | 约5分钟 | 13s | 会员制发布与师徒问答 |
| N2   | 春生茶肆门口·外 | 日 | 实时 | 约2分钟 | 8s | 赵胖偷窥碰壁 |
| N3   | 春生茶肆·内 | 日 | 微压缩 | 约2小时 | 9s | 排队办卡（与 N1 同空间） |
| N4   | 春生茶肆·内 | 日 | 实时 | 约3分钟 | 11s | 小二翻簿（与 N1 同空间） |
| N5   | 赵胖包子铺·内 | 日 | 实时 | 约5分钟 | 11s | 派人打探 |
| N6   | 春生茶肆·内 | 夜 | 膨胀 | 约5分钟 | 14s | 夜思独白（同地但日→夜） |

## 物理场归并表（A3 分场依据 — 以本表为准）

| 场号 | 物理空间 | 日夜 | 含节点 | 场内组规划（戏剧节拍） |
|------|---------|------|--------|----------------------|
| 1 | 春生茶肆·内 | 日 | N1,N3,N4 | 组1发布 / 组2排队 / 组3翻簿 |
| 2 | 春生茶肆门口·外 | 日 | N2 | 组4偷窥碰壁 |
| 3 | 赵胖包子铺·内 | 日 | N5 | 组5打探 |
| 4 | 春生茶肆·内 | 夜 | N6 | 组6夜思 |

分场硬规则：
- **场 = 同一连续物理空间 + 连续故事时间**（与 producer 场景设定的物理空间一致）
- 物理空间切换 → 必须新开场
- 同地显著时间断裂（日→夜、"三日后"）→ 新开场
- **禁止**把同空间多个戏剧节拍拆成多场；节拍用场合内的「组」表达
- 故事节点只服务节奏/时长，**不**直接映射为一场一节点
```

> A3 场次戏剧地图必须按「物理场归并表」建场，不得按节点表一对一拆场。

## Writing Rule

Templates are there to keep the work executable.

Do not let them become dead bureaucracy.
If a section does not help the board artist, tighten it or remove it.
