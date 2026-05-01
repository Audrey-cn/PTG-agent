#!/usr/bin/env python3
"""╔══════════════════════════════════════════════════════════════╗."""

import os
import sys

# ═══════════════════════════════════════════
#   Profile 覆盖 — 必须在任何 prometheus import 之前
# ═══════════════════════════════════════════


def _apply_profile_override():
    """Set PROMETHEUS_HOME from -p/--profile flag, before any imports.

    Called at the VERY TOP of the CLI entry point, before any prometheus
    module is imported.  Uses only stdlib to avoid circular dependencies.
    """
    profile_name = None
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg in ("-p", "--profile"):
            try:
                profile_name = args[i + 1]
            except IndexError:
                pass
            break
        if arg.startswith("--profile="):
            profile_name = arg.split("=", 1)[1]
            break

    if not profile_name:
        return

    if profile_name == "default":
        return

    import re

    if not re.match(r"^[a-z0-9][a-z0-9_-]{0,63}$", profile_name):
        return

    home = os.environ.get(
        "PROMETHEUS_HOME",
        os.path.join(os.path.expanduser("~"), ".prometheus"),
    )
    profile_dir = os.path.join(home, "profiles", profile_name)
    if os.path.isdir(profile_dir):
        os.environ["PROMETHEUS_HOME"] = profile_dir


_apply_profile_override()


import contextlib
import json
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

__version__ = "0.8.0"
__codename__ = "Prometheus"

# 确保 tools/ 子目录在搜索路径中
_PROMETHEUS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROJECT_ROOT = os.path.dirname(_PROMETHEUS_DIR)
_TOOLS_DIR = os.path.join(_PROMETHEUS_DIR, "tools")
if _PROMETHEUS_DIR not in sys.path:
    sys.path.insert(0, _PROMETHEUS_DIR)
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)


# ═══════════════════════════════════════════
#   Banner
# ═══════════════════════════════════════════

BANNER = f"""
🔥 Prometheus · Teach-To-Grow
   种子基因编辑器 v{__version__}

   「神按自己的样子造人，我按人类的基因造种。」
   创始人: Audrey · 001X
"""


# ═══════════════════════════════════════════
#   Setup 引导
# ═══════════════════════════════════════════


def cmd_setup(args):
    """交互式初始化引导。"""
    try:
        from prometheus.init_wizard import run_setup

        completed = run_setup()
        if completed:
            _offer_launch_chat()
    except ImportError:
        print(BANNER)
        print("📋 Prometheus Setup 引导\n")
        print("⚠️  无法加载 init_wizard 模块，请检查安装。")
        return


def _offer_launch_chat():
    from prometheus.init_wizard import _prompt_yes_no as wizard_yes_no

    print()
    if wizard_yes_no("🚀 是否立即进入 Chat 模式？", True):
        chat_args = type("Args", (), {})()
        chat_args.system_prompt = None
        chat_args.model = None
        chat_args.message = None
        chat_args.stream = True
        chat_args.provider = None
        chat_args.list = False
        chat_args.max_iterations = 50
        cmd_chat(chat_args)
    else:
        print()
        print("  随时运行 'ptg chat' 开始对话。")
        print()


# ═══════════════════════════════════════════
#   Doctor 诊断
# ═══════════════════════════════════════════


def cmd_doctor(args):
    """系统健康诊断与修复。"""
    print(BANNER)

    try:
        from doctor import (
            PrometheusDoctor,
            emergency_repair,
            run_doctor_backups,
            run_doctor_diagnose,
            run_doctor_fix,
            run_doctor_full,
            run_doctor_restore,
        )
    except ImportError:
        from prometheus.doctor import (
            emergency_repair,
            run_doctor_backups,
            run_doctor_diagnose,
            run_doctor_fix,
            run_doctor_full,
            run_doctor_restore,
        )

    if args.emergency:
        emergency_repair()
    elif args.backups:
        run_doctor_backups()
    elif args.restore:
        run_doctor_restore(args.restore)
    elif args.fix:
        run_doctor_fix()
    elif args.full:
        run_doctor_full()
    else:
        run_doctor_diagnose()


def cmd_fallback(args):
    """管理 fallback 提供者链。"""
    try:
        from fallback_cmd import cmd_fallback as fallback_impl
    except ImportError:
        from prometheus.cli.fallback_cmd import cmd_fallback as fallback_impl
    fallback_impl(args)


def cmd_dump(args):
    """导出设置摘要用于支持调试。"""
    try:
        from dump import run_dump
    except ImportError:
        from prometheus.cli.dump import run_dump
    run_dump(args)


# ═══════════════════════════════════════════
#   Model 模型配置
# ═══════════════════════════════════════════


def cmd_model(args):
    """模型/提供者配置。"""
    from config import Config as PrometheusConfig

    cfg = PrometheusConfig()

    if args.action == "show":
        print("\n🤖 模型配置\n")
        model_cfg = cfg.to_dict().get("model", {})
        for k, v in model_cfg.items():
            print(f"  {k}: {v}")
    elif args.action == "set":
        if not args.key or not args.value:
            print("用法: ptg model set <key> <value>")
            print("示例: ptg model set provider openrouter")
            print("      ptg model set name anthropic/claude-sonnet-4")
            return
        cfg.set("model", args.key, args.value)
        print(f"✅ 模型配置已更新: {args.key} = {args.value}")
    elif args.action == "providers":
        print("\n🤖 支持的提供者\n")
        providers = [
            ("openrouter", "OpenRouter (推荐)", "OPENROUTER_API_KEY"),
            ("anthropic", "Anthropic", "ANTHROPIC_API_KEY"),
            ("openai", "OpenAI", "OPENAI_API_KEY"),
            ("deepseek", "DeepSeek", "DEEPSEEK_API_KEY"),
            ("google", "Google Gemini", "GOOGLE_API_KEY"),
            ("local", "本地模型", "model.base_url"),
        ]
        for pid, name, auth in providers:
            print(f"  · {pid:<12} {name:<20} 认证: {auth}")
    else:
        print("\n🤖 模型配置\n")
        model_cfg = cfg.to_dict().get("model", {})
        provider = model_cfg.get("provider", "未配置")
        model = model_cfg.get("name", "未配置")
        print(f"  当前提供者: {provider}")
        print(f"  当前模型: {model}")
        print("\n  用法:")
        print("    ptg model show         查看完整配置")
        print("    ptg model set <k> <v>  修改配置")
        print("    ptg model providers    列出支持的提供者")


# ═══════════════════════════════════════════
#   Config 配置管理
# ═══════════════════════════════════════════


def cmd_config(args):
    """配置管理。"""
    from config import Config as PrometheusConfig

    cfg = PrometheusConfig()

    if args.action == "show" or args.action is None:
        print("\n⚙️ Prometheus 配置\n")
        for section, values in cfg.to_dict().items():
            if isinstance(values, dict):
                print(f"  [{section}]")
                for k, v in values.items():
                    print(f"    {k}: {v}")
            else:
                print(f"  {section}: {values}")
    elif args.action == "set":
        if not args.key or not args.value:
            print("用法: ptg config set <key> <value>")
            print("示例: ptg config set model.provider openrouter")
            return
        if "." in args.key:
            section, k = args.key.rsplit(".", 1)
            cfg.set(section, k, args.value)
        else:
            cfg.set("general", args.key, args.value)
        print(f"✅ 已更新: {args.key} = {args.value}")
    elif args.action == "path":
        print(os.path.join(_PROMETHEUS_DIR, "config.yaml"))


# ═══════════════════════════════════════════
#   Status 系统状态
# ═══════════════════════════════════════════


def cmd_status(args):
    """系统总览状态。"""
    print(f"\n🔥 Prometheus · v{__version__}\n")

    # 种子
    from knowledge import SeedIndex

    si = SeedIndex()
    ss = si.stats()
    print(
        f"  🌱 种子: {ss['total_seeds']} 个 · {ss['total_genes']} 基因 · {ss['total_concepts']} 概念"
    )

    # Wiki
    from knowledge import KnowledgeManager

    km = KnowledgeManager()
    ks = km.stats()
    wiki_icon = "✅" if ks["wiki_connected"] else "❌"
    print(f"  📚 Wiki: {wiki_icon} ({ks['wiki_pages']} 页)")
    print(f"  💾 本地知识: {ks['local_entries']} 条")

    # 记忆
    try:
        from vector_memory import get_memory

        mem = get_memory()
        ms = mem.summary()
        print(f"  🧠 记忆: {ms['total_memories']} 条 · {ms['total_tokens']} tok")
        print(f"     维度: {ms['vector_dim']} · DB: {ms['db_size_kb']} KB")
    except Exception:
        print("  🧠 记忆: 未初始化")

    # 配置
    from config import Config as PrometheusConfig

    cfg = PrometheusConfig()
    model_cfg = cfg.to_dict().get("model", {})
    provider = model_cfg.get("provider", "?")
    model = model_cfg.get("name", "?")
    print(f"  🤖 模型: {provider}/{model}")

    print()


# ═══════════════════════════════════════════
#   Seed 种子管理
# ═══════════════════════════════════════════


def cmd_seed(args):
    """种子管理。"""
    if args.action == "list":
        from knowledge import SeedIndex

        si = SeedIndex()
        seeds = si.list_seeds()
        if not seeds:
            print("未发现种子")
            return
        print(f"\n🌱 种子列表 ({len(seeds)} 个)\n")
        for s in seeds:
            print(
                f"  · {s['name']} (v{s['version']}) — {s['gene_count']} 基因 · {s['concept_count']} 概念"
            )
            print(f"    {s['path']}")

    elif args.action == "search":
        query = args.query or args.seed_path
        if not query:
            query = " ".join(args.query) if isinstance(args.query, list) else args.query
        if not query:
            print("用法: ptg seed search <查询>")
            return
        from knowledge import SeedIndex

        si = SeedIndex()
        results = si.search(query)
        if not results:
            print(f"未找到匹配: {query}")
        else:
            print(f'\n🔍 种子搜索: "{query}" · {len(results)} 条\n')
            for r in results:
                print(f"  · {r['name']} — {r['description'][:60]}")

    elif args.action == "view" and args.seed_path:
        sys.path.insert(0, _PROMETHEUS_DIR)
        from prometheus import cmd_view

        cmd_view(args.seed_path)

    elif args.action == "decode" and args.seed_path:
        sys.path.insert(0, _PROMETHEUS_DIR)
        from prometheus import cmd_decode

        cmd_decode(args.seed_path)

    elif args.action == "health" and args.seed_path:
        sys.path.insert(0, _PROMETHEUS_DIR)
        from genes.analyzer import GeneHealthAuditor, print_gene_health_report

        from prometheus import load_seed

        data = load_seed(args.seed_path)
        if data:
            auditor = GeneHealthAuditor()
            result = auditor.audit_seed(data)
            print_gene_health_report(result)

    elif args.action == "vault":
        sys.path.insert(0, _PROMETHEUS_DIR)
        from prometheus import cmd_vault

        cmd_vault()

    elif args.action == "create" and args.seed_path:
        sys.path.insert(0, _PROMETHEUS_DIR)
        from prometheus import cmd_create

        cmd_create(args.seed_path)

    else:
        print("\n🌱 种子管理\n")
        print("  用法:")
        print("    ptg seed list              列出所有种子")
        print("    ptg seed search <查询>     搜索种子")
        print("    ptg seed view <路径>       查看种子 DNA")
        print("    ptg seed decode <路径>     解码为史诗叙事")
        print("    ptg seed health <路径>     基因健康审计")
        print("    ptg seed vault             种子仓库")
        print("    ptg seed create <名称>     创建新种子")


# ═══════════════════════════════════════════
#   Gene 基因编辑
# ═══════════════════════════════════════════


def cmd_gene(args):
    """基因编辑。"""
    if args.action == "list" and args.seed_path:
        sys.path.insert(0, _PROMETHEUS_DIR)
        from prometheus import cmd_genes

        cmd_genes(args.seed_path)

    elif args.action == "library":
        sys.path.insert(0, _PROMETHEUS_DIR)
        from genes.analyzer import GeneLibrary

        lib = GeneLibrary()
        print("\n🧬 标准基因库:")
        for g in lib.list_standard():
            gid = g.get("locus", g.get("gene_id", "?"))
            carbon = " ◆碳基" if g.get("carbon_bonded") else ""
            print(f"  {gid} · {g.get('name', '?')}{carbon}")
            print(f"    {g.get('description', '')[:60]}")

    elif args.action == "edit" and args.seed_path:
        sys.path.insert(0, _PROMETHEUS_DIR)
        from prometheus import cmd_edit

        cmd_edit(args.seed_path)

    elif args.action == "fusion" and args.seed_path:
        if not args.other:
            print("用法: ptg gene fusion <种子A> <种子B>")
            return
        sys.path.insert(0, _PROMETHEUS_DIR)
        from genes.analyzer import GeneFusionAnalyzer, print_fusion_report

        from prometheus import load_seed

        data_a = load_seed(args.seed_path)
        data_b = load_seed(args.other)
        if data_a and data_b:
            genes_a = (
                data_a.get("dna_encoding", {}).get("gene_loci", [])
                if isinstance(data_a.get("dna_encoding"), dict)
                else []
            )
            genes_b = (
                data_b.get("dna_encoding", {}).get("gene_loci", [])
                if isinstance(data_b.get("dna_encoding"), dict)
                else []
            )
            analyzer = GeneFusionAnalyzer()
            result = analyzer.analyze_fusion(
                genes_a, genes_b, os.path.basename(args.seed_path), os.path.basename(args.other)
            )
            print_fusion_report(result)

    else:
        print("\n🧬 基因编辑\n")
        print("  用法:")
        print("    ptg gene list <种子路径>    列出基因位点")
        print("    ptg gene library           查看基因库")
        print("    ptg gene edit <种子路径>   交互式编辑")
        print("    ptg gene fusion <A> <B>    基因融合分析")


# ═══════════════════════════════════════════
#   Memory 向量记忆
# ═══════════════════════════════════════════


