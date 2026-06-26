# 部署流程

## 环境依赖

- Python 3.13.x（uv 管理）
- 虚拟环境路径：`.venv/`（项目根目录）
- 依赖声明：`pyproject.toml`（项目根目录）

---

## macOS / Linux

```bash
# 1. 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 创建虚拟环境并安装依赖
uv sync

# 3. 确认系统凭据已就位
# 确保 .opencode/credentials/media_gen_config.json 存在
# （含 GRSAI_API_KEY、COS 配置等）

# 4. 重启 opencode
```

## Windows（PowerShell 7+）

```powershell
# 1. 安装 uv
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 2. 创建虚拟环境并安装依赖
uv sync

# 3. 确认系统凭据已就位
# 确保 .opencode/credentials/media_gen_config.json 存在

# 4. 重启 opencode
```

## 验证

```bash
.venv/bin/python3 --version        # 确认 3.13.x
uv run python -c "import grsai_client; print('OK')"  # 确认依赖正常
```
