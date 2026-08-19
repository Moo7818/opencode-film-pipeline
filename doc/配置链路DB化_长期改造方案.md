# 配置链路 DB 化 · 长期改造方案

> 目标：废除 `project_config.json` 文件契约，以 `project_configs` 表为唯一配置真相源，为 meta-server 补全配置读写接口，下游全部消费方（orchestrator、各内容 skill、脚本）迁移到统一通道，修复 coordinator 迁移 SQLite 后造成的上下游断裂。

## 一、背景与故障根因

coordinator 从手写 JSON 四件套迁移到 meta-server（SQLite）后，配置只在 `meta_init_project` 时一次性写入 `project_configs` 表，不再落盘 `.meta/projects/{uuid}/project_config.json`。但下游 5 个以上 skill 的文档与脚本仍以该文件为运行时契约，导致：

1. **读路径断裂**：`run_video_pipeline.py` 的 `_load_project_config()` 遍历 `.meta/projects/*/project.json` 反查，新体系不创建该文件，恒返回 None；canvas_uuid 查不到直接 `sys.exit(1)`，`storyboard_mode` / `reference_image_mode` / `suppress_run` 静默回落默认值。
2. **写路径断裂**：video-director 按契约需写回 `workspace_id` 与 `episodes.{剧集}.canvas_uuid`，但文件不存在、coordinator 铁律禁止碰 `.meta/`、meta-server 又无配置更新工具，三方封死。
3. **接口不闭环**：`meta_query` 无 config scope，`project_configs` 表只写不读，是数据黑洞。
4. **分支判定失效**：pipeline.md / orchestrator.md 规定子 agent 自行读 `project_config.json` 决定条件分支（如阶段 6 按 `reference_image_mode` 分支），判定依据消失。

## 二、目标态架构

### 2.1 核心决策

| 决策点 | 结论 | 理由 |
|--------|------|------|
| 唯一真相源 | `project_configs` 表（CONFIG_FIELDS 默认值 + DB 存量合并后对外） | 单一数据源，事务与审计内建 |
| 文件契约 | 彻底废除。磁盘不再有 `project_config.json`；仅 `meta_export_project` 的 ZIP 内保留为导出格式 | 避免双写漂移；export 是交付格式不是运行态 |
| agent 读通道 | `meta_query(scope=config)`，只读，对全部子 agent 开放 | 复用既有工具，零学习成本；只读无安全风险 |
| agent 写通道 | 新增 `meta_update_config`，点路径更新 + 字段级写权限白名单（ACL）+ actor 事件审计 | 写是真实需求（canvas_uuid 写回），封死只会再造文件旁路 |
| 脚本通道 | `run_video_pipeline.py` 去配置化：全部参数由调用方显式传入，缺关键参数硬失败 | 脚本无 MCP 能力；静默回退默认值是本次故障放大器，必须消除 |
| "唯一写者"语义 | 从"唯一写者是 coordinator"改为"唯一写通道是 meta_* 工具" | 本质诉求是防绕库直改、保证事务审计，不是所有写都过 coordinator 的手 |

### 2.2 消费矩阵（上下游能否消费的逐项论证）

| 消费方 | 消费内容 | 通道 | 前提与说明 |
|--------|----------|------|------------|
| orchestrator | 不消费配置内容 | 无 | 保持"不知道项目走哪个分支"的设计；仅在 spawn 指令中携带 project_id（项目名） |
| storyboard-generator | `storyboard_mode`、`reference_image_mode`、`aspect_ratio` | `meta_query(scope=config)` | 纯 agent，有 MCP；文档从"读文件"改为"调工具" |
| roles/scene/prop-ref-generator | 项目参数、剧集号、风格配置 | `meta_query(scope=config)` | 同上 |
| video-director-libtv（含 seedance-prompt-optimizer 内联阶段） | 全部视频参数、`video_prompt_mode`、`episodes.{EP}.canvas_uuid`、`suppress_run` | 读 `meta_query`；写 `meta_update_config`（仅 `workspace_id`、`episodes.*`） | 唯一需要写配置的子 agent |
| run_video_pipeline.py | 模型、比例、分辨率、分镜模式、canvas_uuid | CLI 参数显式传入 | 无 MCP；由 video-director 读配置后拼参调用 |
| meta-server export/import | 配置快照 | ZIP 内 `project_config.json`（导出格式） | 外部消费方（交付、备份）格式不变 |

