#!/usr/bin/env python3
"""Import path checker for Prometheus tools.

Scans all Python files in prometheus/tools/ for invalid import patterns
and reports any paths that don't match the canonical module structure.

Usage:
    python scripts/check_import_paths.py [--fix] [--verbose]
"""

import argparse
import ast
import os
import sys
from pathlib import Path
from typing import NamedTuple


# Canonical module path mapping
# Maps old/invalid paths to their correct canonical paths
CANONICAL_PATHS = {
    "prometheus.tools.fuzzy_match": "prometheus.tools.security.fuzzy_match",
    "prometheus.tools.patch_parser": "prometheus.tools.file.patch_parser",
    "prometheus.tools.tool_output_limits": "prometheus.tools.security.tool_output_limits",
    "prometheus.tools.file_operations": "prometheus.tools.file.file_operations",
    "prometheus.tools.binary_extensions": "prometheus.tools.file.binary_extensions",
    "prometheus.tools.registry": "prometheus.tools.security.registry",
    "prometheus.tools.approval": "prometheus.tools.security.approval",
    "prometheus.tools.path_security": "prometheus.tools.security.path_security",
    "prometheus.tools.url_safety": "prometheus.tools.security.url_safety",
    "prometheus.tools.interrupt": "prometheus.tools.security.interrupt",
    "prometheus.tools.budget_config": "prometheus.tools.security.budget_config",
    "prometheus.tools.process_registry": "prometheus.tools.security.process_registry",
    "prometheus.tools.schema_sanitizer": "prometheus.tools.security.schema_sanitizer",
    "prometheus.tools.tool_result_storage": "prometheus.tools.security.tool_result_storage",
    "prometheus.tools.tool_backend_helpers": "prometheus.tools.security.tool_backend_helpers",
}


class ImportIssue(NamedTuple):
    file: str
    line: int
    old_path: str
    new_path: str
    module_name: str


def scan_file(filepath: str, fix: bool = False) -> list[ImportIssue]:
    """Scan a single Python file for invalid import paths."""
    issues = []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return issues

    try:
        tree = ast.parse(content, filename=filepath)
    except SyntaxError:
        return issues

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                old_path = alias.name
                if old_path in CANONICAL_PATHS:
                    issues.append(ImportIssue(
                        file=filepath,
                        line=node.lineno,
                        old_path=old_path,
                        new_path=CANONICAL_PATHS[old_path],
                        module_name=alias.asname or old_path.split(".")[-1],
                    ))
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module in CANONICAL_PATHS:
                issues.append(ImportIssue(
                    file=filepath,
                    line=node.lineno,
                    old_path=node.module,
                    new_path=CANONICAL_PATHS[node.module],
                    module_name=node.module.split(".")[-1],
                ))

    if fix and issues:
        _fix_file(filepath, issues)

    return issues


def _fix_file(filepath: str, issues: list[ImportIssue]) -> None:
    """Fix invalid import paths in a file."""
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for issue in issues:
        line_idx = issue.line - 1
        if line_idx < len(lines):
            lines[line_idx] = lines[line_idx].replace(issue.old_path, issue.new_path)

    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(lines)


def scan_directory(directory: str, fix: bool = False, verbose: bool = False) -> list[ImportIssue]:
    """Scan all Python files in a directory recursively."""
    all_issues = []
    py_files = list(Path(directory).rglob("*.py"))

    for filepath in py_files:
        issues = scan_file(str(filepath), fix=fix)
        all_issues.extend(issues)
        if verbose and issues:
            for issue in issues:
                action = "FIXED" if fix else "FOUND"
                print(f"  [{action}] {issue.file}:{issue.line}")
                print(f"    {issue.old_path} -> {issue.new_path}")

    return all_issues


def main():
    parser = argparse.ArgumentParser(description="Check and fix invalid import paths")
    parser.add_argument("--fix", action="store_true", help="Automatically fix issues")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    parser.add_argument("--dir", default="prometheus/tools", help="Directory to scan")
    args = parser.parse_args()

    print(f"Scanning {args.dir} for invalid import paths...")
    print(f"Mode: {'FIX' if args.fix else 'CHECK'}")
    print()

    issues = scan_directory(args.dir, fix=args.fix, verbose=args.verbose)

    print()
    if issues:
        print(f"Found {len(issues)} issue(s)")
        if not args.fix:
            print("Run with --fix to automatically resolve")
            sys.exit(1)
        else:
            print(f"Fixed {len(issues)} issue(s)")
    else:
        print("No issues found - all import paths are valid")

    sys.exit(0)


if __name__ == "__main__":
    main()