def cmd_memory(args):
    """向量记忆系统。"""
    from vector_memory import get_memory

    mem = get_memory()

    if args.action == "remember" and args.text:
        result = mem.remember(args.text, layer="working", source="cli")
        print(f"🧠 已记住 · id={result['id']} · ~{result['token_estimate']}tok")

    elif args.action == "recall":
        query = args.query
        if not query and args.text:
            query = " ".join(args.text)
        if not query:
            print("用法: ptg memory recall <查询>")
            return
        results = mem.recall(query, limit=5)
        if not results:
            print("未找到相关记忆")
        else:
            print(f'\n🔍 语义检索: "{query}" · {len(results)} 条\n')
            for i, r in enumerate(results, 1):
                print(f"  {i}. [{r['layer']}] {r['content'][:80]}")
                print(f"     相似度: {r['similarity']:.4f}")

    elif args.action == "status":
        s = mem.summary()
        print("\n🧠 向量记忆系统")
        print(f"  总记忆: {s['total_memories']} 条 · {s['total_tokens']} tok")
        print(
            f"  工作层: {s['by_layer']['working']} · 情景层: {s['by_layer']['episodic']} · 长期层: {s['by_layer']['longterm']}"
        )
        print(f"  向量维度: {s['vector_dim']} · DB: {s['db_size_kb']} KB")

    elif args.action == "dump":
        dump = mem.memory_dump(limit=args.limit or 10)
        if not dump:
            print("记忆为空")
        else:
            print(f"\n🧠 记忆导出 ({len(dump)} 条)\n")
            for d in dump:
                print(f"  [{d['layer']}] {d['content']}")
                print(f"    id={d['id']} · 来源:{d['source']} · 重要性:{d['importance']}")

    else:
        print("\n🧠 向量记忆\n")
        print("  用法:")
        print("    ptg memory remember <文本>  记住文本")
        print("    ptg memory recall <查询>    语义检索")
        print("    ptg memory status           系统状态")
        print("    ptg memory dump             导出记忆")


# ═══════════════════════════════════════════
#   KB 知识库
# ═══════════════════════════════════════════


def cmd_kb(args):
    """知识库管理。"""
    from knowledge import KnowledgeManager

    km = KnowledgeManager()

    if args.action == "search":
        query = args.query
        if isinstance(query, list):
            query = " ".join(query) if query else None
        if not query:
            print("用法: ptg kb search <查询>")
            return
        results = km.search(query, limit=5)
        print(f'\n📚 知识检索: "{query}" · {results["total"]} 条\n')
        if results["seeds"]:
            print("  🌱 种子:")
            for r in results["seeds"][:3]:
                print(f"    · {r['name']} ({r['gene_count']}基因)")
        if results["wiki"]:
            print("  📖 Wiki:")
            for r in results["wiki"][:3]:
                print(f"    · [{r['maturity']}] {r['title']}")
        if results["local"]:
            print("  💾 本地:")
            for r in results["local"][:3]:
                print(f"    · {r['title']}")

    elif args.action == "stats":
        print(km.summary())

    elif args.action == "add" and args.title:
        content = args.content or ""
        entry_id = km.add_knowledge(args.title, content)
        print(f"✅ 已添加: {args.title} (id={entry_id})")

    elif args.action == "wiki":
        pages = km.list_wiki_pages()
        print(f"\n📖 Wiki 页面 ({len(pages)} 个)\n")
        for p in pages[:20]:
            print(f"  · [{p['type']}] {p['title']} ({p['maturity']})")
        if len(pages) > 20:
            print(f"  ... 还有 {len(pages) - 20} 个")

    else:
        print("\n📚 知识库\n")
        print("  用法:")
        print("    ptg kb search <查询>       统一知识检索")
        print("    ptg kb stats               知识库统计")
        print("    ptg kb add <标题> <内容>   添加本地知识")
        print("    ptg kb wiki                列出 Wiki 页面")


# ═══════════════════════════════════════════
#   Dict 语义字典
# ═══════════════════════════════════════════


def cmd_dict(args):
    """语义字典管理。"""
    if args.action == "scan" and args.filepath:
        filepath = os.path.expanduser(args.filepath)
        if not os.path.exists(filepath):
            print(f"❌ 文件不存在: {filepath}")
            return
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            text = f.read()
        from dict_extension import DictExtender

        ext = DictExtender()
        candidates = ext.scan_text(text)
        filtered = ext.filter_candidates(candidates)
        print(f"\n📖 字典扫描: {os.path.basename(filepath)}")
        print(f"  候选: {len(candidates)} · 通过: {len(filtered)}")
        for c in filtered[:10]:
            print(f"    · {c['term']} (频率:{c['frequency']} 分数:{c['score']:.2f})")

    elif args.action == "view" and args.seed_path:
        from semantic_dict import SemanticDictionary

        sd = SemanticDictionary(args.seed_path)
        entries = sd.list_entries()
        print(f"\n📖 语义字典 ({len(entries)} 条)\n")
        for e in entries[:30]:
            print(f"  {e['term']} → {e['definition'][:50]}")
        if len(entries) > 30:
            print(f"  ... 还有 {len(entries) - 30} 条")

    else:
        print("\n📖 语义字典\n")
        print("  用法:")
        print("    ptg dict scan <文件>       扫描文本提取概念")
        print("    ptg dict view <种子路径>   查看种子字典")


# ═══════════════════════════════════════════
#   Update 自我更新
# ═══════════════════════════════════════════