### 2.3 写权限白名单（ACL）

| 字段 | 可写 actor | 说明 |
|------|-----------|------|
| `workspace_id` | video-director-libtv、project-coordinator | 首次创建工作区时写入 |
| `episodes.*`（含 `episodes.{EP}.canvas_uuid`） | video-director-libtv、project-coordinator | 每集首次创建/绑定画布时写入 |
| `suppress_run` | project-coordinator | 用户决策类开关 |
| 其余全部字段（model、aspect_ratio、resolution、mode、enable_sound、storyboard_mode、reference_image_mode、video_prompt_mode、has_audio_reference 等） | 仅 project-coordinator | 创建时定，运行期只读；变更走 coordinator |

ACL 在 `meta_update_config` 服务层校验：越权写入返回 `invalid`（错误信息注明 ACL 拒绝与允许的 actor），不做任何部分写入。

## 三、接口规格

### 3.1 meta_query 扩展：scope=config

```
参数：
  project_id   与 project_name 二选一（子 agent 常只持项目名，免二次查询）
  scope="config"
返回：
  {
    "project_id": "...", "name": "...", "updated_at": "...",
    "config": { ...CONFIG_FIELDS 默认值与 DB 存量合并后的完整配置... }
  }
语义：
  只读，不产生事件。合并逻辑与 init_project 的 merged 一致，
  保证消费方永远拿到全字段配置，无需自行补默认值。
```

### 3.2 新工具 meta_update_config

```
参数：
  project_id  必填
  updates     必填，点路径 KV 字典，如 {"episodes.EP01.canvas_uuid": "uuid-x", "workspace_id": 3}
  actor       必填，ACTORS 枚举值，标识调用者身份
语义：
  单事务 read-merge-write（SQLite WAL 串行化，无并发丢失更新）。
  点路径仅支持两层（a.b），更深路径 invalid。
  未知字段 invalid；ACL 越权 invalid；actor 非法 invalid。
  校验失败不改任何状态（沿用现有事务语义）。
事件：
  config.updated  data={actor, changed_keys, updates}
返回：
  {"config": 合并后完整配置, "changed_keys": [...]}
```

### 3.3 常量与事件变更

- `templates.py` 新增 `CONFIG_WRITE_ACL`（字段 → actor 集合映射，权威源），与 `CONFIG_FIELDS` 并列。
- `CONFIG_FIELDS` 补齐 `video_prompt_mode: "optimized"`（当前与 schema 存在差异，一并修复）。
- `events.md` 事件清单新增 `config.updated`。
- `ARTIFACT_TYPES` 保留 `project_config`（legacy import 兼容），但 `register_artifact` / `archive_artifact` 对该 type 一律返回 `invalid`——运行时不再存在此文件，不应注册；`TYPE_TO_DIR` 中该条目标注"仅 export 用途"。

## 四、脚本去配置化设计（run_video_pipeline.py）

原则：**脚本不读任何持久化配置，所有配置来自调用方显式传参；关键参数缺失硬失败，绝不静默回退。**

| 现状函数 | 处置 |
|----------|------|
| `_load_project_config()` | 删除 |
| `lookup_episode_canvas_uuid()` | 删除；`--canvas-uuid` 改为必填，缺失即报错退出（提示：先 `meta_query(scope=config)` 查 episodes 映射，无则创建画布后 `meta_update_config` 写回） |
| `load_storyboard_mode()` | 删除文件读取；`--storyboard-mode` 必填（由 video-director 从配置读出后显式传入） |
| `load_reference_image_mode()` | 删除文件读取；新增 `--reference-image-mode` 必填参数，控制分镜图/视觉锚点自动扫描逻辑 |
| `suppress_run` 检查（步骤5） | 从脚本移除；改由 video-director 在决定加 `--run` 前自查配置（SKILL 流程约束） |
| `CONFIG_DEFAULTS` | 仅保留 `ratio` / `resolution` / `enableSound` / `count` 的 argparse 本地默认；`model` 改为必填（模型名错误是高危静默故障，禁止默认） |

