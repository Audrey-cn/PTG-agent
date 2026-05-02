#!/usr/bin/env python3
"""Replace all remaining Hermes references in test files."""

import os
import re
from pathlib import Path

REPLACEMENTS = [
    # Class names
    (r'\bHermesCLI\b', 'PrometheusCLI'),
    (r'\bhermes_cli\b', 'prometheus_cli'),
    (r'\bHermesConfig\b', 'PrometheusConfig'),
    (r'\bhermes_config\b', 'prometheus_config'),
    (r'\bHermesAgent\b', 'PrometheusAgent'),
    (r'\bhermes_agent\b', 'prometheus_agent'),
    # Function names
    (r'\bensure_hermes_home\b', 'ensure_prometheus_home'),
    (r'\bget_hermes_home\b', 'get_prometheus_home'),
    (r'\bhermes_home\b', 'prometheus_home'),
    # Variable names
    (r'\bhermes_app\b', 'prometheus_app'),
    (r'\bhermes_mode\b', 'prometheus_mode'),
    # String literals
    (r'"hermes"', '"prometheus"'),
    (r"'hermes'", "'prometheus'"),
    (r'"Hermes"', '"Prometheus"'),
    (r"'Hermes'", "'Prometheus'"),
    # Module paths
    (r'\bhermes\.', 'prometheus.'),
    (r'\.hermes\b', '.prometheus'),
]

def process_file(filepath: Path) -> int:
    """Process a single file and return number of replacements."""
    try:
        content = filepath.read_text(encoding='utf-8')
    except Exception:
        return 0
    
    original = content
    count = 0
    
    for pattern, replacement in REPLACEMENTS:
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            count += len(re.findall(pattern, content))
            content = new_content
    
    if content != original:
        filepath.write_text(content, encoding='utf-8')
        print(f"  ✓ {filepath} - {count} replacements")
    
    return count

def main():
    test_dir = Path(__file__).parent.parent / "tests"
    total = 0
    file_count = 0
    
    print("Scanning test files for Hermes references...")
    
    for py_file in sorted(test_dir.rglob("*.py")):
        if "__pycache__" in str(py_file):
            continue
        
        replacements = process_file(py_file)
        if replacements > 0:
            total += replacements
            file_count += 1
    
    print(f"\nDone! Modified {file_count} files, {total} total replacements")

if __name__ == "__main__":
    main()
