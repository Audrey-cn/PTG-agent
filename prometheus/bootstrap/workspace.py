"""工作空间管理器。."""

import json
import os
from datetime import UTC, datetime

DEFAULT_WORKSPACE_DIR = os.path.expanduser("~/.prometheus/workspace")

BOOTSTRAP_FILES = [
    "AGENTS.md",
    "SOUL.md",
    "IDENTITY.md",
    "USER.md",
    "TOOLS.md",
    "MEMORY.md",
    "HEARTBEAT.md",
    "BOOTSTRAP.md",
]

WORKSPACE_STATE_VERSION = 1
WORKSPACE_STATE_DIRNAME = ".prometheus"
WORKSPACE_STATE_FILENAME = "workspace-state.json"


def resolve_workspace_dir(dir: str | None = None) -> str:
    """解析工作空间目录，默认 ~/.prometheus/workspace，支持环境变量覆盖。"""
    if dir:
        return os.path.expanduser(dir)
    env_dir = os.environ.get("PROMETHEUS_WORKSPACE", "")
    if env_dir:
        return os.path.expanduser(env_dir)
    return DEFAULT_WORKSPACE_DIR


def workspace_state_path(dir: str) -> str:
    """返回 workspace-state.json 的完整路径。"""
    return os.path.join(dir, WORKSPACE_STATE_DIRNAME, WORKSPACE_STATE_FILENAME)


def read_workspace_state(dir: str) -> dict:
    """读取工作空间状态文件，不存在时返回默认空状态。"""
    state_path = workspace_state_path(dir)
    try:
        with open(state_path, encoding="utf-8") as f:
            raw = json.load(f)
            if isinstance(raw, dict):
                raw.setdefault("version", WORKSPACE_STATE_VERSION)
                return raw
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return {"version": WORKSPACE_STATE_VERSION}


def write_workspace_state(dir: str, state: dict) -> None:
    """原子写入工作空间状态文件。"""
    state_path = workspace_state_path(dir)
    state.setdefault("version", WORKSPACE_STATE_VERSION)
    os.makedirs(os.path.dirname(state_path), exist_ok=True)

    tmp_path = f"{state_path}.tmp-{os.getpid()}-{int(datetime.now().timestamp() * 1000)}"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, state_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def _load_template(name: str) -> str:
    """加载引导模板文件内容。"""
    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    template_path = os.path.join(template_dir, name)
    with open(template_path, encoding="utf-8") as f:
        return f.read()


def _write_file_if_missing(file_path: str, content: str) -> bool:
    """仅在文件不存在时写入，返回 True 表示新创建。"""
    try:
        with open(file_path, "x", encoding="utf-8") as f:
            f.write(content)
        return True
    except FileExistsError:
        return False


def ensure_workspace(dir: str | None = None) -> dict:
    """
    确保工作空间存在并播种引导文件。

    对标 OpenClaw 的 ensureAgentWorkspace():
    - 创建目录
    - 播种 AGENTS.md / SOUL.md / IDENTITY.md 等引导文件
    - 初始化 workspace-state.json

    返回: dict with dir, files created, bootstrap_pending
    """
    workspace_dir = resolve_workspace_dir(dir)
    os.makedirs(workspace_dir, exist_ok=True)

    created_files = []
    for filename in BOOTSTRAP_FILES:
        file_path = os.path.join(workspace_dir, filename)
        template_content = _load_template(filename)
        if _write_file_if_missing(file_path, template_content):
            created_files.append(filename)

    state = read_workspace_state(workspace_dir)

    bootstrap_path = os.path.join(workspace_dir, "BOOTSTRAP.md")
    bootstrap_exists = os.path.exists(bootstrap_path)

    state_changed = False
    now_iso = datetime.now(UTC).isoformat()

    if not state.get("bootstrap_seeded_at") and (
        bootstrap_exists or "BOOTSTRAP.md" in created_files
    ):
        state["bootstrap_seeded_at"] = now_iso
        state_changed = True

    if (
        not state.get("setup_completed_at")
        and state.get("bootstrap_seeded_at")
        and not bootstrap_exists
    ):
        state["setup_completed_at"] = now_iso
        state_changed = True

    if state_changed:
        write_workspace_state(workspace_dir, state)

    return {
        "dir": workspace_dir,
        "created_files": created_files,
        "bootstrap_pending": bootstrap_exists,
        "setup_completed": bool(state.get("setup_completed_at")),
    }


def is_setup_completed(dir: str | None = None) -> bool:
    """检查工作空间初始化是否已完成。"""
    workspace_dir = resolve_workspace_dir(dir)
    state = read_workspace_state(workspace_dir)
    completed_at = state.get("setup_completed_at", "")
    return isinstance(completed_at, str) and bool(completed_at.strip())


def is_bootstrap_pending(dir: str | None = None) -> bool:
    """检查是否需要首次引导 (BOOTSTRAP.md 仍然存在)。"""
    workspace_dir = resolve_workspace_dir(dir)
    bootstrap_path = os.path.join(workspace_dir, "BOOTSTRAP.md")
    return os.path.exists(bootstrap_path)


def load_bootstrap_files(dir: str | None = None) -> list[dict]:
    """
    加载所有引导文件。

    返回列表，每项: {name, path, content, missing}
    """
    workspace_dir = resolve_workspace_dir(dir)
    results = []
    for filename in BOOTSTRAP_FILES:
        file_path = os.path.join(workspace_dir, filename)
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
            results.append(
                {
                    "name": filename,
                    "path": file_path,
                    "content": content,
                    "missing": False,
                }
            )
        except FileNotFoundError:
            results.append(
                {
                    "name": filename,
                    "path": file_path,
                    "content": None,
                    "missing": True,
                }
            )
    return results


def complete_bootstrap(dir: str | None = None) -> dict:
    """
    完成首次引导：删除 BOOTSTRAP.md，标记 setup_completed_at。

    对标 OpenClaw: bootstrap 完成后删除 BOOTSTRAP.md。
    """
    workspace_dir = resolve_workspace_dir(dir)
    bootstrap_path = os.path.join(workspace_dir, "BOOTSTRAP.md")

    removed = False
    if os.path.exists(bootstrap_path):
        os.unlink(bootstrap_path)
        removed = True

    state = read_workspace_state(workspace_dir)
    state["setup_completed_at"] = datetime.now(UTC).isoformat()
    write_workspace_state(workspace_dir, state)

    return {
        "dir": workspace_dir,
        "bootstrap_removed": removed,
        "setup_completed_at": state["setup_completed_at"],
    }