video-director 调用模板（写入其 SKILL.md）：

```
1. meta_query(scope=config, project_name=...) 读配置
2. 检查 suppress_run：true 则拒绝 --run（无论用户是否要求）
3. 检查 episodes.{EP}.canvas_uuid：无则创建画布，meta_update_config 写回
4. 按 video_prompt_mode 决定提示词流程（optimized 走 seedance-prompt-optimizer 内联适配）
5. 拼参调用 run_video_pipeline.py（全部参数显式）
```

## 五、逐文件改动清单

### A 组：meta-server（P1）

| 文件 | 改动 |
|------|------|
| `src/meta_server/templates.py` | 新增 `CONFIG_WRITE_ACL`；`CONFIG_FIELDS` 补 `video_prompt_mode`；`TYPE_TO_DIR` 的 project_config 条目注释标注仅 export 用途 |
| `src/meta_server/service.py` | `query()` 增加 config scope（支持 project_name 反查）；新增 `update_config()`（事务、点路径合并、ACL、事件）；register/archive 拒绝 type=project_config |
| `src/meta_server/server.py` | `meta_update_config` 工具注册与 docstring；`meta_query` docstring 补 config scope |
| `README.md` | 工具表 9 → 10 个；补 config 读写说明与 ACL 表 |
| `temp/test_meta_server.py` | 新增用例：query config（含 project_name 反查、默认值合并）、update 点路径合并、ACL 越权拒绝、未知字段拒绝、actor 枚举拒绝、事件落库 |

### B 组：脚本（P2，与 A 组并行）

| 文件 | 改动 |
|------|------|
| `.opencode/skills/video-director-libtv/scripts/run_video_pipeline.py` | 按第四节表格执行；模块 docstring 同步更新 |

### C 组：video-director-libtv skill（P3）

| 文件 | 改动 |
|------|------|
| `SKILL.md` | 字段来源表整体改写：读来源改为 `meta_query(scope=config)`，写来源改为 `meta_update_config`（workspace_id / episodes）；前置条件更新；suppress_run 检查前移到 agent 层；补第五节调用模板 |
| `references/storyboard-to-libtv.md` | 字段对应表、模式优先级（删除"project_config.json 回退"层，仅剩 CLI 参数）、resolution/enableSound 映射说明同步 |
| `references/workflow.md` | workspace_id / canvas_uuid 的"写回 project_config.json"流程改为 meta_update_config 流程 |
| `references/pipeline-script.md` | 参数表更新：`--canvas-uuid` / `--model` / `--storyboard-mode` / `--reference-image-mode` 标注必填 |
| `references/workflow-examples.md` | 示例改为显式全参调用 |

### D 组：其他内容 skill（P4）

| 文件 | 改动 |
|------|------|
| `storyboard-generator/SKILL.md` | 输入表与阶段交接说明：`project_config.json` 改为 `meta_query(scope=config)` |
| `storyboard-generator/references/phase-b-detailed.md`、`phase-b-simplified.md`、`phase-2-visual-anchors.md`、`phase-2-storyboard-images.md` | "Agent 仅从磁盘读取：…project_config.json…" 改为"从 meta_query(scope=config) 读取配置，磁盘仅读组文件与参考图目录" |
| `scene-ref-generator/rules/episode.md` | 路径表删除 project_config.json 行，改为工具调用说明 |
| `seedance-prompt-optimizer/SKILL.md` | `video_prompt_mode` 来源改为 meta_query |

### E 组：rules 与 coordinator（P5）

| 文件 | 改动 |
|------|------|
| `.opencode/rules/pipeline.md` | 阶段 6 说明：按 `reference_image_mode` 分支，来源改为 meta_query |
| `.opencode/rules/orchestrator.md` | "子 agent 自行读取 project_config.json 确定执行分支"改为"子 agent 自行 `meta_query(scope=config)`"；明确 spawn 指令必须携带 project_id |
| `project-coordinator/SKILL.md` | 铁律 4 改写为"唯一写通道 = meta_* 工具（含字段级 ACL）"；工具总览补 meta_update_config；config 变更操作流程（含非 coordinator actor 经由本技能代写的协作约定） |
| `project-coordinator/rules/project_management.md` | 表结构说明补 CONFIG_WRITE_ACL；project_configs 行补读写路径 |
| `project-coordinator/rules/events.md` | 补 `config.updated` 事件类型 |
| `project-coordinator/rules/manifest.md`、`logs.md` | project_config 路径行改为"仅存在于导出 ZIP" |
| `.opencode/schemas/project-config.json` | description 更新（存储位置改为 DB，读写经 meta_* 工具）；字段结构不变 |

