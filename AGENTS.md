# 全局行为规则

所有 agent 使用中文推理和对话。

## Python 环境
- 虚拟环境路径：`.venv/`（项目根目录下）
- Python 版本：3.13.13（uv 管理）
- 激活：`source .venv/bin/activate`
- 运行 Python 脚本时务必使用 `.venv/bin/python` 或在已激活的 venv 内执行
- 依赖管理：`uv sync` 同步，`uv add <包>` 新增

## 文件操作规则
- 项目业务文件存放在 `project/` 目录下
- `temp/` 路径下的任何文件**禁止删除**
- `.opencode/` 配置目录只读，业务文件放 `project/`

## PowerShell 编码规范（Windows）
所有文件读写必须显式指定 `-Encoding UTF8`：
- 读取：`Get-Content -Encoding UTF8 -Raw "路径"`
- 写入：`Set-Content -Encoding UTF8 "路径" -Value "内容"`
- Python：`open("路径", "r", encoding="utf-8")` / `open("路径", "w", encoding="utf-8")`
- JSON：`ConvertTo-Json -Depth 10` / `json.dump(data, f, ensure_ascii=False, indent=2)`

## 配置与技能修改规则
- `.opencode/` 下的所有 skill/agent/config 文件必须通过 `skill-engineer` 子 agent（其加载 `skill-creator` 技能）修改，任何 agent 不得直接操作


