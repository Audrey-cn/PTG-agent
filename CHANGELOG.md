# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- 92 built-in skills (19 creative, 13 MLOps, 11 software dev, 8 productivity, 6 GitHub, etc.)
- 10 plugins (disk-cleanup, google_meet, spotify, kanban, image_gen, etc.)
- Codex transport layer (codex.py, codex_responses_adapter.py, credential_pool, credential_sources)
- Complete TUI Gateway (entry.py, event_publisher.py, render.py, slash_worker.py, transport.py, ws.py)
- Kanban system (kanban_db.py, kanban.py, kanban_tools.py)
- Tool guardrails system (tool_guardrails.py)
- Browser CDP tool (browser_cdp_tool.py)
- Feishu Drive tool (feishu_drive_tool.py)
- Schema sanitizer (schema_sanitizer.py)
- MCP serve (mcp_serve.py)
- Default SOUL template (default_soul.py)
- Comprehensive test suite (98+ test files)
- GitHub Actions CI/CD configuration
- Import lint configuration (.importlinter)
- Pre-commit hooks configuration
- MyPy type checking configuration
- CHANGELOG.md for version history
- .editorconfig for consistent code style

### Changed
- Unified all import paths to `from prometheus.X` format
- Merged duplicate files (constants.py/constants_core.py → constants_core.py)
- Merged duplicate files (logging_config.py/logging_core.py → logging_core.py)
- Organized tools/ into subdirectories (browser, messaging, cron, file, security, voice, web, devops, platform, environments, browser_providers)
- Moved tests/ out of package (prometheus/tests → tests/)
- Dynamic version management from __init__.py
- Added skills and plugins as optional extras
- Enhanced tools/__init__.py for backward compatibility
- Enhanced prometheus/__init__.py with complete public API exports

### Fixed
- Python 3.9 incompatible type annotations
- Missing `as` keyword in except clauses
- Python 3.10+ match/case syntax (converted to if/elif for 3.9 compatibility)
- Invalid f-string syntax in session_export.py
- String literal newlines in trajectory.py
- All old import paths (prometheus_*, prometheus_cli, from tools., from utils import)
- Dead code removal in 8 files
- Managed mode is_managed() check

## [0.8.0] - 2026-04-30

### Added
- Initial release
- Prometheus TTG seed system core
- Chronicler system (stamp/trace/append)
- Semantic audit engine
- Skin engine
- Display system
- Configuration system
- Memory system (USER/MEMORY/SOUL)
- Interactive REPL
- Tools registry and chronicler tools
- Codec (Layer1 structure compression, Layer2 semantic compression)
- Skills (Chronicler SKILL.md)
- CLI main entry point

[Unreleased]: https://github.com/audrey/prometheus-ptg/compare/v0.8.0...HEAD
[0.8.0]: https://github.com/audrey/prometheus-ptg/releases/tag/v0.8.0
