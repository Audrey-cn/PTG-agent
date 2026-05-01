from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any


REQUIRED_MANIFEST_FIELDS = ["name", "version", "description"]


def validate_skill_manifest(manifest: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(manifest, dict):
        return False, "Manifest must be a dictionary"
    for field in REQUIRED_MANIFEST_FIELDS:
        if field not in manifest:
            return False, f"Missing required field: {field}"
    name = manifest.get("name", "")
    if not isinstance(name, str) or not name:
        return False, "Name must be a non-empty string"
    version = manifest.get("version", "")
    if not isinstance(version, str):
        return False, "Version must be a string"
    return True, "Valid"


def get_skill_dependencies(skill: dict[str, Any]) -> list[str]:
    deps = skill.get("dependencies", [])
    if isinstance(deps, list):
        return [str(d) for d in deps]
    if isinstance(deps, dict):
        return list(deps.keys())
    return []


def check_skill_compatibility(skill: dict[str, Any]) -> bool:
    python_version = skill.get("python_version")
    if python_version:
        current = sys.version_info
        required = tuple(int(x) for x in python_version.split(".")[:2])
        if current[:2] < required:
            return False
    required_packages = get_skill_dependencies(skill)
    for pkg in required_packages:
        pkg_name = pkg.split(">=")[0].split("==")[0].split("<")[0].strip()
        try:
            __import__(pkg_name.replace("-", "_"))
        except ImportError:
            return False
    return True


def install_skill_dependencies(skill: dict[str, Any]) -> bool:
    deps = get_skill_dependencies(skill)
    if not deps:
        return True
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", *deps],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def get_skill_readme(skill_path: str) -> str:
    path = Path(skill_path)
    if path.is_file():
        path = path.parent
    readme_path = path / "README.md"
    if readme_path.exists():
        return readme_path.read_text()
    skill_md = path / "SKILL.md"
    if skill_md.exists():
        return skill_md.read_text()
    return ""