def _stash_local_changes_if_needed(git_cmd, cwd):
    result = subprocess.run(
        git_cmd + ["status", "--porcelain"], cwd=cwd, capture_output=True, text=True
    )
    if not result.stdout.strip():
        return None

    unmerged = subprocess.run(
        git_cmd + ["ls-files", "--unmerged"], cwd=cwd, capture_output=True, text=True
    )
    if unmerged.stdout.strip():
        print("→ 清除上次冲突遗留的未合并索引条目...")
        subprocess.run(git_cmd + ["reset"], cwd=cwd, capture_output=True)

    stash_name = datetime.now(UTC).strftime("ptg-update-autostash-%Y%m%d-%H%M%S")
    print("→ 检测到本地改动 — 更新前自动 stash...")
    subprocess.run(
        git_cmd + ["stash", "push", "--include-untracked", "-m", stash_name], cwd=cwd, check=True
    )
    stash_ref = subprocess.run(
        git_cmd + ["rev-parse", "--verify", "refs/stash"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return stash_ref


def _resolve_stash_selector(git_cmd, cwd, stash_ref):
    stash_list = subprocess.run(
        git_cmd + ["stash", "list", "--format=%gd %H"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    for line in stash_list.stdout.splitlines():
        selector, _, commit = line.partition(" ")
        if commit.strip() == stash_ref:
            return selector.strip()
    return None


def _print_stash_cleanup_guidance(stash_ref, stash_selector=None):
    print("  请先检查 `git status`，避免意外重复应用。")
    print("  查看 stash 列表: git stash list --format='%gd %H %s'")
    if stash_selector:
        print(f"  删除: git stash drop {stash_selector}")
    else:
        print(f"  找到 commit {stash_ref} 对应的 selector，然后: git stash drop stash@{{N}}")


def _restore_stashed_changes(git_cmd, cwd, stash_ref):
    print()
    print("⚠ 检测到更新前自动 stash 了本地改动。")
    print("  恢复它们会将你的本地自定义叠加到更新后的代码上。")
    try:
        response = input("是否恢复本地改动？[Y/n] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        response = ""
    if response not in ("", "y", "yes"):
        print("跳过恢复本地改动。")
        print(f"你的改动已保存在 git stash 中，可用 `git stash apply {stash_ref}` 手动恢复。")
        return False

    print("→ 恢复本地改动...")
    restore = subprocess.run(
        git_cmd + ["stash", "apply", stash_ref], cwd=cwd, capture_output=True, text=True
    )

    unmerged = subprocess.run(
        git_cmd + ["diff", "--name-only", "--diff-filter=U"],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    has_conflicts = bool(unmerged.stdout.strip())

    if restore.returncode != 0 or has_conflicts:
        print("✗ 恢复本地改动时产生冲突。")
        if restore.stdout.strip():
            print(restore.stdout.strip())
        if restore.stderr.strip():
            print(restore.stderr.strip())
        conflicted_files = unmerged.stdout.strip()
        if conflicted_files:
            print("\n冲突文件:")
            for f in conflicted_files.splitlines():
                print(f"  • {f}")
        print("\n你的 stash 条目已保留，数据未丢失。")
        print(f"  Stash ref: {stash_ref}")
        subprocess.run(git_cmd + ["reset", "--hard", "HEAD"], cwd=cwd, capture_output=True)
        print("工作区已重置为干净状态。")
        print(f"稍后手动恢复: git stash apply {stash_ref}")
        return False

    stash_selector = _resolve_stash_selector(git_cmd, cwd, stash_ref)
    if stash_selector is None:
        print("⚠ 已恢复本地改动，但找不到对应的 stash 条目。")
        _print_stash_cleanup_guidance(stash_ref)
    else:
        drop = subprocess.run(
            git_cmd + ["stash", "drop", stash_selector], cwd=cwd, capture_output=True, text=True
        )
        if drop.returncode != 0:
            print("⚠ 已恢复本地改动，但无法删除 stash 条目。")
            _print_stash_cleanup_guidance(stash_ref, stash_selector)

    print("✓ 本地改动已恢复到更新后的代码上。")
    return True


def _clear_bytecode_cache(root):
    removed = 0
    for dirpath, dirnames, _ in os.walk(root):
        dirnames[:] = [
            d for d in dirnames if d not in ("venv", ".venv", "node_modules", ".git", ".worktrees")
        ]
        if os.path.basename(dirpath) == "__pycache__":
            try:
                shutil.rmtree(dirpath)
                removed += 1
            except OSError:
                pass
            dirnames.clear()
    return removed


def _cmd_update_check():
    git_dir = os.path.join(_PROJECT_ROOT, ".git")
    if not os.path.isdir(git_dir):
        print("✗ 非 git 仓库，无法检查更新。")
        sys.exit(1)

    git_cmd = ["git"]
    if sys.platform == "win32":
        git_cmd = ["git", "-c", "windows.appendAtomically=false"]

    print("→ 从 origin 拉取更新信息...")
    fetch = subprocess.run(
        git_cmd + ["fetch", "origin"], cwd=_PROJECT_ROOT, capture_output=True, text=True
    )
    if fetch.returncode != 0:
        stderr = fetch.stderr.strip()
        if "Could not resolve host" in stderr or "unable to access" in stderr:
            print("✗ 网络错误 — 无法连接远程仓库。")
        else:
            print("✗ 拉取远程信息失败。")
        if stderr:
            print(f"  {stderr.splitlines()[0]}")
        sys.exit(1)

    result = subprocess.run(
        git_cmd + ["rev-list", "HEAD..origin/main", "--count"],
        cwd=_PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    commit_count = int(result.stdout.strip())

    if commit_count == 0:
        print("✓ 已是最新版本！")
    else:
        print(f"✓ 发现 {commit_count} 个新提交，可运行 'ptg update' 安装更新。")
    print()


def _cmd_update_impl(args):
    git_dir = os.path.join(_PROJECT_ROOT, ".git")
    if not os.path.isdir(git_dir):
        print("✗ 非 git 安装。请重新安装：")
        print("  pip install -e .")
        sys.exit(1)

    git_cmd = ["git"]
    if sys.platform == "win32":
        git_cmd = ["git", "-c", "windows.appendAtomically=false"]
        subprocess.run(
            git_cmd + ["config", "windows.appendAtomically", "false"],
            cwd=_PROJECT_ROOT,
            check=False,
            capture_output=True,
        )

    print("🔥 Prometheus 自我更新\n")
    print("→ 拉取远程更新...")
    fetch = subprocess.run(
        git_cmd + ["fetch", "origin"], cwd=_PROJECT_ROOT, capture_output=True, text=True
    )
    if fetch.returncode != 0:
        stderr = fetch.stderr.strip()
        if "Could not resolve host" in stderr or "unable to access" in stderr:
            print("✗ 网络错误 — 无法连接远程仓库。")
        elif "Authentication failed" in stderr:
            print("✗ 认证失败 — 请检查 git credentials 或 SSH key。")
        else:
            print("✗ 拉取远程更新失败。")
        if stderr:
            print(f"  {stderr.splitlines()[0]}")
        sys.exit(1)

    result = subprocess.run(
        git_cmd + ["rev-parse", "--abbrev-ref", "HEAD"],
        cwd=_PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    current_branch = result.stdout.strip()
    branch = "main"

    if current_branch != "main":
        label = "detached HEAD" if current_branch == "HEAD" else f"分支 '{current_branch}'"
        print(f"  ⚠ 当前位于 {label} — 切换到 main 进行更新...")
        auto_stash_ref = _stash_local_changes_if_needed(git_cmd, _PROJECT_ROOT)
        subprocess.run(
            git_cmd + ["checkout", "main"],
            cwd=_PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    else:
        auto_stash_ref = _stash_local_changes_if_needed(git_cmd, _PROJECT_ROOT)

    result = subprocess.run(
        git_cmd + ["rev-list", f"HEAD..origin/{branch}", "--count"],
        cwd=_PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    commit_count = int(result.stdout.strip())

    if commit_count == 0:
        if auto_stash_ref is not None:
            _restore_stashed_changes(git_cmd, _PROJECT_ROOT, auto_stash_ref)
        if current_branch not in ("main", "HEAD"):
            subprocess.run(
                git_cmd + ["checkout", current_branch],
                cwd=_PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
        print("✓ 已是最新版本！")
        return

    print(f"→ 发现 {commit_count} 个新提交")

    print("→ 拉取更新...")
    update_succeeded = False
    try:
        pull = subprocess.run(
            git_cmd + ["pull", "--ff-only", "origin", branch],
            cwd=_PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        if pull.returncode != 0:
            print("  ⚠ 无法快进合并（历史分叉），重置以匹配远程...")
            reset = subprocess.run(
                git_cmd + ["reset", "--hard", f"origin/{branch}"],
                cwd=_PROJECT_ROOT,
                capture_output=True,
                text=True,
            )
            if reset.returncode != 0:
                print("✗ 重置失败。")
                if reset.stderr.strip():
                    print(f"  {reset.stderr.strip()}")
                sys.exit(1)
        update_succeeded = True
    finally:
        if auto_stash_ref is not None:
            if not update_succeeded:
                print(f"  ℹ️ 本地改动已保存在 stash (ref: {auto_stash_ref})")
                print("  手动恢复: git stash apply")
            else:
                _restore_stashed_changes(git_cmd, _PROJECT_ROOT, auto_stash_ref)

    removed = _clear_bytecode_cache(_PROJECT_ROOT)
    if removed:
        print(f"  ✓ 已清除 {removed} 个过期的 __pycache__ 目录")

    print("→ 更新 Python 依赖...")
    pip_cmd = [sys.executable, "-m", "pip"]
    try:
        subprocess.run(pip_cmd + ["install", "-e", ".", "--quiet"], cwd=_PROJECT_ROOT, check=True)
    except subprocess.CalledProcessError:
        print("  ⚠ 依赖安装失败 — 请手动运行: pip install -e .")

    print()
    print("✓ 更新完成！")

    if current_branch not in ("main", "HEAD"):
        subprocess.run(
            git_cmd + ["checkout", current_branch],
            cwd=_PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )


def cmd_update(args):
    """自我更新 — 从远程仓库拉取最新代码并重装依赖。"""
    if getattr(args, "check", False):
        _cmd_update_check()
        return

    _cmd_update_impl(args)


# ═══════════════════════════════════════════
#   主入口 (argparse)
# ═══════════════════════════════════════════


def build_parser():
    """构建 argparse 解析器。"""
    import argparse

    parser = argparse.ArgumentParser(
        prog="ptg",
        description="🔥 Prometheus · Teach-To-Grow 种子基因编辑器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例 (推荐使用简短形式):
  ptg setup      (s)  引导式初始化
  ptg doctor     (d)  系统健康诊断
  ptg status     (st) 系统状态总览
  ptg seed list  (se) 列出所有种子
  ptg skill      (sk) 技能管理
  ptg repl       (r)  交互式模式

创始人: Audrey · 001X
""",
    )
    parser.add_argument("--version", "-V", action="version", version=f"ptg {__version__}")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    parser.add_argument("--tui", action="store_true", help="启用 Rich TUI 聊天模式")
    parser.add_argument("--profile", "-p", metavar="NAME", help="使用指定 Profile 实例")

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # setup (s)
    subparsers.add_parser("setup", help="引导式初始化")
    subparsers.add_parser("s", help="(别名) setup - 引导式初始化")

    # doctor (d)
    doctor_p = subparsers.add_parser("doctor", help="系统健康诊断与修复（守门员模式）")
    doctor_p.add_argument("--full", action="store_true", help="深度诊断（全部 8 项检查）")
    doctor_p.add_argument("--fix", action="store_true", help="自动修复网关问题")
    doctor_p.add_argument("--backups", action="store_true", help="列出配置备份")
    doctor_p.add_argument("--restore", help="从指定备份恢复")
    doctor_p.add_argument("--emergency", action="store_true", help="紧急修复模式")

    doctor_p_alias = subparsers.add_parser("d", help="(别名) doctor - 系统健康诊断")
    doctor_p_alias.add_argument("--full", action="store_true")
    doctor_p_alias.add_argument("--fix", action="store_true")
    doctor_p_alias.add_argument("--backups", action="store_true")
    doctor_p_alias.add_argument("--restore")
    doctor_p_alias.add_argument("--emergency", action="store_true")

    # model (m)
    model_p = subparsers.add_parser("model", help="模型配置")
    model_p.add_argument("action", nargs="?", default="show", choices=["show", "set", "providers"])
    model_p.add_argument("key", nargs="?")
    model_p.add_argument("value", nargs="?")

    model_p_alias = subparsers.add_parser("m", help="(别名) model - 模型配置")
    model_p_alias.add_argument(
        "action", nargs="?", default="show", choices=["show", "set", "providers"]
    )
    model_p_alias.add_argument("key", nargs="?")
    model_p_alias.add_argument("value", nargs="?")

    # config (c)
    config_p = subparsers.add_parser("config", help="配置管理")
    config_p.add_argument("action", nargs="?", default="show", choices=["show", "set", "path"])
    config_p.add_argument("key", nargs="?")
    config_p.add_argument("value", nargs="?")

    config_p_alias = subparsers.add_parser("c", help="(别名) config - 配置管理")
    config_p_alias.add_argument(
        "action", nargs="?", default="show", choices=["show", "set", "path"]
    )
    config_p_alias.add_argument("key", nargs="?")
    config_p_alias.add_argument("value", nargs="?")

    # status (st)
    subparsers.add_parser("status", help="系统状态总览")
    subparsers.add_parser("st", help="(别名) status - 系统状态总览")

    # seed (se)
    seed_p = subparsers.add_parser("seed", help="种子管理")
    seed_p.add_argument(
        "action", choices=["list", "search", "view", "decode", "health", "vault", "create"]
    )
    seed_p.add_argument("seed_path", nargs="?")
    seed_p.add_argument("--query", "-q")

    seed_p_alias = subparsers.add_parser("se", help="(别名) seed - 种子管理")
    seed_p_alias.add_argument(
        "action", choices=["list", "search", "view", "decode", "health", "vault", "create"]
    )
    seed_p_alias.add_argument("seed_path", nargs="?")
    seed_p_alias.add_argument("--query", "-q")

    # gene (g)
    gene_p = subparsers.add_parser("gene", help="基因编辑")
    gene_p.add_argument("action", choices=["list", "library", "edit", "fusion"])
    gene_p.add_argument("seed_path", nargs="?")
    gene_p.add_argument("--other", "-o")

    gene_p_alias = subparsers.add_parser("g", help="(别名) gene - 基因编辑")
    gene_p_alias.add_argument("action", choices=["list", "library", "edit", "fusion"])
    gene_p_alias.add_argument("seed_path", nargs="?")
    gene_p_alias.add_argument("--other", "-o")

    # memory (mem)
    mem_p = subparsers.add_parser("memory", help="向量记忆")
    mem_p.add_argument("action", choices=["remember", "recall", "status", "dump"])
    mem_p.add_argument("text", nargs="*")
    mem_p.add_argument("--query", "-q")
    mem_p.add_argument("--limit", "-l", type=int, default=10)

    mem_p_alias = subparsers.add_parser("mem", help="(别名) memory - 向量记忆")
    mem_p_alias.add_argument("action", choices=["remember", "recall", "status", "dump"])
    mem_p_alias.add_argument("text", nargs="*")
    mem_p_alias.add_argument("--query", "-q")
    mem_p_alias.add_argument("--limit", "-l", type=int, default=10)

    # kb (k)
    kb_p = subparsers.add_parser("kb", help="知识库")
    kb_p.add_argument("action", choices=["search", "stats", "add", "wiki"])
    kb_p.add_argument("query", nargs="*")
    kb_p.add_argument("--title", "-t")
    kb_p.add_argument("--content", "-c")

    kb_p_alias = subparsers.add_parser("k", help="(别名) kb - 知识库")
    kb_p_alias.add_argument("action", choices=["search", "stats", "add", "wiki"])
    kb_p_alias.add_argument("query", nargs="*")
    kb_p_alias.add_argument("--title", "-t")
    kb_p_alias.add_argument("--content", "-c")

    # dict (di)
    dict_p = subparsers.add_parser("dict", help="语义字典")
    dict_p.add_argument("action", choices=["scan", "view"])
    dict_p.add_argument("filepath", nargs="?")
    dict_p.add_argument("seed_path", nargs="?")

    dict_p_alias = subparsers.add_parser("di", help="(别名) dict - 语义字典")
    dict_p_alias.add_argument("action", choices=["scan", "view"])
    dict_p_alias.add_argument("filepath", nargs="?")
    dict_p_alias.add_argument("seed_path", nargs="?")

    # update (u)
    update_parser = subparsers.add_parser("update", help="自我更新 — 拉取最新代码并重装依赖")
    update_parser.add_argument("--check", action="store_true", help="仅检查是否有新版本")
    u_parser = subparsers.add_parser("u", help="(别名) update - 自我更新")
    u_parser.add_argument("--check", action="store_true", help="仅检查是否有新版本")

    # skill (sk) - 技能管理
    skill_p = subparsers.add_parser("skill", help="技能管理")
    skill_p.add_argument(
        "action", nargs="?", default="list", choices=["list", "view", "create", "suggest", "search"]
    )
    skill_p.add_argument("name", nargs="?", help="技能名称")
    skill_p.add_argument("--category", "-c", help="技能分类")
    skill_p.add_argument("--query", "-q", help="搜索查询")

    skill_p_alias = subparsers.add_parser("sk", help="(别名) skill - 技能管理")
    skill_p_alias.add_argument(
        "action", nargs="?", default="list", choices=["list", "view", "create", "suggest", "search"]
    )
    skill_p_alias.add_argument("name", nargs="?")
    skill_p_alias.add_argument("--category", "-c")
    skill_p_alias.add_argument("--query", "-q")

    # skills (保留向后兼容)
    subparsers.add_parser("skills", help="列出 Skill 工作流")

    # snapshot (sp) - 快照管理
    snapshot_p = subparsers.add_parser("snapshot", help="创建快照")
    snapshot_p.add_argument("name", nargs="?", help="快照名称（可选）")
    snapshot_p.add_argument("--message", "-m", help="快照说明")

    snapshot_p_alias = subparsers.add_parser("sp", help="(别名) snapshot - 创建快照")
    snapshot_p_alias.add_argument("name", nargs="?")
    snapshot_p_alias.add_argument("--message", "-m")

    # list-snapshots (ls) - 列出快照
    subparsers.add_parser("list-snapshots", help="列出所有快照")
    subparsers.add_parser("ls", help="(别名) list-snapshots - 列出快照")

    # restore (rs) - 恢复快照
    restore_p = subparsers.add_parser("restore", help="恢复快照")
    restore_p.add_argument("name", nargs="?", default="latest", help="快照名称（默认 latest）")

    restore_p_alias = subparsers.add_parser("rs", help="(别名) restore - 恢复快照")
    restore_p_alias.add_argument("name", nargs="?", default="latest")

    # resume (r) - 恢复上次状态
    subparsers.add_parser("resume", help="恢复上次状态")
    subparsers.add_parser("re", help="(别名) resume - 恢复上次状态")

    # repl (r)
    subparsers.add_parser("repl", help="交互式 REPL 模式")

    # chat — Agent 对话模式
    chat_p = subparsers.add_parser("chat", help="启动 AI Agent 对话")
    chat_p.add_argument("message", nargs="*", help="初始消息（可选）")
    chat_p.add_argument("--model", "-m", help="模型覆盖")
    chat_p.add_argument("--profile", "-p", help="配置 profile")
    chat_p.add_argument("--system-prompt", "-s", help="系统提示词")
    chat_p.add_argument("--max-iterations", "-i", type=int, default=50, help="最大迭代次数")

    # gateway — 网关管理
    gw_p = subparsers.add_parser("gateway", help="网关管理")
    gw_p.add_argument("action", choices=["start", "stop", "status", "serve"])
    gw_p.add_argument("--platform", "-p", default="cli", help="平台类型")

    # cron — 定时任务管理
    cron_p = subparsers.add_parser("cron", help="定时任务管理")
    cron_p.add_argument("action", choices=["list", "add", "remove", "status", "run"])
    cron_p.add_argument("--name", "-n", help="任务名称")
    cron_p.add_argument("--schedule", help='cron 表达式 (如 "0 8 * * *")')
    cron_p.add_argument("--command", help="任务命令")

    # dashboard — Web UI 服务器
    dashboard_p = subparsers.add_parser("dashboard", help="启动 Web UI 仪表板")
    dashboard_p.add_argument("--port", type=int, default=9119, help="端口 (默认 9119)")
    dashboard_p.add_argument("--host", default="127.0.0.1", help="主机 (默认 127.0.0.1)")
    dashboard_p.add_argument("--no-open", action="store_true", help="不自动打开浏览器")
    dashboard_p.add_argument("--insecure", action="store_true", help="允许公网访问")
    dashboard_p.add_argument("--tui", action="store_true", help="启用嵌入式TUI聊天")

    # acp — ACP 服务器
    acp_p = subparsers.add_parser("acp", help="启动 ACP 服务器")
    acp_p.add_argument("--host", default="0.0.0.0", help="主机 (默认 0.0.0.0)")
    acp_p.add_argument("--port", type=int, default=8080, help="端口 (默认 8080)")

    # version — 版本信息
    subparsers.add_parser("version", help="显示版本信息")

    # completion — Shell 补全
    completion_p = subparsers.add_parser("completion", help="生成 Shell 补全脚本")
    completion_p.add_argument(
        "shell",
        nargs="?",
        default="bash",
        choices=["bash", "zsh", "fish"],
        help="Shell 类型 (默认 bash)",
    )

    # insights — 行为分析
    insights_p = subparsers.add_parser("insights", help="用户行为分析")
    insights_p.add_argument("--days", type=int, default=7, help="分析天数 (默认 7)")
    insights_p.add_argument("--source", help="按来源过滤")

    # fallback — 管理 fallback 提供者
    fallback_parser = subparsers.add_parser(
        "fallback",
        help="管理 fallback 提供者（主模型失败时尝试）",
        description="管理 fallback 提供者链，在主模型失败时依次尝试",
    )
    fallback_subparsers = fallback_parser.add_subparsers(dest="fallback_command")
    fallback_subparsers.add_parser(
        "list", aliases=["ls"], help="显示当前 fallback 链（无子命令时默认）"
    )
    fallback_subparsers.add_parser(
        "add", help="选择提供者 + 模型（同 prometheus model）并添加到链中"
    )
    fallback_subparsers.add_parser("remove", aliases=["rm"], help="选择并删除链中的条目")
    fallback_subparsers.add_parser("clear", help="删除所有 fallback 条目")

    # dump — 导出设置摘要用于支持
    dump_p = subparsers.add_parser("dump", help="导出设置摘要用于支持调试")
    dump_p.add_argument("--show-keys", action="store_true", help="显示（脱敏的）API密钥")

    # claw — OpenClaw 迁移
    claw_p = subparsers.add_parser("claw", help="OpenClaw 迁移工具")
    claw_subparsers = claw_p.add_subparsers(dest="claw_action")

    claw_migrate = claw_subparsers.add_parser("migrate", help="从 OpenClaw 迁移")
    claw_migrate.add_argument("--source", help="OpenClaw 目录路径 (默认 ~/.openclaw)")
    claw_migrate.add_argument("--dry-run", action="store_true", help="仅预览")
    claw_migrate.add_argument(
        "--preset", choices=["user-data", "full"], default="full", help="迁移预设"
    )
    claw_migrate.add_argument("--overwrite", action="store_true", help="覆盖现有文件")
    claw_migrate.add_argument("--migrate-secrets", action="store_true", help="包含 API 密钥")
    claw_migrate.add_argument("--no-backup", action="store_true", help="跳过备份")
    claw_migrate.add_argument("--yes", "-y", action="store_true", help="跳过确认")

    claw_cleanup = claw_subparsers.add_parser(
        "cleanup", aliases=["clean"], help="清理 OpenClaw 残留"
    )
    claw_cleanup.add_argument("--source", help="指定目录")
    claw_cleanup.add_argument("--dry-run", action="store_true", help="仅预览")
    claw_cleanup.add_argument("--yes", "-y", action="store_true", help="跳过确认")

    # agent — Agent 管理器
    agent_p = subparsers.add_parser("agent", help="Agent 管理")
    agent_p.add_argument(
        "action", nargs="?", default="status", choices=["status", "list", "create", "run"]
    )

    # bench — 基准测试
    bench_p = subparsers.add_parser("bench", help="性能基准测试")
    bench_p.add_argument("action", nargs="?", default="run", choices=["run", "list", "info"])
    bench_p.add_argument("--iterations", "-n", type=int, default=3, help="测试轮数")

    # profile — Profile 管理
    profile_p = subparsers.add_parser("profile", help="Profile 管理")
    profile_subparsers = profile_p.add_subparsers(dest="profile_action")

    profile_list = profile_subparsers.add_parser("list", help="列出所有 Profile")
    profile_list.add_argument("--verbose", "-v", action="store_true", help="详细信息")

    profile_create = profile_subparsers.add_parser("create", help="创建新 Profile")
    profile_create.add_argument("name", help="Profile 名称")
    profile_create.add_argument("--copy-from", "-c", help="从已有 Profile 复制设置")

    profile_activate = profile_subparsers.add_parser("activate", help="激活 Profile")
    profile_activate.add_argument("name", help="Profile 名称")

    profile_delete = profile_subparsers.add_parser("delete", help="删除 Profile")
    profile_delete.add_argument("name", help="Profile 名称")
    profile_delete.add_argument("--force", "-f", action="store_true", help="强制删除（不提示确认）")

    profile_rename = profile_subparsers.add_parser("rename", help="重命名 Profile")
    profile_rename.add_argument("old_name", help="原名称")
    profile_rename.add_argument("new_name", help="新名称")

    profile_export = profile_subparsers.add_parser("export", help="导出会话")
    profile_export.add_argument("name", help="Profile 名称")
    profile_export.add_argument("output", help="导出路径")

    profile_import = profile_subparsers.add_parser("import", help="导入 Profile")
    profile_import.add_argument("name", help="Profile 名称")
    profile_import.add_argument("input", help="导入路径")

    profile_info = profile_subparsers.add_parser("info", help="显示当前 Profile 信息")
    profile_info.add_argument("name", nargs="?", help="Profile 名称（默认当前）")

    # hooks — Shell钩子管理
    hooks_p = subparsers.add_parser("hooks", help="Shell钩子管理")
    hooks_subparsers = hooks_p.add_subparsers(dest="hooks_action")

    hooks_test = hooks_subparsers.add_parser("test", help="测试钩子")
    hooks_test.add_argument("hook_id", nargs="?", help="钩子ID（留空测试所有）")

    hooks_revoke = hooks_subparsers.add_parser("revoke", help="撤销钩子")
    hooks_revoke.add_argument("hook_id", help="要撤销的钩子ID")

    hooks_subparsers.add_parser("doctor", help="检查钩子配置")

    hooks_subparsers.add_parser("list", help="列出所有钩子")

    # auth — 认证管理
    auth_p = subparsers.add_parser("auth", help="认证管理")
    auth_subparsers = auth_p.add_subparsers(dest="auth_action")

    auth_add = auth_subparsers.add_parser("add", help="添加认证")
    auth_add.add_argument("provider", help="提供商（github, google等）")
    auth_add.add_argument("token", help="认证令牌")

    auth_subparsers.add_parser("list", help="列出已认证的提供商")
    auth_remove = auth_subparsers.add_parser("remove", help="移除认证")
    auth_remove.add_argument("provider", help="提供商名称")
    auth_reset = auth_subparsers.add_parser("reset", help="重置认证")
    auth_reset.add_argument("provider", nargs="?", help="提供商名称（留空重置所有）")
    auth_subparsers.add_parser("status", help="显示认证状态")

    # webhook — Webhook管理
    webhook_p = subparsers.add_parser("webhook", help="Webhook管理")
    webhook_subparsers = webhook_p.add_subparsers(dest="webhook_action")

    webhook_subscribe = webhook_subparsers.add_parser("subscribe", help="订阅Webhook")
    webhook_subscribe.add_argument("url", help="Webhook URL")
    webhook_subscribe.add_argument("--event", "-e", action="append", help="事件类型")

    webhook_unsubscribe = webhook_subparsers.add_parser("unsubscribe", help="取消订阅Webhook")
    webhook_unsubscribe.add_argument("url", help="Webhook URL")

    webhook_test = webhook_subparsers.add_parser("test", help="测试Webhook")
    webhook_test.add_argument("url", help="Webhook URL")
    webhook_test.add_argument("--event", "-e", default="test", help="事件类型")

    webhook_subparsers.add_parser("list", help="列出所有Webhook")

    # backup — 备份命令
    backup_p = subparsers.add_parser("backup", help="备份数据")
    backup_p.add_argument("output", nargs="?", help="备份文件路径（默认自动生成）")
    backup_p.add_argument(
        "--include", action="append", help="包含的项目（sessions, memories, config）"
    )
    backup_p.add_argument("--encrypt", action="store_true", help="加密备份")

    # import_cmd — 导入命令
    import_p = subparsers.add_parser("import", help="导入数据")
    import_p.add_argument("input", help="导入文件路径")
    import_p.add_argument("--type", choices=["backup", "sessions", "memories"], help="导入类型")
    import_p.add_argument("--force", action="store_true", help="强制覆盖现有数据")

    # pairing — 设备配对
    pairing_p = subparsers.add_parser("pairing", help="设备配对管理")
    pairing_subparsers = pairing_p.add_subparsers(dest="pairing_action")

    pairing_start = pairing_subparsers.add_parser("start", help="开始配对")
    pairing_start.add_argument("--timeout", type=int, default=60, help="超时时间（秒）")

    pairing_accept = pairing_subparsers.add_parser("accept", help="接受配对请求")
    pairing_accept.add_argument("device_id", help="设备ID")

    pairing_reject = pairing_subparsers.add_parser("reject", help="拒绝配对请求")
    pairing_reject.add_argument("device_id", help="设备ID")

    pairing_subparsers.add_parser("list", help="列出已配对设备")

    pairing_remove = pairing_subparsers.add_parser("remove", help="移除配对设备")
    pairing_remove.add_argument("device_id", help="设备ID")

    # tools — 工具管理
    tools_p = subparsers.add_parser("tools", help="工具管理")
    tools_subparsers = tools_p.add_subparsers(dest="tools_action")

    tools_list = tools_subparsers.add_parser("list", help="列出所有可用工具")
    tools_list.add_argument("--verbose", "-v", action="store_true", help="详细信息")

    tools_enable = tools_subparsers.add_parser("enable", help="启用工具")
    tools_enable.add_argument("tool_name", help="工具名称")

    tools_disable = tools_subparsers.add_parser("disable", help="禁用工具")
    tools_disable.add_argument("tool_name", help="工具名称")

    tools_info = tools_subparsers.add_parser("info", help="显示工具信息")
    tools_info.add_argument("tool_name", help="工具名称")

    # debug — 调试命令
    debug_p = subparsers.add_parser("debug", help="调试命令")
    debug_subparsers = debug_p.add_subparsers(dest="debug_action")

    debug_share = debug_subparsers.add_parser("share", help="分享调试报告")
    debug_share.add_argument("--session-id", help="会话ID")
    debug_share.add_argument("--include-logs", action="store_true", help="包含日志")

    debug_logs = debug_subparsers.add_parser("logs", help="查看日志")
    debug_logs.add_argument("--lines", type=int, default=50, help="行数")
    debug_logs.add_argument(
        "--level", choices=["debug", "info", "warning", "error"], help="日志级别"
    )

    # whatsapp — WhatsApp集成
    whatsapp_p = subparsers.add_parser("whatsapp", help="WhatsApp集成")
    whatsapp_subparsers = whatsapp_p.add_subparsers(dest="whatsapp_action")

    whatsapp_start = whatsapp_subparsers.add_parser("start", help="启动WhatsApp Bot")
    whatsapp_start.add_argument("--phone", help="手机号码")

    whatsapp_subparsers.add_parser("stop", help="停止WhatsApp Bot")

    whatsapp_subparsers.add_parser("status", help="查看WhatsApp连接状态")

    # slack — Slack集成
    slack_p = subparsers.add_parser("slack", help="Slack集成")
    slack_subparsers = slack_p.add_subparsers(dest="slack_action")

    slack_start = slack_subparsers.add_parser("start", help="启动Slack Bot")
    slack_start.add_argument("--team", help="Team ID")

    slack_subparsers.add_parser("stop", help="停止Slack Bot")

    slack_subparsers.add_parser("status", help="查看Slack连接状态")

    # login/logout — 登录登出
    login_p = subparsers.add_parser("login", help="登录到服务")
    login_p.add_argument(
        "provider", nargs="?", choices=["github", "google", "anthropic"], help="提供商"
    )
    login_p.add_argument("--token", help="直接提供令牌")

    logout_p = subparsers.add_parser("logout", help="登出服务")
    logout_p.add_argument(
        "provider",
        nargs="?",
        choices=["github", "google", "anthropic", "all"],
        help="提供商（默认所有）",
    )

    # plugins — 插件管理
    plugins_p = subparsers.add_parser("plugins", help="插件管理")
    plugins_subparsers = plugins_p.add_subparsers(dest="plugins_action")

    plugins_subparsers.add_parser("list", aliases=["ls"], help="列出已安装插件")
    plugins_install = plugins_subparsers.add_parser("install", help="安装插件")
    plugins_install.add_argument("identifier", help="插件标识符（Git URL 或 owner/repo）")
    plugins_install.add_argument("--enable", action="store_true", help="安装后启用")
    plugins_install.add_argument("--no-enable", action="store_true", help="安装后不启用")
    plugins_install.add_argument("--force", action="store_true", help="强制重新安装")

    plugins_update = plugins_subparsers.add_parser("update", help="更新插件")
    plugins_update.add_argument("name", nargs="?", help="插件名称（留空更新所有）")

    plugins_remove = plugins_subparsers.add_parser(
        "remove", aliases=["rm", "uninstall"], help="卸载插件"
    )
    plugins_remove.add_argument("name", help="插件名称")

    plugins_enable = plugins_subparsers.add_parser("enable", help="启用插件")
    plugins_enable.add_argument("name", help="插件名称")

    plugins_disable = plugins_subparsers.add_parser("disable", help="禁用插件")
    plugins_disable.add_argument("name", help="插件名称")

    # sessions — 会话管理
    sessions_p = subparsers.add_parser(
        "sessions", help="会话历史管理（列表、浏览、重命名、导出、删除）"
    )
    sessions_subparsers = sessions_p.add_subparsers(dest="sessions_action")

    sessions_list = sessions_subparsers.add_parser("list", help="列出最近会话")
    sessions_list.add_argument("--source", help="按来源过滤（cli, telegram, discord等）")
    sessions_list.add_argument("--limit", type=int, default=20, help="最大显示数量")

    sessions_browse = sessions_subparsers.add_parser(
        "browse", help="交互式会话浏览器 — 浏览、搜索和恢复会话"
    )
    sessions_browse.add_argument("--source", help="按来源过滤")
    sessions_browse.add_argument("--limit", type=int, default=500, help="最大加载数量")

    sessions_export = sessions_subparsers.add_parser("export", help="导出会话到JSONL文件")
    sessions_export.add_argument("output", help="输出JSONL文件路径（使用-输出到stdout）")
    sessions_export.add_argument("--source", help="按来源过滤")
    sessions_export.add_argument("--session-id", help="导出特定会话")

    sessions_delete = sessions_subparsers.add_parser("delete", help="删除特定会话")
    sessions_delete.add_argument("session_id", help="要删除的会话ID")
    sessions_delete.add_argument("--yes", "-y", action="store_true", help="跳过确认")

    sessions_prune = sessions_subparsers.add_parser("prune", help="删除旧会话")
    sessions_prune.add_argument(
        "--older-than", type=int, default=90, help="删除N天前的会话（默认90天）"
    )
    sessions_prune.add_argument("--source", help="仅删除此来源的会话")
    sessions_prune.add_argument("--yes", "-y", action="store_true", help="跳过确认")

    sessions_rename = sessions_subparsers.add_parser("rename", help="设置或更改会话标题")
    sessions_rename.add_argument("session_id", help="要重命名的会话ID")
    sessions_rename.add_argument("title", nargs="+", help="会话新标题")

    sessions_subparsers.add_parser("stats", help="显示会话存储统计")

    sessions_branch = sessions_subparsers.add_parser("branch", help="创建会话分支（fork）")
    sessions_branch.add_argument("session_id", help="源会话ID")
    sessions_branch.add_argument("--title", "-t", help="新会话标题")

    return parser


def cmd_repl(args):
    """启动交互式 REPL。"""
    from prometheus.repl import main as repl_main

    repl_main()


def _check_first_run(config):
    user_name = config.get("user.name", "")
    if user_name:
        return False
    from prometheus.config import get_prometheus_home

    prometheus_home = get_prometheus_home()
    user_md = prometheus_home / "memories" / "USER.md"
    if not user_md.exists():
        return True
    try:
        with open(user_md, encoding="utf-8") as f:
            content = f.read()
        if "名字：探索者" in content:
            return True
    except Exception:
        pass
    return False


def _free_input(prompt_text):
    print(prompt_text)
    print("(请用一段话自由描述，输入完成后按回车）")
    lines = []
    while True:
        try:
            line = input(">>> ").rstrip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if line == "" and lines:
            break
        if line:
            lines.append(line)
    return "\n".join(lines) if lines else ""


def _run_chat_onboarding(config):
    print("✨ 欢迎来到 Prometheus！检测到你是首次进入 Chat 模式。\n")
    print("在开始对话之前，让我先了解你。请用自然语言自由描述即可。\n")

    answers = {}

    print("首先，你的名字（或代号）是？")
    while True:
        try:
            name = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            name = "探索者"
            break
        if name:
            break
        print("名字不能为空，请重新输入：")
    answers["name"] = name

    print(f"\n{name}，请描述你希望的沟通风格。")
    answers["communication_style"] = _free_input(
        "比如：简洁直接、代码优先？还是温和耐心、解释详尽？或者你习惯中英夹杂、频繁打断？都可以说。"
    )

    print("\n请描述你的工作偏好。")
    answers["work_preference"] = _free_input(
        "比如：追求快速交付不求完美？还是每一行都要经过审慎测试？或者你偏好边写边学、深入理解每个细节？"
    )

    print("\n你希望我以什么样的风格与你互动？")
    answers["ai_personality"] = _free_input(
        "比如：严厉的代码审查者？温柔耐心的导师？一个平等的技术搭档？或者创意爆棚的自由探索者？"
    )

    config.set("user.name", answers["name"])
    config.set("user.communication_style", answers["communication_style"])
    config.set("user.work_preference", answers["work_preference"])
    config.set("user.ai_personality", answers["ai_personality"])
    config.save()

    _update_onboarding_files(answers)

    print(f"\n✨ 个性化设置完成，{name}！现在开始对话吧。\n")

    return config


def _update_onboarding_files(answers):
    from datetime import datetime

    from prometheus.config import get_prometheus_home

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prometheus_home = get_prometheus_home()

    user_content = f"""# 用户画像

## 基本信息
- 名字：{answers["name"]}
- 首次注册：{now}

## 沟通风格
{answers["communication_style"]}

## 工作偏好
{answers["work_preference"]}

## 自定义区
<!-- 在此区域添加您的个人偏好 -->
"""
    user_path = prometheus_home / "memories" / "USER.md"
    with open(user_path, "w", encoding="utf-8") as f:
        f.write(user_content)

    soul_content = f"""# AI 个性定义

## 用户期望的互动风格
{answers["ai_personality"]}

## 行为准则
1. 保持严谨简洁的沟通风格
2. 不确定时主动询问，不猜测
3. 控制权放用户，AI 不自动修改
4. 遵循三查三定原则：查技能/查知识库/查工具；定边界/定分工/定里程碑

## 编码规范
1. 优先编辑现有文件，不创建新文件
2. 不主动创建文档
3. 遵循现有代码风格
"""
    soul_path = prometheus_home / "SOUL.md"
    with open(soul_path, "w", encoding="utf-8") as f:
        f.write(soul_content)


def cmd_chat(args):
    """启动 AI Agent 对话模式。"""
    print("\U0001f525 Prometheus Chat · v" + __version__ + "\n")

    from prometheus.config import Config as PrometheusConfig

    cfg = PrometheusConfig.load()

    if _check_first_run(cfg):
        cfg = _run_chat_onboarding(cfg)

    config_dict = cfg.to_dict()
    model_cfg = config_dict.get("model", {})
    api_cfg = config_dict.get("api", {})

    model = getattr(args, "model", None) or model_cfg.get("name", "") or "gpt-4o"
    base_url = api_cfg.get("base_url", "https://api.openai.com/v1")
    api_key = api_cfg.get("key", "") or os.getenv("OPENAI_API_KEY", "")
    provider = model_cfg.get("provider", "")

    if provider == "anthropic":
        api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
    elif provider == "openrouter":
        api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        base_url = api_cfg.get("base_url", "") or "https://openrouter.ai/api/v1"
    elif provider == "deepseek":
        api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        base_url = api_cfg.get("base_url", "") or "https://api.deepseek.com/v1"

    if not api_key:
        print("⚠️  未配置 API Key。请运行 'ptg setup' 或设置环境变量。")
        print(
            "   支持的 Key: OPENAI_API_KEY, ANTHROPIC_API_KEY, OPENROUTER_API_KEY, DEEPSEEK_API_KEY"
        )
        return

    system_prompt = getattr(args, "system_prompt", None) or (
        "You are Prometheus, the epic chronicler agent. "
        "You manage genetic seeds, maintain the chronicle, and assist with creative and technical tasks. "
        "Use tools when appropriate. Be concise and precise."
    )

    try:
        from prometheus.agent_loop import AIAgent
    except ImportError:
        from agent_loop import AIAgent

    agent = AIAgent(
        system_prompt=system_prompt,
        api_key=api_key,
        base_url=base_url,
        model=model,
        max_iterations=getattr(args, "max_iterations", 50),
        provider=provider,
    )

    if getattr(args, "message", None):
        initial = " ".join(getattr(args, "message", []))
        print(f"\n>>> {initial}\n")
        result = agent.run_conversation(initial)
        print(f"\n{result['text']}\n")
        print(
            f"({result.get('iterations', '?')} 次迭代, {result.get('tool_calls_made', '?')} 次工具调用)"
        )
        return

    from prometheus.slash_commands import ChatSession, SlashCommandDispatcher

    session = ChatSession(agent, config_dict)
    dispatcher = SlashCommandDispatcher(session)

    print("  输入消息开始对话，/help 查看命令，/quit 退出\n")

    while True:
        try:
            user_input = input("\n>>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！🔥")
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            is_cmd, exit_signal = dispatcher.dispatch(user_input)
            if exit_signal == "EXIT":
                print("再见！🔥")
                break
            if is_cmd:
                continue

        try:
            from prometheus.context_references import resolve_context_references

            resolved_input = resolve_context_references(user_input)
        except Exception:
            resolved_input = user_input

        try:
            from prometheus.context_compressor import auto_compress, should_compress

            if should_compress(session.history):
                session.history = auto_compress(session.history)
        except Exception:
            pass

        try:
            result = agent.run_conversation(resolved_input, history=session.history)
            text = result.get("text", "")
            print(f"\n{text}\n")
            session.add_exchange(user_input, text, result.get("cost"))
            session.tool_calls_count += result.get("tool_calls_made", 0)
        except Exception as e:
            print(f"\n错误: {e}\n")


def cmd_gateway(args):
    """网关管理。"""
    from prometheus.gateway_manager import gateway_status, start_gateway, stop_gateway

    if args.action == "status":
        status = gateway_status()
        if status["running"]:
            print(
                f"\n\U0001f310 Gateway 运行中\n  pid: {status['pid']}\n  日志: {status.get('log_file', '')}\n"
            )
        else:
            print("\n\U0001f310 Gateway 未运行\n")
    elif args.action == "start":
        start_gateway(platform=args.platform)
    elif args.action == "stop":
        stop_gateway()
    elif args.action == "serve":
        print(f"\n\U0001f310 Gateway 服务启动 (platform={args.platform})\n")
        start_gateway(platform=args.platform)
    else:
        print("\n\U0001f310 网关管理\n")
        print("  用法:")
        print("    ptg gateway start    启动网关")
        print("    ptg gateway stop     停止网关")
        print("    ptg gateway status   查看状态")


def cmd_cron(args):
    """定时任务管理。"""
    try:
        from prometheus.tools.cron import CronManager
    except ImportError:
        try:
            from prometheus.tools.cron import CronManager
        except ImportError:
            print("\n\U0001f4c5 定时任务系统未安装\n")
            return

    manager = CronManager()

    if args.action == "list":
        tasks = manager.list_tasks()
        if not tasks:
            print("\n\U0001f4c5 无定时任务\n")
        else:
            print(f"\n\U0001f4c5 定时任务 ({len(tasks)} 个)\n")
            for task in tasks:
                print(f"  · {task['name']}")
                print(f"    调度: {task.get('schedule', '?')}")
                print(f"    上次运行: {task.get('last_run', '从未')}")
                print()
    elif args.action == "add":
        if not args.name or not args.schedule:
            print("用法: ptg cron add --name <名称> --schedule <cron表达式> --command <命令>")
            return
        manager.add_task(args.name, args.schedule, args.command or "")
        print(f"\n✅ 已添加: {args.name}\n")
    elif args.action == "remove":
        if not args.name:
            print("用法: ptg cron remove --name <名称>")
            return
        manager.remove_task(args.name)
        print(f"\n✅ 已移除: {args.name}\n")
    elif args.action == "status":
        status = manager.status()
        print("\n\U0001f4c5 Cron 状态")
        print(f"  活跃任务: {status.get('active', 0)}")
        print(f"  总任务: {status.get('total', 0)}\n")
    elif args.action == "run":
        if not args.name:
            print("用法: ptg cron run --name <名称>")
            return
        manager.run_task(args.name)
        print(f"\n✅ 已执行: {args.name}\n")
    else:
        print("\n\U0001f4c5 定时任务管理\n")
        print("  用法:")
        print("    ptg cron list                列出任务")
        print("    ptg cron add --name ...      添加任务")
        print("    ptg cron remove --name ...   移除任务")
        print("    ptg cron status              查看状态")
        print("    ptg cron run --name ...      立即执行")


def cmd_dashboard(args):
    """启动 Web UI 仪表板。"""
    try:
        import fastapi
        import uvicorn
    except ImportError:
        print("\n❌ Web UI 需要 fastapi 和 uvicorn\n")
        print("安装命令:")
        print(f"  {sys.executable} -m pip install 'fastapi' 'uvicorn[standard]'")
        return

    host = getattr(args, "host", "127.0.0.1")
    port = getattr(args, "port", 9119)
    no_open = getattr(args, "no_open", False)
    insecure = getattr(args, "insecure", False)
    tui = getattr(args, "tui", False)

    print(f"\n🔥 Prometheus Web UI · http://{host}:{port}\n")

    if not insecure and host == "0.0.0.0":
        print("⚠️  警告: 使用 0.0.0.0 将允许公网访问")
        print("   使用 --insecure 确认继续\n")

    try:
        from prometheus.web_ui import start_dashboard_server

        start_dashboard_server(
            host=host,
            port=port,
            open_browser=not no_open,
            embedded_tui=tui,
        )
    except Exception as e:
        print(f"\n❌ 启动 Web UI 失败: {e}")
        import traceback

        traceback.print_exc()


def cmd_acp(args):
    """启动 ACP 服务器。"""
    host = getattr(args, "host", "0.0.0.0")
    port = getattr(args, "port", 8080)

    print(f"\n🔌 Prometheus ACP Server · {host}:{port}\n")

    try:
        from prometheus.acp_server import ACPServer

        server = ACPServer(host=host, port=port)
        server.start()
    except KeyboardInterrupt:
        print("\n\n👋 ACP 服务器已停止")
    except Exception as e:
        print(f"\n❌ 启动 ACP 服务器失败: {e}")
        import traceback

        traceback.print_exc()


def cmd_version(args):
    """显示版本信息。"""
    print(f"\n🔥 Prometheus · v{__version__}\n")
    print(f"  代码名: {__codename__}")

    import sys

    print(f"  Python: {sys.version.split()[0]}")

    try:
        import openai

        print(f"  OpenAI SDK: {openai.__version__}")
    except ImportError:
        print("  OpenAI SDK: 未安装")

    try:
        import anthropic

        print(f"  Anthropic SDK: {anthropic.__version__}")
    except ImportError:
        print("  Anthropic SDK: 未安装")

    print()


def cmd_completion(args):
    """生成 Shell 补全脚本。"""
    shell = getattr(args, "shell", "bash")

    if shell == "bash":
        print(generate_bash_completion())
    elif shell == "zsh":
        print(generate_zsh_completion())
    elif shell == "fish":
        print(generate_fish_completion())


def generate_bash_completion() -> str:
    """生成 Bash 补全脚本。"""
    return """# Prometheus CLI Bash Completion
_prometheus() {
    local cur prev words cword
    _init_completion || return

    commands="setup doctor model config status seed gene memory kb dict update skill skills snapshot list-snapshots restore resume repl chat gateway cron dashboard acp version completion insights claw profile hooks auth webhook backup import pairing tools debug whatsapp slack login logout plugins sessions bench"

    if [[ $cword -eq 1 ]]; then
        COMPREPLY=($(compgen -W "$commands" -- "$cur"))
    fi
}

complete -F _prometheus ptg
"""


def generate_zsh_completion() -> str:
    """生成 Zsh 补全脚本。"""
    return """# Prometheus CLI Zsh Completion
_prometheus() {
    local -a commands
    commands=(
        "setup:引导式初始化"
        "doctor:系统健康诊断"
        "model:模型配置"
        "config:配置管理"
        "status:系统状态"
        "seed:种子管理"
        "gene:基因编辑"
        "memory:向量记忆"
        "kb:知识库"
        "dict:语义字典"
        "update:自我更新"
        "skill:技能管理"
        "skills:列出技能"
        "snapshot:创建快照"
        "restore:恢复快照"
        "resume:恢复状态"
        "repl:交互式REPL"
        "chat:AI对话"
        "gateway:网关管理"
        "cron:定时任务"
        "dashboard:Web仪表板"
        "acp:ACP服务器"
        "version:版本信息"
        "completion:Shell补全"
        "insights:行为分析"
        "claw:OpenClaw迁移"
        "profile:Profile管理"
        "hooks:Shell钩子"
        "auth:认证管理"
        "webhook:Webhook管理"
        "backup:备份"
        "import:导入"
        "pairing:设备配对"
        "tools:工具管理"
        "debug:调试"
        "whatsapp:WhatsApp"
        "slack:Slack"
        "login:登录"
        "logout:登出"
        "plugins:插件管理"
        "sessions:会话管理"
        "bench:基准测试"
    )

    _describe 'command' commands
}

compdef _prometheus ptg
"""


def generate_fish_completion() -> str:
    """生成 Fish 补全脚本。"""
    return """# Prometheus CLI Fish Completion
complete -c ptg -f

set -l commands setup doctor model config status seed gene memory kb dict update skill skills snapshot list-snapshots restore resume repl chat gateway cron dashboard acp version completion insights claw profile hooks auth webhook backup import pairing tools debug whatsapp slack login logout plugins sessions bench

for cmd in $commands
    complete -c ptg -n "__fish_use_subcommand" -a $cmd
end
"""


def cmd_insights(args):
    """用户行为分析。"""
    days = getattr(args, "days", 7)
    source = getattr(args, "source", None)

    print(f"\n📊 Prometheus 行为分析 (过去 {days} 天)\n")

    try:
        from prometheus.insights import Insights

        insights = Insights()
        report = insights.generate(days=days, source=source)
        print(insights.format_terminal(report))
    except Exception as e:
        print(f"❌ 生成分析失败: {e}")


def cmd_claw(args):
    """OpenClaw 迁移工具。"""
    action = getattr(args, "claw_action", None)

    if action is None:
        print("\n🦬 OpenClaw 迁移工具\n")
        print("  用法:")
        print("    ptg claw migrate           迁移 OpenClaw 数据")
        print("    ptg claw cleanup          清理残留文件")
        print()
        return

    if action == "migrate":
        from prometheus.claw_migration import migrate_from_openclaw

        source = getattr(args, "source", None)
        dry_run = getattr(args, "dry_run", False)
        preset = getattr(args, "preset", "full")
        overwrite = getattr(args, "overwrite", False)
        migrate_secrets = getattr(args, "migrate_secrets", False)
        no_backup = getattr(args, "no_backup", False)
        yes = getattr(args, "yes", False)

        print("\n🦬 迁移 OpenClaw 数据\n")
        print(f"  预设: {preset}")
        print(f"  模式: {'预览' if dry_run else '执行'}")
        print()

        migrate_from_openclaw(
            source=source,
            dry_run=dry_run,
            preset=preset,
            overwrite=overwrite,
            include_secrets=migrate_secrets,
            backup=not no_backup,
            confirm=yes,
        )

    elif action in ("cleanup", "clean"):
        from prometheus.claw_migration import cleanup_openclaw

        source = getattr(args, "source", None)
        dry_run = getattr(args, "dry_run", False)
        yes = getattr(args, "yes", False)

        print("\n🦬 清理 OpenClaw 残留\n")
        cleanup_openclaw(source=source, dry_run=dry_run, confirm=yes)


def cmd_agent(args):
    """Agent 管理。"""
    print(f"\n\U0001f916 Agent 管理 · Prometheus v{__version__}\n")

    try:
        from prometheus.agents.manager import get_agent_manager
    except ImportError:
        try:
            from agents.manager import get_agent_manager
        except ImportError:
            print("Agent 管理器不可用\n")
            return

    mgr = get_agent_manager()

    if args.action == "status":
        agents = mgr.list_all()
        print(f"  Agents: {len(agents)}\n")
        for a in agents:
            print(f"  · {a.name} [{a.state}]")
        print()
    elif args.action == "list":
        agents = mgr.list_all()
        print(f"  Active agents: {len(agents)}\n")
        for a in agents:
            print(f"  · {a.name or a.agent_id} [{a.state}]")
    elif args.action == "run":
        print("  用法: ptg agent run\n")
    else:
        print("  用法:")
        print("    ptg agent status   查看状态")
        print("    ptg agent list     列出 Agents")
        print("    ptg agent run      运行 Agent\n")


def cmd_profile(args):
    """Profile 管理命令组。"""
    from prometheus.profiles import get_profile_manager

    pm = get_profile_manager()
    action = args.profile_action

    if action == "list":
        profiles = pm.list_profiles()
        active = pm.get_active_profile_name()
        print(f"\n  Profile 列表 (当前: {active}):\n")
        for p in profiles:
            marker = " ● " if p.name == active else "   "
            print(f"  {marker}{p.name}")
            if getattr(args, "verbose", False):
                print(f"      路径: {p.home}")
                print(
                    f"      记忆: {list((p.home / 'memories').glob('*.md')) if (p.home / 'memories').exists() else '无'}"
                )
                print(
                    f"      会话: {len(list((p.home / 'sessions').glob('*.json')))}"
                    if (p.home / "sessions").exists()
                    else "      会话: 0"
                )
        print()

    elif action == "create":
        name = args.name
        copy_from = getattr(args, "copy_from", None)
        try:
            pm.create_profile(name, copy_from=copy_from)
            print(f"  已创建 Profile: {name}")
            if copy_from:
                print(f"  (从 {copy_from} 复制设置)")
        except ValueError as e:
            print(f"  错误: {e}")

    elif action == "activate":
        name = args.name
        try:
            pm.activate_profile(name)
            print(f"  已激活 Profile: {name}")
        except ValueError as e:
            print(f"  错误: {e}")

    elif action == "delete":
        name = args.name
        force = getattr(args, "force", False)
        if not force:
            confirm = input(f"删除 Profile '{name}'？此操作不可撤销。[y/N] ").strip().lower()
            if confirm not in ("y", "yes"):
                print("  已取消。")
                return
        try:
            pm.delete_profile(name, force=True)
            print(f"  已删除 Profile: {name}")
        except ValueError as e:
            print(f"  错误: {e}")

    elif action == "rename":
        old_name = args.old_name
        new_name = args.new_name
        profile = pm.get_profile(old_name)
        if old_name == pm.get_active_profile_name():
            print("  错误: 无法重命名当前激活的 Profile。先激活其他 Profile。")
            return
        profile.home = pm._profiles_dir / new_name
        pm._profiles[old_name].home = profile.home
        print(f"  已重命名 Profile: {old_name} -> {new_name}")

    elif action == "export":
        name = args.name
        output = Path(args.output)
        try:
            pm.export_profile(name, output)
            print(f"  已导出 Profile '{name}' 到 {output}")
        except Exception as e:
            print(f"  错误: {e}")

    elif action == "import":
        name = args.name
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"  错误: 导入路径不存在: {input_path}")
            return
        try:
            pm.import_profile(name, input_path)
            print(f"  已导入 Profile '{name}' 从 {input_path}")
        except Exception as e:
            print(f"  错误: {e}")

    elif action == "info":
        name = getattr(args, "name", None)
        if name:
            try:
                profile = pm.get_profile(name)
            except ValueError:
                print(f"  Profile '{name}' 不存在。")
                return
        else:
            profile = pm.get_active_profile()
        active_marker = " (当前激活)" if profile.is_active else ""
        print(f"\n  Profile: {profile.name}{active_marker}\n")
        print(f"  路径: {profile.home}")
        print(f"  记忆目录: {profile.home / 'memories'}")
        print(f"  会话目录: {profile.home / 'sessions'}")
        print(f"  配置: {profile.home / 'config.yaml'}")
        print(f"  灵魂: {profile.home / 'SOUL.md'}")
        print()


def cmd_plugins(args):
    """插件管理命令组。"""
    try:
        from prometheus.cli.plugins_cmd import plugins_command
    except ImportError:
        try:
            from cli.plugins_cmd import plugins_command
        except ImportError:
            print("\n❌ 插件命令不可用\n")
            return

    plugins_command(args)


def cmd_hooks(args):
    """Shell钩子管理命令组。"""
    from prometheus.hooks.shell_hooks import get_shell_hooks

    hooks = get_shell_hooks()
    action = getattr(args, "hooks_action", None)

    if action is None:
        print("\n  Shell钩子管理\n")
        print("  可用命令:")
        print("    ptg hooks list     - 列出所有钩子")
        print("    ptg hooks test     - 测试钩子")
        print("    ptg hooks revoke   - 撤销钩子")
        print("    ptg hooks doctor   - 检查钩子配置")
        print()
        return

    if action == "list":
        all_hooks = []
        for event, hook_list in hooks._hooks.items():
            for h in hook_list:
                all_hooks.append({"event": event, "hook": h})
        if not all_hooks:
            print("  没有配置任何钩子。")
            return
        print(f"\n  已配置 {len(all_hooks)} 个钩子:\n")
        for i, item in enumerate(all_hooks):
            h = item["hook"]
            status = "✓" if h.enabled else "✗"
            consent = "✓" if h.consent_granted else "✗"
            print(f"  {i + 1}. [{status}] {item['event']} - {h.command[:50]}")
            print(f"      超时: {h.timeout}s | 需要确认: {consent}")

    elif action == "test":
        hook_id = getattr(args, "hook_id", None)
        print("\n  测试钩子执行...")
        result = hooks.fire("pre_tool_call", {"test": True})
        print(f"  已执行 {result.get('hooks_executed', 0)} 个钩子")
        for r in result.get("results", []):
            print(f"    - {r}")

    elif action == "revoke":
        hook_id = getattr(args, "hook_id", None)
        if hook_id:
            hooks._revoked_commands.add(hook_id)
            print(f"  已撤销钩子: {hook_id}")
        else:
            print("  错误: 需要指定钩子ID")

    elif action == "doctor":
        print("\n  Shell钩子配置检查\n")
        from prometheus.doctor import run_doctor_checks

        run_doctor_checks(["shell_hooks"])


def cmd_auth(args):
    """认证管理命令组。"""
    from prometheus.auth_manager import get_auth_manager

    auth = get_auth_manager()
    action = getattr(args, "auth_action", None)

    if action is None:
        print("\n  认证管理\n")
        print("  可用命令:")
        print("    ptg auth list    - 列出已认证的提供商")
        print("    ptg auth add     - 添加认证")
        print("    ptg auth remove  - 移除认证")
        print("    ptg auth reset   - 重置认证")
        print("    ptg auth status  - 显示认证状态")
        print()
        return

    if action == "list":
        providers = auth.list_providers()
        if not providers:
            print("  没有已认证的提供商。")
        else:
            print("\n  已认证的提供商:\n")
            for p in providers:
                print(f"    - {p}")

    elif action == "add":
        provider = getattr(args, "provider", None)
        token = getattr(args, "token", None)
        if not provider or not token:
            print("  错误: 需要提供商和令牌")
            return
        success = auth.add_provider(provider, token)
        if success:
            print(f"  已添加 {provider} 认证")
        else:
            print(f"  添加 {provider} 认证失败")

    elif action == "remove":
        provider = getattr(args, "provider", None)
        if not provider:
            print("  错误: 需要提供商名称")
            return
        auth.remove_provider(provider)
        print(f"  已移除 {provider} 认证")

    elif action == "reset":
        provider = getattr(args, "provider", None)
        if provider:
            auth.reset_provider(provider)
            print(f"  已重置 {provider} 认证")
        else:
            auth.reset_all()
            print("  已重置所有认证")

    elif action == "status":
        status = auth.get_status()
        print("\n  认证状态:\n")
        for k, v in status.items():
            print(f"    {k}: {v}")


def cmd_webhook(args):
    """Webhook管理命令组。"""
    from prometheus.webhook_manager import get_webhook_manager

    wh = get_webhook_manager()
    action = getattr(args, "webhook_action", None)

    if action is None:
        print("\n  Webhook管理\n")
        print("  可用命令:")
        print("    ptg webhook subscribe   - 订阅Webhook")
        print("    ptg webhook unsubscribe - 取消订阅")
        print("    ptg webhook test         - 测试Webhook")
        print("    ptg webhook list        - 列出所有Webhook")
        print()
        return

    if action == "subscribe":
        url = getattr(args, "url", None)
        events = getattr(args, "event", None) or ["*"]
        if not url:
            print("  错误: 需要Webhook URL")
            return
        wh.subscribe(url, events)
        print(f"  已订阅: {url}")

    elif action == "unsubscribe":
        url = getattr(args, "url", None)
        if not url:
            print("  错误: 需要Webhook URL")
            return
        wh.unsubscribe(url)
        print(f"  已取消订阅: {url}")

    elif action == "test":
        url = getattr(args, "url", None)
        event = getattr(args, "event", "test")
        if not url:
            print("  错误: 需要Webhook URL")
            return
        success = wh.test_webhook(url, event)
        if success:
            print(f"  Webhook测试成功: {url}")
        else:
            print(f"  Webhook测试失败: {url}")

    elif action == "list":
        webhooks = wh.list_webhooks()
        if not webhooks:
            print("  没有已订阅的Webhook。")
        else:
            print("\n  已订阅的Webhook:\n")
            for w in webhooks:
                print(f"    - {w['url']} ({', '.join(w['events'])})")


def cmd_backup(args):
    """备份数据命令。"""
    from datetime import datetime

    output = getattr(args, "output", None)
    include = getattr(args, "include", None) or ["sessions", "memories", "config"]
    encrypt = getattr(args, "encrypt", False)

    if not output:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = f"prometheus_backup_{timestamp}.json"

    print("\n  正在备份数据...\n")
    print(f"  输出: {output}")
    print(f"  包含: {', '.join(include)}")
    print(f"  加密: {'是' if encrypt else '否'}")

    backup_data = {"version": "1.0", "timestamp": datetime.now().isoformat(), "includes": include}

    for item in include:
        if item == "sessions":
            from prometheus.session_manager import get_session_browser

            browser = get_session_browser()
            sessions = browser.list_sessions(limit=10000)
            backup_data["sessions"] = [s.to_dict() for s in sessions]
        elif item == "memories":
            from prometheus.memory_system import MemorySystem

            mem = MemorySystem()
            backup_data["memories"] = mem.get_all_memories()
        elif item == "config":
            from prometheus.config import get_config

            backup_data["config"] = get_config()

    with open(output, "w", encoding="utf-8") as f:
        json.dump(backup_data, f, ensure_ascii=False, indent=2)

    print(f"\n  备份完成: {output}")


def cmd_import_data(args):
    """导入数据命令。"""

    input_path = getattr(args, "input", None)
    getattr(args, "type", None)
    getattr(args, "force", False)

    if not input_path:
        print("  错误: 需要输入文件路径")
        return

    input_file = Path(input_path)
    if not input_file.exists():
        print(f"  错误: 文件不存在: {input_path}")
        return

    print("\n  正在导入数据...\n")
    print(f"  输入: {input_path}")

    with open(input_file, encoding="utf-8") as f:
        data = json.load(f)

    imported_count = 0

    if "sessions" in data:
        from prometheus.session_manager import get_session_browser

        browser = get_session_browser()
        for session_data in data["sessions"]:
            try:
                browser._index.create_session(
                    session_id=session_data["session_id"],
                    title=session_data.get("title", ""),
                    metadata=session_data.get("metadata", {}),
                )
                imported_count += 1
            except Exception:
                pass

    if "memories" in data:
        from prometheus.memory_system import MemorySystem

        mem = MemorySystem()
        for memory in data["memories"]:
            mem.add_memory(memory.get("content", ""), memory.get("type", "general"))

    print(f"\n  导入完成: {imported_count} 条会话已导入")


def cmd_pairing(args):
    """设备配对管理命令组。"""
    from prometheus.pairing_manager import get_pairing_manager

    pm = get_pairing_manager()
    action = getattr(args, "pairing_action", None)

    if action is None:
        print("\n  设备配对管理\n")
        print("  可用命令:")
        print("    ptg pairing start   - 开始配对")
        print("    ptg pairing accept - 接受配对请求")
        print("    ptg pairing reject - 拒绝配对请求")
        print("    ptg pairing list   - 列出已配对设备")
        print("    ptg pairing remove - 移除配对设备")
        print()
        return

    if action == "start":
        timeout = getattr(args, "timeout", 60)
        print(f"\n  开始配对 (超时: {timeout}s)...\n")
        code = pm.start_pairing(timeout=timeout)
        print(f"  配对码: {code}")
        print("  请在其他设备上输入此配对码")

    elif action == "accept":
        device_id = getattr(args, "device_id", None)
        if not device_id:
            print("  错误: 需要设备ID")
            return
        pm.accept_pairing(device_id)
        print(f"  已接受配对请求: {device_id}")

    elif action == "reject":
        device_id = getattr(args, "device_id", None)
        if not device_id:
            print("  错误: 需要设备ID")
            return
        pm.reject_pairing(device_id)
        print(f"  已拒绝配对请求: {device_id}")

    elif action == "list":
        devices = pm.list_devices()
        if not devices:
            print("  没有已配对的设备。")
        else:
            print("\n  已配对设备:\n")
            for d in devices:
                print(f"    - {d['name']} ({d['id']}) - {d.get('last_seen', '未知')}")

    elif action == "remove":
        device_id = getattr(args, "device_id", None)
        if not device_id:
            print("  错误: 需要设备ID")
            return
        pm.remove_device(device_id)
        print(f"  已移除设备: {device_id}")


def cmd_tools(args):
    """工具管理命令组。"""
    from prometheus.tools.registry import get_tool_registry

    registry = get_tool_registry()
    action = getattr(args, "tools_action", None)

    if action is None:
        print("\n  工具管理\n")
        print("  可用命令:")
        print("    ptg tools list    - 列出所有可用工具")
        print("    ptg tools enable  - 启用工具")
        print("    ptg tools disable - 禁用工具")
        print("    ptg tools info    - 显示工具信息")
        print()
        return

    if action == "list":
        tools = registry.list_tools()
        verbose = getattr(args, "verbose", False)
        if not tools:
            print("  没有可用工具。")
        else:
            print(f"\n  可用工具 ({len(tools)}):\n")
            for t in tools:
                status = "✓" if t.get("enabled", True) else "✗"
                print(f"    [{status}] {t['name']}")
                if verbose:
                    print(f"         {t.get('description', '无描述')}")

    elif action == "enable":
        tool_name = getattr(args, "tool_name", None)
        if not tool_name:
            print("  错误: 需要工具名称")
            return
        registry.enable_tool(tool_name)
        print(f"  已启用工具: {tool_name}")

    elif action == "disable":
        tool_name = getattr(args, "tool_name", None)
        if not tool_name:
            print("  错误: 需要工具名称")
            return
        registry.disable_tool(tool_name)
        print(f"  已禁用工具: {tool_name}")

    elif action == "info":
        tool_name = getattr(args, "tool_name", None)
        if not tool_name:
            print("  错误: 需要工具名称")
            return
        info = registry.get_tool_info(tool_name)
        if info:
            print(f"\n  工具: {info['name']}\n")
            print(f"  描述: {info.get('description', '无')}")
            print(f"  状态: {'启用' if info.get('enabled', True) else '禁用'}")
        else:
            print(f"  工具不存在: {tool_name}")


def cmd_debug(args):
    """调试命令组。"""
    action = getattr(args, "debug_action", None)

    if action is None:
        print("\n  调试命令\n")
        print("  可用命令:")
        print("    ptg debug share - 分享调试报告")
        print("    ptg debug logs  - 查看日志")
        print()
        return

    if action == "share":
        session_id = getattr(args, "session_id", None)
        include_logs = getattr(args, "include_logs", False)
        print("\n  生成调试报告...\n")
        from prometheus.debug_report import generate_debug_report

        report_url = generate_debug_report(session_id=session_id, include_logs=include_logs)
        if report_url:
            print(f"  报告已生成: {report_url}")
        else:
            print("  报告生成失败")

    elif action == "logs":
        lines = getattr(args, "lines", 50)
        level = getattr(args, "level", None)
        print(f"\n  最近 {lines} 行日志:\n")
        from prometheus.logging_core import get_recent_logs

        logs = get_recent_logs(lines=lines, level=level)
        for log in logs:
            print(f"  {log}")


def cmd_whatsapp(args):
    """WhatsApp集成命令组。"""
    from prometheus.channels.manager import ChannelManager

    action = getattr(args, "whatsapp_action", None)

    if action is None:
        print("\n  WhatsApp集成\n")
        print("  可用命令:")
        print("    ptg whatsapp start  - 启动WhatsApp Bot")
        print("    ptg whatsapp stop   - 停止WhatsApp Bot")
        print("    ptg whatsapp status - 查看连接状态")
        print()
        return

    manager = ChannelManager.get_instance()
    adapter = manager.get_adapter("whatsapp")

    if action == "start":
        getattr(args, "phone", None)
        print("\n  启动WhatsApp Bot...\n")
        if adapter:
            adapter.start()
            print("  WhatsApp Bot已启动")
        else:
            print("  WhatsApp适配器未配置")

    elif action == "stop":
        print("\n  停止WhatsApp Bot...\n")
        if adapter:
            adapter.stop()
            print("  WhatsApp Bot已停止")
        else:
            print("  WhatsApp适配器未配置")

    elif action == "status":
        print("\n  WhatsApp状态:\n")
        if adapter:
            started = getattr(adapter, "_started", False)
            print(f"    状态: {'运行中' if started else '已停止'}")
        else:
            print("    状态: 未配置")


def cmd_slack(args):
    """Slack集成命令组。"""
    from prometheus.channels.manager import ChannelManager

    action = getattr(args, "slack_action", None)

    if action is None:
        print("\n  Slack集成\n")
        print("  可用命令:")
        print("    ptg slack start  - 启动Slack Bot")
        print("    ptg slack stop   - 停止Slack Bot")
        print("    ptg slack status - 查看连接状态")
        print()
        return

    manager = ChannelManager.get_instance()
    adapter = manager.get_adapter("slack_socket")

    if action == "start":
        getattr(args, "team", None)
        print("\n  启动Slack Bot...\n")
        if adapter:
            adapter.start()
            print("  Slack Bot已启动")
        else:
            print("  Slack适配器未配置")

    elif action == "stop":
        print("\n  停止Slack Bot...\n")
        if adapter:
            adapter.stop()
            print("  Slack Bot已停止")
        else:
            print("  Slack适配器未配置")

    elif action == "status":
        print("\n  Slack状态:\n")
        if adapter:
            started = getattr(adapter, "_started", False)
            print(f"    状态: {'运行中' if started else '已停止'}")
        else:
            print("    状态: 未配置")


def cmd_login(args):
    """登录到服务。"""
    provider = getattr(args, "provider", None)
    token = getattr(args, "token", None)

    if not provider:
        print("\n  登录帮助:\n")
        print("    ptg login github      - 使用GitHub登录")
        print("    ptg login google     - 使用Google登录")
        print("    ptg login anthropic  - 使用Anthropic登录")
        print()
        return

    print(f"\n  正在登录 {provider}...\n")

    if token:
        success = True
    else:
        import getpass

        token = getpass.getpass(f"  输入 {provider} 令牌: ")

    from prometheus.auth_manager import get_auth_manager

    auth = get_auth_manager()
    success = auth.add_provider(provider, token)

    if success:
        print(f"  成功登录 {provider}")
    else:
        print(f"  登录 {provider} 失败")


def cmd_logout(args):
    """登出服务。"""
    provider = getattr(args, "provider", None)

    if not provider or provider == "all":
        print("\n  正在登出所有服务...\n")
        from prometheus.auth_manager import get_auth_manager

        auth = get_auth_manager()
        auth.reset_all()
        print("  已登出所有服务")
    else:
        print(f"\n  正在登出 {provider}...\n")
        from prometheus.auth_manager import get_auth_manager

        auth = get_auth_manager()
        auth.remove_provider(provider)
        print(f"  已登出 {provider}")


def cmd_sessions(args):
    """会话历史管理命令组。"""
    import json as _json
    from datetime import datetime, timedelta

    from prometheus.session_manager import get_session_browser

    browser = get_session_browser()

    action = args.sessions_action

    if action == "list":
        sessions = browser.list_sessions(
            source=getattr(args, "source", None),
            limit=getattr(args, "limit", 20),
        )
        if not sessions:
            print("没有找到会话。")
            return
        has_titles = any(s.title for s in sessions)
        if has_titles:
            print(f"{'标题':<32} {'预览':<40} {'最后活跃':<13} {'ID'}")
            print("─" * 110)
        else:
            print(f"{'预览':<50} {'最后活跃':<13} {'来源':<6} {'ID'}")
            print("─" * 95)
        for s in sessions:
            last_active = _relative_time(s.last_accessed)
            preview = ""
            if has_titles:
                title = (s.title or "—")[:30]
                print(f"{title:<32} {preview:<40} {last_active:<13} {s.session_id}")
            else:
                print(
                    f"{preview:<50} {last_active:<13} {s.metadata.get('source', 'cli'):<6} {s.session_id}"
                )

    elif action == "export":
        output = getattr(args, "output", "-")
        session_id = getattr(args, "session_id", None)
        if session_id:
            messages = browser._search.load_transcript(session_id)
            if not messages:
                print(f"会话 '{session_id}' 没有消息。")
                return
            data = {
                "session_id": session_id,
                "messages": messages,
                "exported_at": datetime.now().isoformat(),
            }
            line = _json.dumps(data, ensure_ascii=False) + "\n"
            if output == "-":
                sys.stdout.write(line)
            else:
                with open(output, "w", encoding="utf-8") as f:
                    f.write(line)
                print(f"导出了 1 个会话到 {output}")
        else:
            sessions = browser.list_sessions(source=getattr(args, "source", None), limit=1000)
            if output == "-":
                for s in sessions:
                    messages = browser._search.load_transcript(s.session_id)
                    data = {
                        "session_id": s.session_id,
                        "title": s.title,
                        "messages": messages,
                        "exported_at": datetime.now().isoformat(),
                    }
                    sys.stdout.write(_json.dumps(data, ensure_ascii=False) + "\n")
            else:
                with open(output, "w", encoding="utf-8") as f:
                    for s in sessions:
                        messages = browser._search.load_transcript(s.session_id)
                        data = {
                            "session_id": s.session_id,
                            "title": s.title,
                            "messages": messages,
                            "exported_at": datetime.now().isoformat(),
                        }
                        f.write(_json.dumps(data, ensure_ascii=False) + "\n")
                print(f"导出了 {len(sessions)} 个会话到 {output}")

    elif action == "delete":
        session_id = args.session_id
        if not args.yes:
            confirm = input(f"删除会话 '{session_id}' 及其所有消息？[y/N] ").strip().lower()
            if confirm not in ("y", "yes"):
                print("已取消。")
                return
        try:
            browser.delete_session(session_id)
            print(f"已删除会话 '{session_id}'。")
        except Exception as e:
            print(f"错误: {e}")

    elif action == "prune":
        days = getattr(args, "older_than", 90)
        source = getattr(args, "source", None)
        if not args.yes:
            source_msg = f" from '{source}'" if source else ""
            confirm = input(f"删除 {days} 天前已结束的所有会话{source_msg}？[y/N] ").strip().lower()
            if confirm not in ("y", "yes"):
                print("已取消。")
                return
        cutoff = datetime.now() - timedelta(days=days)
        sessions = browser.list_sessions(source=source, limit=10000)
        deleted = 0
        for s in sessions:
            if s.end_reason:
                try:
                    created = datetime.fromisoformat(s.created_at)
                    if created < cutoff:
                        browser.delete_session(s.session_id)
                        deleted += 1
                except Exception:
                    pass
        print(f"已清理 {deleted} 个会话。")

    elif action == "rename":
        session_id = args.session_id
        title = " ".join(args.title)
        entry = browser._index.get_session(session_id)
        if not entry:
            print(f"会话 '{session_id}' 未找到。")
            return
        entry.title = title
        browser._index._save()
        print(f"会话 '{session_id}' 已重命名为: {title}")

    elif action == "stats":
        sessions = browser.list_sessions(limit=100000)
        total = len(sessions)
        total_messages = sum(s.message_count for s in sessions)
        print(f"总会话数: {total}")
        print(f"总消息数: {total_messages}")

    elif action == "browse":
        from prometheus.cli.main import _session_browse_picker

        sessions = browser.list_sessions(
            source=getattr(args, "source", None),
            limit=getattr(args, "limit", 500) or 500,
        )
        if not sessions:
            print("没有找到会话。")
            return
        session_dicts = [
            {
                "id": s.session_id,
                "title": s.title,
                "preview": "",
                "source": s.metadata.get("source", "cli"),
                "last_active": s.last_accessed,
            }
            for s in sessions
        ]
        selected_id = _session_browse_picker(session_dicts)
        if not selected_id:
            print("已取消。")
            return
        print(f"恢复会话: {selected_id}")
        from prometheus.cli.relaunch import relaunch

        relaunch(["--resume", selected_id])

    elif action == "branch":
        source_id = args.session_id
        new_title = getattr(args, "title", None)
        new_id = browser.branch_session(source_id, new_title)
        if new_id:
            print(f"已创建分支: {new_id}")
            if new_title:
                print(f"标题: {new_title}")
        else:
            print(f"创建分支失败: 源会话 '{source_id}' 未找到。")


def _session_browse_picker(sessions: list) -> str:
    """交互式curses会话浏览器，支持实时搜索过滤。

    返回选定的会话ID，如果取消则返回None。
    使用curses避免tmux/iTerm中的箭头键幽灵复制渲染bug。
    """
    if not sessions:
        print("没有找到会话。")
        return None

    try:
        import curses

        result_holder = [None]

        def _format_row(s, max_x):
            title = (s.get("title") or "").strip()
            preview = (s.get("preview") or "").strip()
            source = s.get("source", "")[:6]
            last_active = _relative_time(s.get("last_active"))
            sid = s["id"][:18]

            fixed_cols = 3 + 12 + 6 + 18 + 6
            name_width = max(20, max_x - fixed_cols)

            if title:
                name = title[:name_width]
            elif preview:
                name = preview[:name_width]
            else:
                name = sid

            return f"{name:<{name_width}}  {last_active:<10}  {source:<5} {sid}"

        def _match(s, query):
            q = query.lower()
            return (
                q in (s.get("title") or "").lower()
                or q in (s.get("preview") or "").lower()
                or q in s.get("id", "").lower()
                or q in (s.get("source") or "").lower()
            )

        def _curses_browse(stdscr):
            curses.curs_set(0)
            if curses.has_colors():
                curses.start_color()
                curses.use_default_colors()
                curses.init_pair(1, curses.COLOR_GREEN, -1)
                curses.init_pair(2, curses.COLOR_YELLOW, -1)
                curses.init_pair(3, curses.COLOR_CYAN, -1)
                curses.init_pair(4, 8, -1)

            cursor = 0
            scroll_offset = 0
            search_text = ""
            filtered = list(sessions)

            while True:
                stdscr.clear()
                max_y, max_x = stdscr.getmaxyx()
                if max_y < 5 or max_x < 40:
                    with contextlib.suppress(curses.error):
                        stdscr.addstr(0, 0, "Terminal too small")
                    stdscr.refresh()
                    stdscr.getch()
                    return

                if search_text:
                    header = f"  浏览会话 — 过滤: {search_text}█"
                    header_attr = curses.A_BOLD
                    if curses.has_colors():
                        header_attr |= curses.color_pair(3)
                else:
                    header = "  浏览会话 — ↑↓ 导航  Enter 选择  输入过滤  Esc 退出"
                    header_attr = curses.A_BOLD
                    if curses.has_colors():
                        header_attr |= curses.color_pair(2)
                with contextlib.suppress(curses.error):
                    stdscr.addnstr(0, 0, header, max_x - 1, header_attr)

                fixed_cols = 3 + 12 + 6 + 18 + 6
                name_width = max(20, max_x - fixed_cols)
                col_header = (
                    f"   {'标题 / 预览':<{name_width}}  {'活跃时间':<10} {'来源':<5} {'ID'}"
                )
                try:
                    dim_attr = curses.color_pair(4) if curses.has_colors() else curses.A_DIM
                    stdscr.addnstr(1, 0, col_header, max_x - 1, dim_attr)
                except curses.error:
                    pass

                visible_rows = max_y - 4
                if visible_rows < 1:
                    visible_rows = 1

                if not filtered:
                    try:
                        msg = "  没有匹配的会话。"
                        stdscr.addnstr(3, 0, msg, max_x - 1, curses.A_DIM)
                    except curses.error:
                        pass
                else:
                    if cursor >= len(filtered):
                        cursor = len(filtered) - 1
                    if cursor < 0:
                        cursor = 0
                    if cursor < scroll_offset:
                        scroll_offset = cursor
                    elif cursor >= scroll_offset + visible_rows:
                        scroll_offset = cursor - visible_rows + 1

                    for draw_i, i in enumerate(
                        range(scroll_offset, min(len(filtered), scroll_offset + visible_rows))
                    ):
                        y = draw_i + 3
                        if y >= max_y - 1:
                            break
                        s = filtered[i]
                        arrow = " → " if i == cursor else "   "
                        row = arrow + _format_row(s, max_x - 3)
                        attr = curses.A_NORMAL
                        if i == cursor:
                            attr = curses.A_BOLD
                            if curses.has_colors():
                                attr |= curses.color_pair(1)
                        with contextlib.suppress(curses.error):
                            stdscr.addnstr(y, 0, row, max_x - 1, attr)

                footer_y = max_y - 1
                if filtered:
                    footer = f"  {cursor + 1}/{len(filtered)} 个会话"
                    if len(filtered) < len(sessions):
                        footer += f" (已过滤，共 {len(sessions)} 个)"
                else:
                    footer = f"  0/{len(sessions)} 个会话"
                with contextlib.suppress(curses.error):
                    stdscr.addnstr(
                        footer_y,
                        0,
                        footer,
                        max_x - 1,
                        curses.color_pair(4) if curses.has_colors() else curses.A_DIM,
                    )

                stdscr.refresh()
                key = stdscr.getch()

                if key in (curses.KEY_UP,):
                    if filtered:
                        cursor = (cursor - 1) % len(filtered)
                elif key in (curses.KEY_DOWN,):
                    if filtered:
                        cursor = (cursor + 1) % len(filtered)
                elif key in (curses.KEY_ENTER, 10, 13):
                    if filtered:
                        result_holder[0] = filtered[cursor]["id"]
                    return
                elif key == 27:
                    if search_text:
                        search_text = ""
                        filtered = list(sessions)
                        cursor = 0
                        scroll_offset = 0
                    else:
                        return
                elif key in (curses.KEY_BACKSPACE, 127, 8):
                    if search_text:
                        search_text = search_text[:-1]
                        if search_text:
                            filtered = [s for s in sessions if _match(s, search_text)]
                        else:
                            filtered = list(sessions)
                        cursor = 0
                        scroll_offset = 0
                elif key == ord("q") and not search_text:
                    return
                elif 32 <= key <= 126:
                    search_text += chr(key)
                    filtered = [s for s in sessions if _match(s, search_text)]
                    cursor = 0
                    scroll_offset = 0

        curses.wrapper(_curses_browse)
        return result_holder[0]

    except Exception:
        pass

    print("\n  浏览会话  (输入数字选择，q取消)\n")
    for i, s in enumerate(sessions):
        title = (s.get("title") or "").strip()
        preview = (s.get("preview") or "").strip()
        label = title or preview or s["id"]
        if len(label) > 50:
            label = label[:47] + "..."
        last_active = _relative_time(s.get("last_active"))
        src = s.get("source", "")[:6]
        print(f"  {i + 1:>3}. {label:<50}  {last_active:<10}  {src}")

    while True:
        try:
            val = input(f"\n  选择 [1-{len(sessions)}]: ").strip()
            if not val or val.lower() in ("q", "quit", "exit"):
                return None
            idx = int(val) - 1
            if 0 <= idx < len(sessions):
                return sessions[idx]["id"]
            print(f"  无效选择。输入 1-{len(sessions)} 或 q 取消。")
        except ValueError:
            print("  无效输入。输入数字或 q 取消。")
        except (KeyboardInterrupt, EOFError):
            print()
            return None


def _relative_time(iso_date: str) -> str:
    """将ISO日期字符串转换为相对时间描述。"""
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        now = datetime.now()
        diff = now - dt

        if diff.days > 365:
            return f"{diff.days // 365}年前"
        elif diff.days > 30:
            return f"{diff.days // 30}月前"
        elif diff.days > 0:
            return f"{diff.days}天前"
        elif diff.seconds > 3600:
            return f"{diff.seconds // 3600}小时前"
        elif diff.seconds > 60:
            return f"{diff.seconds // 60}分钟前"
        else:
            return "刚刚"
    except Exception:
        return iso_date


def cmd_bench(args):
    """性能基准测试。"""
    print(f"\n\U0001f4ca Prometheus Benchmark · v{__version__}\n")

    if args.action == "run":
        print(f"  运行 {args.iterations} 轮基准测试...\n")

        benchmarks = {
            "seed_load": 0.0,
            "gene_decode": 0.0,
            "semantic_search": 0.0,
            "memory_write": 0.0,
            "memory_read": 0.0,
            "sandbox_python": 0.0,
        }

        for _i in range(args.iterations):
            t0 = time.time()
            try:
                from prometheus.sandboxing import run_python

                run_python("sum(range(1000))", timeout_s=5)
            except Exception:
                pass
            benchmarks["sandbox_python"] += time.time() - t0

        for name, total in benchmarks.items():
            avg = total / max(args.iterations, 1)
            print(f"  {name:<20} {avg * 1000:>8.2f} ms")

        print(f"\n  ✅ {args.iterations} 轮测试完成\n")
    elif args.action == "list":
        print("  可用基准测试:")
        print("    · seed_load      — 种子加载速度")
        print("    · gene_decode    — 基因解码速度")
        print("    · semantic_search — 语义搜索速度")
        print("    · memory_write   — 记忆写入速度")
        print("    · memory_read    — 记忆读取速度")
        print("    · sandbox_python  — 沙箱执行速度\n")
    elif args.action == "info":
        print("  Prometheus 性能基准测试系统")
        print(f"  版本: {__version__}")
        print(f"  Python: {sys.version}\n")
    else:
        print("  用法:")
        print("    ptg bench run    运行基准测试")
        print("    ptg bench list   列出测试项")
        print("    ptg bench info   系统信息\n")


def main():
    """CLI 主入口。"""
    parser = build_parser()

    if len(sys.argv) < 2:
        print(BANNER)
        parser.print_help()
        return

    args = parser.parse_args()

    if args.tui:
        from prometheus.tui_chat import run_tui_chat

        run_tui_chat(model=getattr(args, "model", "default"))
        return

    # 命令别名映射
    command_aliases = {
        "s": "setup",
        "d": "doctor",
        "m": "model",
        "c": "config",
        "st": "status",
        "se": "seed",
        "g": "gene",
        "mem": "memory",
        "k": "kb",
        "di": "dict",
        "u": "update",
        "sk": "skill",
        "sp": "snapshot",
        "ls": "list-snapshots",
        "rs": "restore",
        "re": "resume",
        "r": "repl",
        "gw": "gateway",
        "b": "bench",
        "sess": "sessions",
    }

    # 解析实际命令
    actual_command = command_aliases.get(args.command, args.command)

    # 路由到命令处理函数
    commands = {
        "setup": cmd_setup,
        "doctor": cmd_doctor,
        "model": cmd_model,
        "config": cmd_config,
        "status": cmd_status,
        "seed": cmd_seed,
        "gene": cmd_gene,
        "memory": cmd_memory,
        "kb": cmd_kb,
        "dict": cmd_dict,
        "update": cmd_update,
        "repl": cmd_repl,
        "chat": cmd_chat,
        "gateway": cmd_gateway,
        "cron": cmd_cron,
        "dashboard": cmd_dashboard,
        "acp": cmd_acp,
        "version": cmd_version,
        "completion": cmd_completion,
        "insights": cmd_insights,
        "fallback": cmd_fallback,
        "dump": cmd_dump,
        "claw": cmd_claw,
        "agent": cmd_agent,
        "bench": cmd_bench,
        "profile": cmd_profile,
        "hooks": cmd_hooks,
        "auth": cmd_auth,
        "webhook": cmd_webhook,
        "backup": cmd_backup,
        "import": cmd_import_data,
        "pairing": cmd_pairing,
        "tools": cmd_tools,
        "debug": cmd_debug,
        "whatsapp": cmd_whatsapp,
        "slack": cmd_slack,
        "login": cmd_login,
        "logout": cmd_logout,
        "plugins": cmd_plugins,
        "sessions": cmd_sessions,
        "skill": cmd_skill,
        "snapshot": cmd_snapshot,
        "list-snapshots": cmd_list_snapshots,
        "restore": cmd_restore,
        "resume": cmd_resume,
    }

    if actual_command == "skills":
        cmd_skills()
    elif actual_command in commands:
        commands[actual_command](args)
    else:
        print(BANNER)
        parser.print_help()


def cmd_skill(args):
    """技能管理命令。"""
    try:
        from prometheus.tools.skill_loader import SkillLoader
    except ImportError:
        try:
            from skill_loader import SkillLoader
        except ImportError:
            print("\n❌ 技能加载器不可用\n")
            return

    action = args.action
    loader = SkillLoader()
    loader.scan()

    if action == "list":
        # 列出技能
        category = args.category
        print("\n🔧 技能列表\n")

        if category:
            skills = loader.by_category(category)
            print(f"  分类: {category} ({len(skills)} 个)\n")
        else:
            skills = list(loader._skills.values())
            print(f"  总计: {len(skills)} 个技能\n")

        for s in skills:
            print(f"  · {s.meta.name}")
            if s.meta.description:
                print(f"    {s.meta.description[:60]}")
            if s.meta.tags:
                print(f"    标签: {', '.join(s.meta.tags)}")
            print()

    elif action == "view" and args.name:
        # 查看技能
        skill = loader.get(args.name)
        if not skill:
            print(f"\n❌ 未找到技能: {args.name}\n")
            return

        print("\n🔍 技能详情\n")
        print(f"  名称: {skill.meta.name}")
        print(f"  描述: {skill.meta.description}")
        print(f"  版本: {skill.meta.version}")
        print(f"  作者: {skill.meta.author}")
        print(f"  分类: {skill.category}")
        print(f"  标签: {', '.join(skill.meta.tags)}")
        print(f"  路径: {skill.path}")
        print("\n  内容:\n")
        print("  " + "\n  ".join(skill.body.split("\n")))

    elif action == "search" and args.query:
        # 搜索技能
        results = loader.search(args.query)
        print(f"\n🔎 搜索: {args.query} ({len(results)} 个结果)\n")

        for s in results:
            print(f"  · {s.meta.name}")
            if s.meta.description:
                print(f"    {s.meta.description[:60]}")
            print()

    elif action == "create":
        # 创建技能
        print("\n🛠️  技能创建\n")
        print("  提示: 使用内置技能作为参考")
        print("  位置: prometheus/skills/\n")

        if args.name:
            print(f"  创建技能: {args.name}")
            category = args.category or "custom"
            print(f"  分类: {category}")
            print("\n  示例:")
            print("    prometheus/skills/system/doctor_quick_fix/SKILL.md")

    elif action == "suggest":
        # 技能建议
        print("\n💡 技能建议\n")
        print("  分析工作流模式，建议创建新技能")
        print("  提示: 使用长工具链或重复任务触发建议")

    else:
        # 默认帮助
        print("\n🔧 技能管理\n")
        print("  用法:")
        print("    ptg skill list [--category <分类>]  列出技能")
        print("    ptg skill view <名称>               查看技能")
        print("    ptg skill search <查询>              搜索技能")
        print("    ptg skill create <名称> [--category] 创建技能")
        print("    ptg skill suggest                    获取建议")


def cmd_skills():
    """列出可用 Skill 工作流 (向后兼容)。"""
    try:
        from prometheus.tools.skill_loader import SkillLoader
    except ImportError:
        from skill_loader import SkillLoader

    loader = SkillLoader()
    loader.scan()
    skills = loader.all_skills

    print(f"\n🔧 Skill 工作流 ({len(skills)} 个)\n")
    for s in skills:
        print(f"  · {s.meta.name}")
        if s.meta.description:
            print(f"    {s.meta.description[:60]}")
        print()


# ═══════════════════════════════════════════
#   Snapshot 快照管理
# ═══════════════════════════════════════════


def cmd_snapshot(args):
    """创建快照。"""
    try:
        from prometheus.checkpoint_system import get_checkpoint_system, get_session_logger
    except ImportError:
        from checkpoint_system import get_checkpoint_system, get_session_logger

    cp_sys = get_checkpoint_system()
    session_logger = get_session_logger()

    additional_state = {}
    if args.message:
        additional_state["message"] = args.message

    cp = cp_sys.create_snapshot(args.name, additional_state)
    session_logger.log_snapshot(cp.name)

    print("\n📸 快照已创建\n")
    print(f"  名称: {cp.name}")
    print(f"  时间: {cp.timestamp}")
    try:
        from prometheus.checkpoint_system import get_checkpoints_dir

        print(f"  目录: {get_checkpoints_dir()}")
    except ImportError:
        from checkpoint_system import get_checkpoints_dir

        print(f"  目录: {get_checkpoints_dir()}")
    print()


def cmd_list_snapshots(args):
    """列出所有快照。"""
    try:
        from prometheus.checkpoint_system import get_checkpoint_system
    except ImportError:
        from checkpoint_system import get_checkpoint_system

    cp_sys = get_checkpoint_system()
    snapshots = cp_sys.list_snapshots()

    if not snapshots:
        print("\n📸 无快照记录\n")
        return

    print(f"\n📸 快照列表 ({len(snapshots)} 个)\n")
    for i, s in enumerate(snapshots, 1):
        name = s.get("name", "?")
        timestamp = s.get("timestamp", "?")
        state = s.get("state", {})
        message = state.get("message", "")

        line = f"  {i}. {name}"
        if message:
            line += f" — {message}"
        print(line)
        print(f"      {timestamp}")
        print()


def cmd_restore(args):
    """恢复快照。"""
    try:
        from prometheus.checkpoint_system import get_checkpoint_system
    except ImportError:
        from checkpoint_system import get_checkpoint_system

    cp_sys = get_checkpoint_system()
    found = cp_sys.restore_snapshot(args.name)

    if not found:
        print(f"\n❌ 未找到快照: {args.name}\n")


def cmd_resume(args):
    """恢复上次状态（别名）。"""
    try:
        from prometheus.checkpoint_system import get_checkpoint_system
    except ImportError:
        from checkpoint_system import get_checkpoint_system

    cp_sys = get_checkpoint_system()
    found = cp_sys.restore_snapshot("latest")

    if not found:
        print("\n❌ 未找到快照\n")


if __name__ == "__main__":
    main()
