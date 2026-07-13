# 产物追踪

## 何时注册产物

以下情况需要注册或更新 `manifest.json`：

| 场景 | 操作 |
|------|------|
| 新产物创建 | 追加新条目 |
| 产物内容更新 | 旧条目标记 `deprecated`，追加新条目 |
| 产物废弃 | 标记 `deprecated` |
| 产物恢复 | 标记 `final` 或 `draft` |

## 核心约束

- **绝不读取产物内容**：SHA-256 哈希只通过二进制流计算，用于文件指纹识别和变更检测，不作为 LLM 分析内容的输入
- **只操作元数据**：统筹 agent 对产物的操作限于：路径、名称、大小、哈希、类型、状态

## 注册流程

**禁止使用 `Read`/`Write` 文件工具。所有文件操作必须通过 `RunCommand` CLI 执行。**

1. **使用 CLI 读取 manifest.json**：
   ```powershell
   # PowerShell (Windows)
   $json = Get-Content -Encoding UTF8 -Raw ".meta/projects/{id}/manifest.json"
   $manifest = $json | ConvertFrom-Json
   ```
   ```bash
   # bash (Unix/macOS)：JSON 读写建议统一用 python3 调用 json 库
   python3 -c "
   import json
   with open('.meta/projects/{id}/manifest.json', 'r', encoding='utf-8') as f:
     m = json.load(f)
   "
   ```
2. 为新产物生成唯一 `id`（`art_001`、`art_002` 递增，或使用 UUID 片段）
3. 计算文件 SHA-256（使用内置脚本，只读二进制流，不解析内容）
4. 获取文件大小
5. 若同路径已有 `final` 状态的条目，将其标记为 `deprecated`
6. 追加新条目
7. **使用 CLI 追加 events.jsonl**：
   ```powershell
   # PowerShell (Windows)
   Add-Content -Encoding UTF8 -Path ".meta/projects/{id}/events.jsonl" -Value '{"timestamp":"...","type":"artifact.created","actor":"project-coordinator","data":{...}}'
   ```
   ```bash
   # bash (Unix/macOS)
   python3 -c "
   import json
   event = {'timestamp':'...','type':'artifact.created','actor':'project-coordinator','data':{...}}
   with open('.meta/projects/{id}/events.jsonl', 'a', encoding='utf-8') as f:
     f.write(json.dumps(event, ensure_ascii=False, separators=(',', ':')) + '\n')
   "
   ```
8. **使用 CLI 写回 manifest.json**：
   ```powershell
   # PowerShell (Windows)
   $manifest | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 -Path ".meta/projects/{id}/manifest.json"
   ```
   ```bash
   # bash (Unix/macOS)
   python3 -c "
   import json
   with open('.meta/projects/{id}/manifest.json', 'w', encoding='utf-8') as f:
     json.dump(m, f, ensure_ascii=False, indent=2)
   "
   ```
9. **校验**：调用 `validate.py` 校验 `manifest.json`、`events.jsonl` 语法，通过后才算完成

> **`actor` 命名规范**：events.jsonl 中的 `actor` 字段必须是 opencode.json 中定义的 skill name（如 `producer`、`storyboard-generator`、`roles-ref-generator`、`scene-ref-generator`、`prop-ref-generator`、`art-director`、`video-director-libtv`、`project-coordinator`），禁止使用 `script_writer`、`character-director` 这类未定义名（character-director 实际对应 skill 是 `roles-ref-generator`）。当事件由 producer 产出剧本触发时，`actor` 应填 `producer`，而非 `script_writer`。详见 `project_management.md` 的 events.jsonl 字段说明。

> **哈希计算（使用内置脚本，无需写临时脚本）**：
> ```powershell
> python scripts/hash.py --fast "project/山与鱼/原始剧本.md"
> ```
> 输出：
> ```
> PATH=D:\Dev_project\...\原始剧本.md
> HASH=sha256-xxxxxxxx
> SIZE=12345
> ```
> 支持同时传入多个文件路径，批量计算。不要创建自定义哈希脚本。
> 
> **`--fast` 说明**：图片文件（.png/.jpg/.jpeg/.gif/.webp）跳过全量 SHA-256，改用修改时间+大小快速指纹，避免 I/O 开销。

## 归档流程

其他 agent 在临时路径生成产物后，统筹 agent 负责将产物移动到项目目录下的正确路径并注册。

**归档与注册的关系**：归档包含注册。归档 = 移动文件 + 注册到 manifest。

**操作步骤**：

1. **接收通知**：其他 agent 通知统筹 agent，提供以下信息：
   - 临时路径：`temp/{batch_id}/{filename}`
   - 产物类型：`storyboard`、`character_ref` 等
   - 元信息：角色名/场景名/剧集号等（用于确定目标路径）
2. **计算目标路径**：根据产物类型和元信息，按路径映射规则确定 `project/{name}/.../{filename}`
3. **使用 CLI 移动文件**（若目标目录不存在，先创建）：

   ```powershell
   # PowerShell (Windows)
   New-Item -ItemType Directory -Force -Path "project/{name}/.../"
   Move-Item -Path "temp/{batch_id}/{filename}" -Destination "project/{name}/.../{filename}" -Force
   ```
   ```bash
   # bash (Unix/macOS)
   mkdir -p "project/{name}/.../"
   mv "temp/{batch_id}/{filename}" "project/{name}/.../{filename}"
   ```
   - 绝不打开或读取文件内容
4. **计算元数据**：`RunCommand` → `python scripts/hash.py "project/{name}/.../{filename}"` 获取 SHA-256 和文件大小（跨平台，python 脚本在 Windows/Unix 通用）
5. **注册产物**：按"注册流程"步骤 1-9 在 `manifest.json` 中追加新条目
6. **记录事件**：向 `events.jsonl` 追加 `artifact.archived` 事件（actor 必须是规范定义的 skill name，详见注册流程末尾的 actor 命名规范）

**路径映射规则**（详见 [统筹管理规范](project_management.md#3-产物归档路径映射)）：

## 产物类型对照

| `type` | 对应目录/文件 |
|--------|--------------|
| `raw_script` | `*/原始剧本.md` |
| `script` | `*/剧本.md` |
| `character_design` | `*/角色设定/具体设定/{角色名}.md` |
| `scene_design` | `*/场景设定/具体设定/{场景名}.md` |
| `prop_design` | `*/道具设定/具体设定/{道具名}.md` |
| `storyboard` | `*/分镜/*.png` |
| `poster` | `*/海报设计/*.png` |
| `reference` | `*/前期采样/**`, `*/角色设定/角色参考图/**` |
| `setting` | `*/全局依赖/全局设定.md`（单一文件，不再使用 `全局设定/` 子目录） |
| `audio_reference` | `*/音色参考/*.wav` |
| `asset_sync` | `temp/分组素材/{剧集号}/角色参考|场景参考|道具参考/`（目录） |
| `other` | 其他类型产物 |

## 查询

- 按 `type` 过滤：获取某类产物的所有版本
- 按 `stage` 过滤：获取某个阶段的所有产物
- 按 `status` 过滤：仅获取最终版（`final`）
