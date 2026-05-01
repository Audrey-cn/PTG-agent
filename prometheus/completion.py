from __future__ import annotations

from pathlib import Path

_SUBCOMMANDS = [
    "setup",
    "s",
    "doctor",
    "d",
    "model",
    "m",
    "config",
    "c",
    "status",
    "st",
    "seed",
    "se",
    "gene",
    "g",
    "memory",
    "mem",
    "kb",
    "k",
    "dict",
    "di",
    "skill",
    "sk",
    "update",
    "u",
    "repl",
    "r",
    "chat",
    "gateway",
    "cron",
    "agent",
    "bench",
    "snapshot",
    "sp",
    "list-snapshots",
    "ls",
    "restore",
    "rs",
    "resume",
    "re",
    "oneshot",
    "plugins",
    "debug",
    "logs",
]

_SUBCOMMAND_OPTIONS: dict[str, list[str]] = {
    "doctor": ["--full", "--fix", "--backups", "--restore", "--emergency"],
    "d": ["--full", "--fix", "--backups", "--restore", "--emergency"],
    "model": ["show", "set", "providers"],
    "m": ["show", "set", "providers"],
    "config": ["show", "set", "path"],
    "c": ["show", "set", "path"],
    "seed": ["list", "search", "view", "decode", "health", "vault", "create", "--query", "-q"],
    "se": ["list", "search", "view", "decode", "health", "vault", "create", "--query", "-q"],
    "gene": ["list", "library", "edit", "fusion", "--other", "-o"],
    "g": ["list", "library", "edit", "fusion", "--other", "-o"],
    "memory": ["remember", "recall", "status", "dump", "--query", "-q", "--limit", "-l"],
    "mem": ["remember", "recall", "status", "dump", "--query", "-q", "--limit", "-l"],
    "kb": ["search", "stats", "add", "wiki", "--title", "-t", "--content", "-c"],
    "k": ["search", "stats", "add", "wiki", "--title", "-t", "--content", "-c"],
    "dict": ["scan", "view"],
    "di": ["scan", "view"],
    "skill": ["list", "view", "create", "suggest", "search", "--category", "-c", "--query", "-q"],
    "sk": ["list", "view", "create", "suggest", "search", "--category", "-c", "--query", "-q"],
    "update": ["--check"],
    "u": ["--check"],
    "chat": ["--model", "-m", "--profile", "-p", "--system-prompt", "-s", "--max-iterations", "-i"],
    "gateway": ["start", "stop", "status", "serve", "--platform", "-p"],
    "cron": ["list", "add", "remove", "status", "run", "--name", "-n", "--schedule", "--command"],
    "agent": ["status", "list", "create", "run"],
    "bench": ["run", "list", "info", "--iterations", "-n"],
    "snapshot": ["--message", "-m"],
    "sp": ["--message", "-m"],
    "restore": [],
    "rs": [],
    "oneshot": [
        "--model",
        "-m",
        "--system-prompt",
        "-s",
        "--api-key",
        "--base-url",
        "--max-tokens",
        "--temperature",
    ],
    "plugins": ["list", "install", "uninstall", "enable", "disable", "info"],
    "debug": ["--upload"],
    "logs": ["--level", "--lines", "--clear", "--rotate"],
}

_GLOBAL_OPTIONS = ["--version", "-V", "--verbose", "-v"]


def generate_bash_completion() -> str:
    subcmds = " ".join(_SUBCOMMANDS)
    lines = [
        "#!/bin/bash",
        f"_ptg_subcommands=({subcmds})",
        "",
        "_ptg_completions() {",
        "  local cur prev subcmd",
        "  COMPREPLY=()",
        '  cur="${COMP_WORDS[COMP_CWORD]}"',
        '  prev="${COMP_WORDS[COMP_CWORD-1]}"',
        "",
        "  if [ $COMP_CWORD -eq 1 ]; then",
        '    COMPREPLY=($(compgen -W "${_ptg_subcommands[*]}" -- "$cur"))',
        "    return 0",
        "  fi",
        "",
        '  subcmd="${COMP_WORDS[1]}"',
    ]

    case_body = '  case "$subcmd" in\n'
    for sub, opts in _SUBCOMMAND_OPTIONS.items():
        if not opts:
            continue
        opts_str = " ".join(opts)
        case_body += f"    {sub})\n"
        case_body += f'      COMPREPLY=($(compgen -W "{opts_str}" -- "$cur"))\n'
        case_body += "      return 0\n"
        case_body += "      ;;\n"
    case_body += "  esac\n"

    lines.append(case_body)
    lines += [
        '  COMPREPLY=($(compgen -W "${_ptg_subcommands[*]}" -- "$cur"))',
        "  return 0",
        "}",
        "",
        "complete -F _ptg_completions ptg",
    ]
    return "\n".join(lines) + "\n"


