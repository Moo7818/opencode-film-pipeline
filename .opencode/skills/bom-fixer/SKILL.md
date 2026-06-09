---
name: bom-fixer
description: 快速检测和去除文件中的 UTF-8 BOM（Byte Order Mark）编码头，以及检测和修复 PowerShell 默认编码（GBK 代码页 936）导致的 UTF-8 中文乱码。当 Agent 遇到以下情况时必须触发此技能：(1) 读文件时首行出现不可见字符/编码错误 (2) JSON/YAML 解析失败且报错指向文件开头 (3) 用户提到"BOM"、"乱码"、"编码问题"、"UTF-8 BOM" (4) 用户要求"检查编码"或"修复编码" (5) 在 file operations 之前主动扫描预防 (6) 中文内容出现诡异乱码（如"娓呮偁"等 GBK 误读特征）(7) PowerShell 读取 UTF-8 JSON 文件后的内容异常。也适用于 Windows 文件迁移到 Linux/Python 环境中出现的各种编码不兼容问题。
---

# BOM 编码修复

快速扫描和去除 UTF-8 BOM（Byte Order Mark），避免因 BOM 导致的文件解析异常。

## 为什么需要这个技能

UTF-8 BOM 是 Windows 平台（记事本等编辑器）自动在文件开头插入的 3 字节头 `EF BB BF`。它不是可见字符，但会被解析器当成数据，导致：

- **JSON 解析失败** — 首行出现 Unexpected token
- **YAML 解析异常** — 文档开始处多了不可见字符
- **Python 脚本异常** — `SyntaxError: Non-UTF-8 code starting with '\xef'`
- **Shell 脚本崩溃** — `#!/usr/bin/env` 前多了 3 字节
- **Git diff 显示异常** — 文件开头多出 `ï»¿`

一次扫描+修复只需几秒钟，可以避免后续多轮排查。

---

## 脚本快速参考

所有操作通过 `scripts/fix_bom.py` 完成：

```bash
# 扫描：检查目录中有无 BOM 文件（不修改）
python "{skill_dir}/scripts/fix_bom.py" --scan project/

# 修复：扫描并自动去除 BOM
python "{skill_dir}/scripts/fix_bom.py" --fix project/清悠居_思辰龙飞凤舞/

# 修复特定文件列表
python "{skill_dir}/scripts/fix_bom.py" --fix-files temp/request.json temp/response.json

# 检测未知文件的编码
python "{skill_dir}/scripts/fix_bom.py" --check-encoding temp/unknown.txt
```

退出码说明：`0` = 全部成功或无 BOM | `1` = 部分失败。

---

## Agent 工作流

### 场景 1：文件操作前的预防性检查

这是推荐的默认行为。在你开始对 `project/` 或 `temp/` 下的文件做任何读取/写入/修改操作前，**花 2 秒检查 BOM**：

```bash
python "{skill_dir}/scripts/fix_bom.py" --fix temp/
```

如果发现 BOM，脚本会自动修复并报告。这避免了后续所有因 BOM 引发的诡异错误。

### 场景 2：遇到诡异的解析错误

如果出现以下情况，90% 是 BOM 问题：

| 错误特征 | 典型报错 |
|----------|----------|
| JSON 首行解析失败 | `JSONDecodeError: Unexpected UTF-8 BOM` |
| 脚本首行报语法错误 | `SyntaxError: Non-UTF-8 code starting with '\xef'` |
| 文件开头出现不可见字符 | `Â`、`ï»¿` 等 |
| YAML 加载异常 | `yaml.composer.ComposerError: expected stream start` |

**处理方法**：一步到位

```bash
python "{skill_dir}/scripts/fix_bom.py" --fix-files 报错文件路径.json 其他相关文件.yaml
```

脚本会去除 BOM + 自动校验 JSON 语法，无需手动排查。

### 场景 3：批量项目文件修复

当从 Windows 迁移文件到项目时，一次性全量检查：

```bash
# 扫描整个 project 目录
python "{skill_dir}/scripts/fix_bom.py" --scan project/

# 如果发现 BOM 文件，直接改 --scan 为 --fix 全量修复
python "{skill_dir}/scripts/fix_bom.py" --fix project/
```

### 场景 4：检测未知文件的编码

从外部获取的文件，不确定是什么编码：

```bash
python "{skill_dir}/scripts/fix_bom.py" --check-encoding external/data.csv
```

输出格式（NAME=VALUE，易于机器解析）：
```
path=external/data.csv
bom=UTF-8 BOM
encoding_guess=UTF-8
valid_utf8=yes
```

### 场景 5：PowerShell GBK 编码陷阱（中文乱码修复）

> 这是 Windows 环境特有的高频故障：PowerShell 5.1 的 `Get-Content` 默认使用系统代码页（936/GBK）而非 UTF-8 读取文件，导致 UTF-8 编码的中文内容被错误解析为 GBK 字符，产生类似 `娓呮偁灞` 的诡异中文乱码。

**判断标准**：文件自身是有效的 UTF-8，但中文内容明显不对（如拼音化的乱码或 `娓呮偁` 这类不常见的汉字序列）。

**处理流程（参考）**：

1. 先用 `--check-encoding` 确认文件编码
2. 若文件确实是 UTF-8 但内容乱码，则为 GBK 误读，非 BOM 问题。需用 Python 从源文件（情景中的原始正确文件）以 UTF-8 重新读取并写入
3. 如果不确定哪个文件是正确源，检查上游步骤中是否有其他同名文件或原始输入文件
4. 修复后验证 JSON 语法

```bash
# 检测编码状态
python "{skill_dir}/scripts/fix_bom.py" --check-encoding temp/乱码文件.json

# 用 Python 验证 GBK 误读（确认问题）
python -c "correct = open('源文件.json', encoding='utf-8').read(); garbled = correct.encode('utf-8').decode('gbk', 'replace'); print(f'GBK误读结果: {garbled[:80]}')"
```

---

## 文件类型覆盖

脚本默认检查以下扩展名的文件：

`.md` `.py` `.json` `.yaml` `.yml` `.txt` `.cfg` `.ini` `.toml` `.jsonl`

如需自定义，使用 `--extensions` 参数：

```bash
python "{skill_dir}/scripts/fix_bom.py" --fix temp/ --extensions json yaml md
```

自动跳过 `__pycache__/` 和 `.git/` 目录。

---

## 常见问题

**Q: 去除 BOM 会改变文件内容吗？**
A: 不会。BOM 不是文件内容的一部分，它只是编码标记。去除 BOM 后文件的文本内容完全不变。

**Q: 修复 JSON 文件后需要额外检查吗？**
A: 不需要。脚本在去除 BOM 后会自动运行 `json.load()` 验证 JSON 语法，有问题会报错。

**Q: 怎么添加到日常流程？**
A: 推荐在每次文件操作前执行 `--fix temp/`。单次扫描仅需几秒到几十秒，远低于 BOM 导致的排查时间。