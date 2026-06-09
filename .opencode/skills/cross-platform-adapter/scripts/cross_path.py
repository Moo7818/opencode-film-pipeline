#!/usr/bin/env python3
"""Cross-platform path utilities for .trae skills.

Provides helpers for handling paths, temporary directories, and external
tool dependencies across Windows and Unix environments.
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Optional


def ensure_dir(path: str | Path) -> Path:
    """Ensure a directory exists, creating parent directories as needed.

    Cross-platform replacement for ``mkdir -p``.
    """
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def temp_dir(prefix: str = "trae_") -> Path:
    """Create a temporary directory in a cross-platform location.

    Returns the Path to the new directory. Caller is responsible for cleanup.
    """
    return Path(tempfile.mkdtemp(prefix=prefix))


def normalize_path(path: str | Path) -> str:
    """Normalize a path to use OS-native separators.

    On Windows: converts forward slashes to backslashes.
    On Unix: converts backslashes to forward slashes (rare).
    """
    return str(Path(path))


def to_forward_slash(path: str | Path) -> str:
    """Convert path to use forward slashes (for display or cross-platform URLs)."""
    return str(path).replace("\\", "/")


def require_tool(name: str, hint: Optional[str] = None) -> str:
    """Find an executable on PATH, or exit with a platform-specific error message.

    Args:
        name: The executable name (e.g., "ffmpeg", "soffice").
        hint: Optional custom installation hint. If not provided, a default
              platform-specific hint is used.

    Returns:
        The full path to the executable.

    Raises:
        SystemExit: If the tool is not found.
    """
    path = shutil.which(name)
    if path:
        return path

    default_hints = {
        "ffmpeg": {
            "win32": "从 https://ffmpeg.org/download.html 下载并加入 PATH",
            "cygwin": "apt-cyg install ffmpeg",
            "linux": "sudo apt install ffmpeg 或 sudo dnf install ffmpeg",
            "darwin": "brew install ffmpeg",
        },
        "ffprobe": {
            "win32": "从 https://ffmpeg.org/download.html 下载并加入 PATH",
            "linux": "sudo apt install ffmpeg",
            "darwin": "brew install ffmpeg",
        },
        "soffice": {
            "win32": "安装 LibreOffice: https://www.libreoffice.org/download/",
            "linux": "sudo apt install libreoffice",
            "darwin": "brew install --cask libreoffice",
        },
        "gcc": {
            "win32": "安装 MinGW-W64 或 Visual Studio Build Tools",
            "linux": "sudo apt install build-essential",
            "darwin": "xcode-select --install",
        },
    }

    tool_hints = default_hints.get(name, {})
    platform = sys.platform
    platform_str = {"win32": "Windows", "cygwin": "Cygwin", "darwin": "macOS"}.get(
        platform, "Linux"
    )

    platform_tip = tool_hints.get(platform)
    if not platform_tip:
        # Try linux hints for linux-like platforms
        for key in ("linux", "darwin"):
            platform_tip = tool_hints.get(key)
            if platform_tip:
                break
    if not platform_tip:
        platform_tip = f"请安装 {name}"

    msg = hint or f"错误: 未找到 '{name}'。在 {platform_str} 上: {platform_tip}"
    print(msg, file=sys.stderr)
    sys.exit(1)


def is_windows() -> bool:
    """Check if running on Windows."""
    return sys.platform == "win32" or os.name == "nt"


def python_command() -> str:
    """Return the correct Python command for the current platform.

    On Unix: returns "python3".
    On Windows: returns "python" (python3 usually doesn't exist).
    """
    if is_windows():
        return "python"
    return "python3"