def generate_zsh_completion() -> str:
    lines = [
        "#compdef ptg",
        "",
        "_ptg() {",
        "  local -a commands subcmd_opts",
        "  commands=(",
    ]
    for sc in _SUBCOMMANDS:
        lines.append(f"    '{sc}'")
    lines.append("  )")

    lines += [
        "",
        "  _arguments -C \\",
        "    '--version[Show version]' \\",
        "    '-V[Show version]' \\",
        "    '--verbose[Verbose output]' \\",
        "    '-v[Verbose output]' \\",
        "    '1:command:->command' \\",
        "    '*::arg:->args'",
        "",
        "  case $state in",
        "    command)",
        "      _describe 'command' commands",
        "      ;;",
        "    args)",
        "      case $words[1] in",
    ]

    for sub, opts in _SUBCOMMAND_OPTIONS.items():
        if not opts:
            continue
        lines.append(f"        {sub})")
        subcmd_opts = []
        for opt in opts:
            if opt.startswith("--") or opt.startswith("-"):
                subcmd_opts.append(f"'{opt}'")
            else:
                subcmd_opts.append(f"'{opt}'")
        joined = " ".join(subcmd_opts)
        lines.append(f"          _arguments '*::option:(({joined}))'")
        lines.append("          ;;")

    lines += [
        "      esac",
        "      ;;",
        "  esac",
        "}",
        "",
        '_ptg "$@"',
    ]
    return "\n".join(lines) + "\n"


def generate_fish_completion() -> str:
    lines = [
        "complete -c ptg -n '__fish_use_subcommand' -a 'setup' -d '引导式初始化'",
        "complete -c ptg -n '__fish_use_subcommand' -a 's' -d '引导式初始化'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'doctor' -d '系统健康诊断'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'd' -d '系统健康诊断'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'model' -d '模型配置'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'm' -d '模型配置'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'config' -d '配置管理'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'c' -d '配置管理'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'status' -d '系统状态总览'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'st' -d '系统状态总览'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'seed' -d '种子管理'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'se' -d '种子管理'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'gene' -d '基因编辑'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'g' -d '基因编辑'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'memory' -d '向量记忆'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'mem' -d '向量记忆'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'kb' -d '知识库'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'k' -d '知识库'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'dict' -d '语义字典'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'di' -d '语义字典'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'skill' -d '技能管理'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'sk' -d '技能管理'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'update' -d '自我更新'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'u' -d '自我更新'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'repl' -d '交互式 REPL'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'r' -d '交互式 REPL'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'chat' -d 'AI Agent 对话'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'gateway' -d '网关管理'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'cron' -d '定时任务'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'agent' -d 'Agent 管理'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'bench' -d '性能基准测试'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'snapshot' -d '创建快照'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'sp' -d '创建快照'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'oneshot' -d '单次执行'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'plugins' -d '插件管理'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'debug' -d '调试报告'",
        "complete -c ptg -n '__fish_use_subcommand' -a 'logs' -d '日志管理'",
    ]

    for sub, opts in _SUBCOMMAND_OPTIONS.items():
        if not opts:
            continue
        for opt in opts:
            if opt.startswith("--"):
                lines.append(
                    f"complete -c ptg -n '__fish_seen_subcommand_from {sub}' -l {opt.lstrip('-')}"
                )

    lines.append("complete -c ptg -n '__fish_use_subcommand' -l version -d 'Show version'")
    lines.append("complete -c ptg -n '__fish_use_subcommand' -s V -d 'Show version'")
    lines.append("complete -c ptg -n '__fish_use_subcommand' -l verbose -d 'Verbose output'")
    lines.append("complete -c ptg -n '__fish_use_subcommand' -s v -d 'Verbose output'")
    return "\n".join(lines) + "\n"


def install_completion(shell: str = "bash") -> bool:
    shell = shell.lower()
    if shell == "bash":
        script = generate_bash_completion()
        comp_dir = Path.home() / ".bash_completion.d"
        comp_dir.mkdir(parents=True, exist_ok=True)
        target = comp_dir / "ptg"
        target.write_text(script, encoding="utf-8")
        bashrc = Path.home() / ".bashrc"
        source_line = f'[ -f "{target}" ] && . "{target}"\n'
        if bashrc.exists():
            content = bashrc.read_text(encoding="utf-8")
            if str(target) not in content:
                with open(bashrc, "a", encoding="utf-8") as f:
                    f.write(f"\n{source_line}")
        return True
    elif shell == "zsh":
        script = generate_zsh_completion()
        comp_dir = Path.home() / ".zfunc"
        comp_dir.mkdir(parents=True, exist_ok=True)
        target = comp_dir / "_ptg"
        target.write_text(script, encoding="utf-8")
        return True
    elif shell == "fish":
        script = generate_fish_completion()
        comp_dir = Path.home() / ".config" / "fish" / "completions"
        comp_dir.mkdir(parents=True, exist_ok=True)
        target = comp_dir / "ptg.fish"
        target.write_text(script, encoding="utf-8")
        return True
    else:
        return False
