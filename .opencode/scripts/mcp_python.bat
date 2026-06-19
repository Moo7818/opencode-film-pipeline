@echo off
REM 跨平台 Python 启动脚本 (Windows)
REM 用于 opencode MCP 服务器配置，自动检测 .venv 中的 Python
REM
REM 用法：scripts\mcp_python.bat <script_path> [args...]
REM 示例：scripts\mcp_python.bat .opencode\mcp-servers\grsai-server\server.py

setlocal

REM 获取项目根目录（.opencode\scripts\ 的上两级目录）
set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..\..

REM 虚拟环境路径
set VENV_DIR=%PROJECT_ROOT%\.venv

REM 检测 Python 路径
if exist "%VENV_DIR%\Scripts\python.exe" (
    set PYTHON=%VENV_DIR%\Scripts\python.exe
) else if exist "%VENV_DIR%\bin\python3" (
    set PYTHON=%VENV_DIR%\bin\python3
) else (
    echo 错误：未找到虚拟环境，请先运行: uv sync >&2
    exit /b 1
)

REM 执行目标脚本
"%PYTHON%" %*