### F 组：人读文档（P6）

| 文件 | 改动 |
|------|------|
| `README.md` | 管线总览中 project_config.json 表述更新 |
| `doc/流程.html` | 阶段 1 说明与配置模板区块改为 DB + 工具调用示意 |

## 六、实施阶段与依赖

```
P1 meta-server 接口 + 测试 ──┬──→ P3 video-director skill 文档 ──→ P6 文档清理与全库验收
P2 脚本去配置化（独立并行）─┘   P4 其他 skill 文档（仅依赖 P1 定稿）
                                P5 coordinator 铁律与 rules（仅依赖 P1）
```

- P1、P2 可并行：脚本改造不依赖新工具（它本来就不该依赖任何存储）。
- P3 依赖 P1 + P2 定稿（调用模板需引用最终参数表与工具签名）。
- 每阶段完成后跑一次全库 `grep project_config.json`，监控残留引用收敛。

## 七、验收标准

1. **引用归零**：`.opencode/`（skills、rules、schemas、scripts）与根 README 中，`project_config.json` 的运行时路径引用（`.meta/projects/...`）归零；仅 meta-server（export/import 实现与 README）、本方案文档、doc/ 历史文档允许保留。
2. **脚本硬失败**：`run_video_pipeline.py --build` 缺 `--canvas-uuid` 或 `--model` 时以非零退出码报错，无任何静默默认行为。
3. **无文件落盘**：新项目从 `meta_init_project` 到 `video_generation` 全流程，磁盘不出现 `project_config.json`。
4. **读写闭环**：`meta_update_config` 写入 `episodes.EP01.canvas_uuid` 后，`meta_query(scope=config)` 可读到合并值；events 表存在对应 `config.updated` 记录（含 actor 与 changed_keys）。
5. **ACL 生效**：actor=video-director-libtv 尝试写 `model` 字段被拒（invalid），DB 无变更。
6. **端到端**：以一个测试项目走完 init → 分镜（两种 storyboard_mode 各一）→ 参考图（reference_image_mode 分支）→ 视频生成准备（canvas_uuid 写回 + 二次运行复用），全程配置仅经 DB。

## 八、风险与对策

| 风险 | 对策 |
|------|------|
| 子 agent 会话未放行 meta MCP（tools allowlist 缺失） | P1 落地时逐一核查 opencode.json 及各 agent 配置，`meta_query` 只读放行无安全风险；这是 P4 文档切换的前置检查项 |
| actor 自报身份无法强认证 | ACL 白名单收敛可写字段（仅 workspace_id / episodes.*）；config.updated 事件留全审计，异常写入可追溯可回滚 |
| export ZIP 的外部消费方依赖 project_config.json | 导出格式保持不变（5 文件结构原样），仅运行态去文件化 |
| 脚本全参必填后人工裸调不便 | SKILL.md 提供标准调用模板；脚本 `--help` 输出完整示例；这是有意设计（宁可失败可见，不可默认错跑） |
| 并发写 episodes（多集同时建画布） | 单事务 read-merge-write + WAL 已串行化；点路径合并避免整树覆盖 |
| 旧项目配置仍在旧 JSON 里 | 走既有 `meta_import_legacy`（已支持 project_config.json 归一化导入），不新增迁移逻辑 |

## 九、回滚预案

本方案不设双写（双写即重新引入漂移）。极端回滚手段：`meta_export_project` 导出 ZIP 后解包落盘 `project_config.json` 与 `project.json` 到 `.meta/projects/{uuid}/`，临时恢复 B/C 组改造前的文件读取逻辑（git revert B 组脚本提交）。此为应急通道，不作为运行态长期共存。
