from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import URLError


def resolve_context_references(text: str, cwd: str | None = None) -> str:
    import re

    working_dir = cwd or os.getcwd()

    def _replace_ref(match):
        full = match.group(0)
        ref_body = match.group(1)

        if ref_body.startswith("file:"):
            path = ref_body[5:].strip()
            return _resolve_file(path, working_dir)

        if ref_body.startswith("folder:"):
            path = ref_body[7:].strip()
            return _resolve_folder(path, working_dir)

        if ref_body == "diff":
            return _resolve_git_diff(working_dir)

        if ref_body == "staged":
            return _resolve_git_staged(working_dir)

        if ref_body.startswith("git:"):
            n = ref_body[4:].strip()
            return _resolve_git_log(n, working_dir)

        if ref_body.startswith("url:"):
            url = ref_body[4:].strip()
            return _resolve_url(url)

        path = ref_body.strip()
        if os.path.isfile(os.path.join(working_dir, path)):
            return _resolve_file(path, working_dir)
        if os.path.isdir(os.path.join(working_dir, path)):
            return _resolve_folder(path, working_dir)

        return full

    pattern = re.compile(r'@([a-zA-Z0-9_./:\-]+)')
    return pattern.sub(_replace_ref, text)


def _resolve_file(path: str, cwd: str) -> str:
    full = os.path.join(cwd, path) if not os.path.isabs(path) else path
    try:
        content = Path(full).read_text(encoding="utf-8", errors="replace")
        lines = content.count("\n") + 1
        header = f"[File: {path} ({lines} lines)]"
        if lines > 500:
            content = content.split("\n")
            head = "\n".join(content[:200])
            tail = "\n".join(content[-100:])
            return f"{header}\n{head}\n... ({lines - 300} lines omitted) ...\n{tail}\n[End of file]"
        return f"{header}\n{content}\n[End of file]"
    except Exception as e:
        return f"[Error reading {path}: {e}]"


def _resolve_folder(path: str, cwd: str) -> str:
    full = os.path.join(cwd, path) if not os.path.isabs(path) else path
    try:
        entries = []
        for root, dirs, files in os.walk(full):
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules", ".venv", "venv")]
            for f in sorted(files):
                if f.endswith((".pyc", ".pyo", ".so", ".dll", ".exe")):
                    continue
                fp = os.path.join(root, f)
                rel = os.path.relpath(fp, full)
                entries.append(rel)
                if len(entries) >= 100:
                    entries.append("... (truncated)")
                    break
            if len(entries) >= 100:
                break
        header = f"[Folder: {path} ({len(entries)} files shown)]"
        return f"{header}\n" + "\n".join(entries) + f"\n[End of folder]"
    except Exception as e:
        return f"[Error reading {path}: {e}]"


def _resolve_git_diff(cwd: str) -> str:
    try:
        result = subprocess.run(
            ["git", "diff", "--stat"],
            capture_output=True, text=True, timeout=10, cwd=cwd,
        )
        stat = result.stdout.strip()
        if not stat:
            return "[Git diff: no changes]"

        result_full = subprocess.run(
            ["git", "diff"],
            capture_output=True, text=True, timeout=15, cwd=cwd,
        )
        diff = result_full.stdout.strip()
        if len(diff) > 8000:
            diff = diff[:8000] + "\n... (truncated)"
        return f"[Git working tree diff]\n{stat}\n\n{diff}\n[End of diff]"
    except Exception as e:
        return f"[Git diff error: {e}]"


def _resolve_git_staged(cwd: str) -> str:
    try:
        result = subprocess.run(
            ["git", "diff", "--cached"],
            capture_output=True, text=True, timeout=15, cwd=cwd,
        )
        diff = result.stdout.strip()
        if not diff:
            return "[Git staged: no staged changes]"
        if len(diff) > 8000:
            diff = diff[:8000] + "\n... (truncated)"
        return f"[Git staged diff]\n{diff}\n[End of staged diff]"
    except Exception as e:
        return f"[Git staged error: {e}]"


def _resolve_git_log(n_str: str, cwd: str) -> str:
    try:
        n = int(n_str) if n_str else 5
        n = max(1, min(n, 20))
        result = subprocess.run(
            ["git", "log", f"-{n}", "--oneline", "--stat"],
            capture_output=True, text=True, timeout=10, cwd=cwd,
        )
        log = result.stdout.strip()
        if not log:
            return "[Git log: no commits]"
        if len(log) > 8000:
            log = log[:8000] + "\n... (truncated)"
        return f"[Git log (last {n} commits)]\n{log}\n[End of git log]"
    except Exception as e:
        return f"[Git log error: {e}]"


def _resolve_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        req = Request(url, headers={"User-Agent": "Prometheus/0.8.0"})
        with urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8", errors="replace")
        content_type = resp.headers.get("Content-Type", "")
        if "html" in content_type:
            content = _strip_html(content)
        if len(content) > 12000:
            content = content[:12000] + "\n... (truncated)"
        return f"[URL: {url}]\n{content}\n[End of URL content]"
    except Exception as e:
        return f"[URL fetch error: {e}]"


def _strip_html(html: str) -> str:
    import re
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<[^>]+>', ' ', html)
    html = re.sub(r'\s+', ' ', html)
    return html.strip()
