#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║   🔥 ptg — Prometheus CLI                                    ║
║                                                              ║
║   Teach-To-Grow 种子管理的统一命令行入口。                    ║
║                                                              ║
║   命令支持缩写 (推荐使用简短形式):                           ║
║     ptg setup     (s)  引导式初始化                          ║
║     ptg doctor    (d)  系统健康诊断                          ║
║     ptg model     (m)  模型/提供者配置                       ║
║     ptg config    (c)  配置管理                              ║
║     ptg status    (st) 系统状态总览                          ║
║     ptg seed      (se) 种子管理                              ║
║     ptg gene      (g)  基因编辑                              ║
║     ptg memory    (mem) 向量记忆                              ║
║     ptg kb        (k)  知识库管理                            ║
║     ptg dict      (di) 语义字典                              ║
║     ptg skill     (sk) 技能管理                              ║
║     ptg update    (u)  自我更新                              ║
║     ptg repl      (r)  交互式 REPL                           ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
import time
import subprocess

__version__ = "0.8.0"
__codename__ = "Prometheus"

# 确保 tools/ 子目录在搜索路径中
_PROMETHEUS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TOOLS_DIR = os.path.join(_PROMETHEUS_DIR, "tools")
if _PROMETHEUS_DIR not in sys.path:
    sys.path.insert(0, _PROMETHEUS_DIR)
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)


# ═══════════════════════════════════════════
#   Banner
# ═══════════════════════════════════════════

BANNER = """
🔥 Prometheus · Teach-To-Grow
   种子基因编辑器 v{version}

   「神按自己的样子造人，我按人类的基因造种。」
   创始人: Audrey · 001X
""".format(version=__version__)


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
        chat_args = type('Args', (), {})()
        chat_args.model = None
        chat_args.message = None
        chat_args.stream = True
        chat_args.provider = None
        chat_args.list = False
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
            run_doctor_diagnose,
            run_doctor_full,
            run_doctor_fix,
            run_doctor_backups,
            run_doctor_restore,
            emergency_repair
        )
    except ImportError:
        from prometheus.doctor import (
            PrometheusDoctor,
            run_doctor_diagnose,
            run_doctor_full,
            run_doctor_fix,
            run_doctor_backups,
            run_doctor_restore,
            emergency_repair
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


# ═══════════════════════════════════════════
#   Model 模型配置
# ═══════════════════════════════════════════

def cmd_model(args):
    """模型/提供者配置。"""
    from config import Config as PrometheusConfig
    cfg = PrometheusConfig()

    if args.action == 'show':
        print("\n🤖 模型配置\n")
        model_cfg = cfg.to_dict().get('model', {})
        for k, v in model_cfg.items():
            print(f"  {k}: {v}")
    elif args.action == 'set':
        if not args.key or not args.value:
            print("用法: ptg model set <key> <value>")
            print("示例: ptg model set provider openrouter")
            print("      ptg model set name anthropic/claude-sonnet-4")
            return
        cfg.set('model', args.key, args.value)
        print(f"✅ 模型配置已更新: {args.key} = {args.value}")
    elif args.action == 'providers':
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
        model_cfg = cfg.to_dict().get('model', {})
        provider = model_cfg.get('provider', '未配置')
        model = model_cfg.get('name', '未配置')
        print(f"  当前提供者: {provider}")
        print(f"  当前模型: {model}")
        print(f"\n  用法:")
        print(f"    ptg model show         查看完整配置")
        print(f"    ptg model set <k> <v>  修改配置")
        print(f"    ptg model providers    列出支持的提供者")


# ═══════════════════════════════════════════
#   Config 配置管理
# ═══════════════════════════════════════════

def cmd_config(args):
    """配置管理。"""
    from config import Config as PrometheusConfig
    cfg = PrometheusConfig()

    if args.action == 'show' or args.action is None:
        print("\n⚙️ Prometheus 配置\n")
        for section, values in cfg.to_dict().items():
            if isinstance(values, dict):
                print(f"  [{section}]")
                for k, v in values.items():
                    print(f"    {k}: {v}")
            else:
                print(f"  {section}: {values}")
    elif args.action == 'set':
        if not args.key or not args.value:
            print("用法: ptg config set <key> <value>")
            print("示例: ptg config set model.provider openrouter")
            return
        if '.' in args.key:
            section, k = args.key.rsplit('.', 1)
            cfg.set(section, k, args.value)
        else:
            cfg.set('general', args.key, args.value)
        print(f"✅ 已更新: {args.key} = {args.value}")
    elif args.action == 'path':
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
    print(f"  🌱 种子: {ss['total_seeds']} 个 · {ss['total_genes']} 基因 · {ss['total_concepts']} 概念")

    # Wiki
    from knowledge import KnowledgeManager
    km = KnowledgeManager()
    ks = km.stats()
    wiki_icon = "✅" if ks['wiki_connected'] else "❌"
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
        print(f"  🧠 记忆: 未初始化")

    # 配置
    from config import Config as PrometheusConfig
    cfg = PrometheusConfig()
    model_cfg = cfg.to_dict().get('model', {})
    provider = model_cfg.get('provider', '?')
    model = model_cfg.get('name', '?')
    print(f"  🤖 模型: {provider}/{model}")

    print()


# ═══════════════════════════════════════════
#   Seed 种子管理
# ═══════════════════════════════════════════

def cmd_seed(args):
    """种子管理。"""
    if args.action == 'list':
        from knowledge import SeedIndex
        si = SeedIndex()
        seeds = si.list_seeds()
        if not seeds:
            print("未发现种子")
            return
        print(f"\n🌱 种子列表 ({len(seeds)} 个)\n")
        for s in seeds:
            print(f"  · {s['name']} (v{s['version']}) — {s['gene_count']} 基因 · {s['concept_count']} 概念")
            print(f"    {s['path']}")

    elif args.action == 'search':
        query = args.query or args.seed_path
        if not query:
            query = ' '.join(args.query) if isinstance(args.query, list) else args.query
        if not query:
            print("用法: ptg seed search <查询>")
            return
        from knowledge import SeedIndex
        si = SeedIndex()
        results = si.search(query)
        if not results:
            print(f"未找到匹配: {query}")
        else:
            print(f"\n🔍 种子搜索: \"{query}\" · {len(results)} 条\n")
            for r in results:
                print(f"  · {r['name']} — {r['description'][:60]}")

    elif args.action == 'view' and args.seed_path:
        sys.path.insert(0, _PROMETHEUS_DIR)
        from prometheus import cmd_view
        cmd_view(args.seed_path)

    elif args.action == 'decode' and args.seed_path:
        sys.path.insert(0, _PROMETHEUS_DIR)
        from prometheus import cmd_decode
        cmd_decode(args.seed_path)

    elif args.action == 'health' and args.seed_path:
        sys.path.insert(0, _PROMETHEUS_DIR)
        from genes.analyzer import GeneHealthAuditor, print_gene_health_report
        from prometheus import load_seed
        data = load_seed(args.seed_path)
        if data:
            auditor = GeneHealthAuditor()
            result = auditor.audit_seed(data)
            print_gene_health_report(result)

    elif args.action == 'vault':
        sys.path.insert(0, _PROMETHEUS_DIR)
        from prometheus import cmd_vault
        cmd_vault()

    elif args.action == 'create' and args.seed_path:
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
    if args.action == 'list' and args.seed_path:
        sys.path.insert(0, _PROMETHEUS_DIR)
        from prometheus import cmd_genes
        cmd_genes(args.seed_path)

    elif args.action == 'library':
        sys.path.insert(0, _PROMETHEUS_DIR)
        from genes.analyzer import GeneLibrary
        lib = GeneLibrary()
        print("\n🧬 标准基因库:")
        for g in lib.list_standard():
            gid = g.get('locus', g.get('gene_id', '?'))
            carbon = " ◆碳基" if g.get('carbon_bonded') else ""
            print(f"  {gid} · {g.get('name', '?')}{carbon}")
            print(f"    {g.get('description', '')[:60]}")

    elif args.action == 'edit' and args.seed_path:
        sys.path.insert(0, _PROMETHEUS_DIR)
        from prometheus import cmd_edit
        cmd_edit(args.seed_path)

    elif args.action == 'fusion' and args.seed_path:
        if not args.other:
            print("用法: ptg gene fusion <种子A> <种子B>")
            return
        sys.path.insert(0, _PROMETHEUS_DIR)
        from genes.analyzer import GeneFusionAnalyzer, print_fusion_report
        from prometheus import load_seed
        data_a = load_seed(args.seed_path)
        data_b = load_seed(args.other)
        if data_a and data_b:
            genes_a = data_a.get('dna_encoding', {}).get('gene_loci', []) if isinstance(data_a.get('dna_encoding'), dict) else []
            genes_b = data_b.get('dna_encoding', {}).get('gene_loci', []) if isinstance(data_b.get('dna_encoding'), dict) else []
            analyzer = GeneFusionAnalyzer()
            result = analyzer.analyze_fusion(genes_a, genes_b, os.path.basename(args.seed_path), os.path.basename(args.other))
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

    if args.action == 'remember' and args.text:
        result = mem.remember(args.text, layer="working", source="cli")
        print(f"🧠 已记住 · id={result['id']} · ~{result['token_estimate']}tok")

    elif args.action == 'recall':
        query = args.query
        if not query and args.text:
            query = ' '.join(args.text)
        if not query:
            print("用法: ptg memory recall <查询>")
            return
        results = mem.recall(query, limit=5)
        if not results:
            print("未找到相关记忆")
        else:
            print(f"\n🔍 语义检索: \"{query}\" · {len(results)} 条\n")
            for i, r in enumerate(results, 1):
                print(f"  {i}. [{r['layer']}] {r['content'][:80]}")
                print(f"     相似度: {r['similarity']:.4f}")

    elif args.action == 'status':
        s = mem.summary()
        print(f"\n🧠 向量记忆系统")
        print(f"  总记忆: {s['total_memories']} 条 · {s['total_tokens']} tok")
        print(f"  工作层: {s['by_layer']['working']} · 情景层: {s['by_layer']['episodic']} · 长期层: {s['by_layer']['longterm']}")
        print(f"  向量维度: {s['vector_dim']} · DB: {s['db_size_kb']} KB")

    elif args.action == 'dump':
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

    if args.action == 'search':
        query = args.query
        if isinstance(query, list):
            query = ' '.join(query) if query else None
        if not query:
            print("用法: ptg kb search <查询>")
            return
        results = km.search(query, limit=5)
        print(f"\n📚 知识检索: \"{query}\" · {results['total']} 条\n")
        if results['seeds']:
            print("  🌱 种子:")
            for r in results['seeds'][:3]:
                print(f"    · {r['name']} ({r['gene_count']}基因)")
        if results['wiki']:
            print("  📖 Wiki:")
            for r in results['wiki'][:3]:
                print(f"    · [{r['maturity']}] {r['title']}")
        if results['local']:
            print("  💾 本地:")
            for r in results['local'][:3]:
                print(f"    · {r['title']}")

    elif args.action == 'stats':
        print(km.summary())

    elif args.action == 'add' and args.title:
        content = args.content or ""
        entry_id = km.add_knowledge(args.title, content)
        print(f"✅ 已添加: {args.title} (id={entry_id})")

    elif args.action == 'wiki':
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
    if args.action == 'scan' and args.filepath:
        filepath = os.path.expanduser(args.filepath)
        if not os.path.exists(filepath):
            print(f"❌ 文件不存在: {filepath}")
            return
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
        from dict_extension import DictExtender
        ext = DictExtender()
        candidates = ext.scan_text(text)
        filtered = ext.filter_candidates(candidates)
        print(f"\n📖 字典扫描: {os.path.basename(filepath)}")
        print(f"  候选: {len(candidates)} · 通过: {len(filtered)}")
        for c in filtered[:10]:
            print(f"    · {c['term']} (频率:{c['frequency']} 分数:{c['score']:.2f})")

    elif args.action == 'view' and args.seed_path:
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

def cmd_update(args):
    """检查更新。"""
    print(f"\n🔥 Prometheus v{__version__}\n")
    print("  当前版本:", __version__)
    print("  代码名称:", __codename__)

    # 检查 git 状态
    git_dir = os.path.join(_PROMETHEUS_DIR, ".git")
    if os.path.isdir(git_dir):
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-1"],
                cwd=_PROMETHEUS_DIR, capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                print(f"  最新提交: {result.stdout.strip()}")
            result = subprocess.run(
                ["git", "status", "--short"],
                cwd=_PROMETHEUS_DIR, capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                changes = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
                if changes > 0:
                    print(f"  ⚠️  {changes} 个未提交的更改")
                else:
                    print(f"  ✅ 工作区干净")
        except Exception:
            print("  ⚠️  无法检查 git 状态")
    else:
        print("  ⚠️  非 git 安装")

    print()


# ═══════════════════════════════════════════
#   主入口 (argparse)
# ═══════════════════════════════════════════

def build_parser():
    """构建 argparse 解析器。"""
    import argparse

    parser = argparse.ArgumentParser(
        prog='ptg',
        description='🔥 Prometheus · Teach-To-Grow 种子基因编辑器',
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
    parser.add_argument('--version', '-V', action='version', version=f'ptg {__version__}')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')

    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # setup (s)
    setup_p = subparsers.add_parser('setup', help='引导式初始化')
    subparsers.add_parser('s', help='(别名) setup - 引导式初始化')

    # doctor (d)
    doctor_p = subparsers.add_parser('doctor', help='系统健康诊断与修复（守门员模式）')
    doctor_p.add_argument('--full', action='store_true', help='深度诊断（全部 8 项检查）')
    doctor_p.add_argument('--fix', action='store_true', help='自动修复网关问题')
    doctor_p.add_argument('--backups', action='store_true', help='列出配置备份')
    doctor_p.add_argument('--restore', help='从指定备份恢复')
    doctor_p.add_argument('--emergency', action='store_true', help='紧急修复模式')
    
    doctor_p_alias = subparsers.add_parser('d', help='(别名) doctor - 系统健康诊断')
    doctor_p_alias.add_argument('--full', action='store_true')
    doctor_p_alias.add_argument('--fix', action='store_true')
    doctor_p_alias.add_argument('--backups', action='store_true')
    doctor_p_alias.add_argument('--restore')
    doctor_p_alias.add_argument('--emergency', action='store_true')

    # model (m)
    model_p = subparsers.add_parser('model', help='模型配置')
    model_p.add_argument('action', nargs='?', default='show', choices=['show', 'set', 'providers'])
    model_p.add_argument('key', nargs='?')
    model_p.add_argument('value', nargs='?')
    
    model_p_alias = subparsers.add_parser('m', help='(别名) model - 模型配置')
    model_p_alias.add_argument('action', nargs='?', default='show', choices=['show', 'set', 'providers'])
    model_p_alias.add_argument('key', nargs='?')
    model_p_alias.add_argument('value', nargs='?')

    # config (c)
    config_p = subparsers.add_parser('config', help='配置管理')
    config_p.add_argument('action', nargs='?', default='show', choices=['show', 'set', 'path'])
    config_p.add_argument('key', nargs='?')
    config_p.add_argument('value', nargs='?')
    
    config_p_alias = subparsers.add_parser('c', help='(别名) config - 配置管理')
    config_p_alias.add_argument('action', nargs='?', default='show', choices=['show', 'set', 'path'])
    config_p_alias.add_argument('key', nargs='?')
    config_p_alias.add_argument('value', nargs='?')

    # status (st)
    subparsers.add_parser('status', help='系统状态总览')
    subparsers.add_parser('st', help='(别名) status - 系统状态总览')

    # seed (se)
    seed_p = subparsers.add_parser('seed', help='种子管理')
    seed_p.add_argument('action', choices=['list', 'search', 'view', 'decode', 'health', 'vault', 'create'])
    seed_p.add_argument('seed_path', nargs='?')
    seed_p.add_argument('--query', '-q')
    
    seed_p_alias = subparsers.add_parser('se', help='(别名) seed - 种子管理')
    seed_p_alias.add_argument('action', choices=['list', 'search', 'view', 'decode', 'health', 'vault', 'create'])
    seed_p_alias.add_argument('seed_path', nargs='?')
    seed_p_alias.add_argument('--query', '-q')

    # gene (g)
    gene_p = subparsers.add_parser('gene', help='基因编辑')
    gene_p.add_argument('action', choices=['list', 'library', 'edit', 'fusion'])
    gene_p.add_argument('seed_path', nargs='?')
    gene_p.add_argument('--other', '-o')
    
    gene_p_alias = subparsers.add_parser('g', help='(别名) gene - 基因编辑')
    gene_p_alias.add_argument('action', choices=['list', 'library', 'edit', 'fusion'])
    gene_p_alias.add_argument('seed_path', nargs='?')
    gene_p_alias.add_argument('--other', '-o')

    # memory (mem)
    mem_p = subparsers.add_parser('memory', help='向量记忆')
    mem_p.add_argument('action', choices=['remember', 'recall', 'status', 'dump'])
    mem_p.add_argument('text', nargs='*')
    mem_p.add_argument('--query', '-q')
    mem_p.add_argument('--limit', '-l', type=int, default=10)
    
    mem_p_alias = subparsers.add_parser('mem', help='(别名) memory - 向量记忆')
    mem_p_alias.add_argument('action', choices=['remember', 'recall', 'status', 'dump'])
    mem_p_alias.add_argument('text', nargs='*')
    mem_p_alias.add_argument('--query', '-q')
    mem_p_alias.add_argument('--limit', '-l', type=int, default=10)

    # kb (k)
    kb_p = subparsers.add_parser('kb', help='知识库')
    kb_p.add_argument('action', choices=['search', 'stats', 'add', 'wiki'])
    kb_p.add_argument('query', nargs='*')
    kb_p.add_argument('--title', '-t')
    kb_p.add_argument('--content', '-c')
    
    kb_p_alias = subparsers.add_parser('k', help='(别名) kb - 知识库')
    kb_p_alias.add_argument('action', choices=['search', 'stats', 'add', 'wiki'])
    kb_p_alias.add_argument('query', nargs='*')
    kb_p_alias.add_argument('--title', '-t')
    kb_p_alias.add_argument('--content', '-c')

    # dict (di)
    dict_p = subparsers.add_parser('dict', help='语义字典')
    dict_p.add_argument('action', choices=['scan', 'view'])
    dict_p.add_argument('filepath', nargs='?')
    dict_p.add_argument('seed_path', nargs='?')
    
    dict_p_alias = subparsers.add_parser('di', help='(别名) dict - 语义字典')
    dict_p_alias.add_argument('action', choices=['scan', 'view'])
    dict_p_alias.add_argument('filepath', nargs='?')
    dict_p_alias.add_argument('seed_path', nargs='?')

    # update (u)
    subparsers.add_parser('update', help='检查更新')
    subparsers.add_parser('u', help='(别名) update - 检查更新')

    # skill (sk) - 技能管理
    skill_p = subparsers.add_parser('skill', help='技能管理')
    skill_p.add_argument('action', nargs='?', default='list', choices=['list', 'view', 'create', 'suggest', 'search'])
    skill_p.add_argument('name', nargs='?', help='技能名称')
    skill_p.add_argument('--category', '-c', help='技能分类')
    skill_p.add_argument('--query', '-q', help='搜索查询')
    
    skill_p_alias = subparsers.add_parser('sk', help='(别名) skill - 技能管理')
    skill_p_alias.add_argument('action', nargs='?', default='list', choices=['list', 'view', 'create', 'suggest', 'search'])
    skill_p_alias.add_argument('name', nargs='?')
    skill_p_alias.add_argument('--category', '-c')
    skill_p_alias.add_argument('--query', '-q')

    # skills (保留向后兼容)
    subparsers.add_parser('skills', help='列出 Skill 工作流')
    
    # snapshot (sp) - 快照管理
    snapshot_p = subparsers.add_parser('snapshot', help='创建快照')
    snapshot_p.add_argument('name', nargs='?', help='快照名称（可选）')
    snapshot_p.add_argument('--message', '-m', help='快照说明')
    
    snapshot_p_alias = subparsers.add_parser('sp', help='(别名) snapshot - 创建快照')
    snapshot_p_alias.add_argument('name', nargs='?')
    snapshot_p_alias.add_argument('--message', '-m')
    
    # list-snapshots (ls) - 列出快照
    subparsers.add_parser('list-snapshots', help='列出所有快照')
    subparsers.add_parser('ls', help='(别名) list-snapshots - 列出快照')
    
    # restore (rs) - 恢复快照
    restore_p = subparsers.add_parser('restore', help='恢复快照')
    restore_p.add_argument('name', nargs='?', default='latest', help='快照名称（默认 latest）')
    
    restore_p_alias = subparsers.add_parser('rs', help='(别名) restore - 恢复快照')
    restore_p_alias.add_argument('name', nargs='?', default='latest')
    
    # resume (r) - 恢复上次状态
    subparsers.add_parser('resume', help='恢复上次状态')
    subparsers.add_parser('re', help='(别名) resume - 恢复上次状态')
    
    # repl (r)
    subparsers.add_parser('repl', help='交互式 REPL 模式')

    # chat — Agent 对话模式
    chat_p = subparsers.add_parser('chat', help='启动 AI Agent 对话')
    chat_p.add_argument('message', nargs='*', help='初始消息（可选）')
    chat_p.add_argument('--model', '-m', help='模型覆盖')
    chat_p.add_argument('--profile', '-p', help='配置 profile')
    chat_p.add_argument('--system-prompt', '-s', help='系统提示词')
    chat_p.add_argument('--max-iterations', '-i', type=int, default=50, help='最大迭代次数')

    # gateway — 网关管理
    gw_p = subparsers.add_parser('gateway', help='网关管理')
    gw_p.add_argument('action', choices=['start', 'stop', 'status', 'serve'])
    gw_p.add_argument('--platform', '-p', default='cli', help='平台类型')

    # cron — 定时任务管理
    cron_p = subparsers.add_parser('cron', help='定时任务管理')
    cron_p.add_argument('action', choices=['list', 'add', 'remove', 'status', 'run'])
    cron_p.add_argument('--name', '-n', help='任务名称')
    cron_p.add_argument('--schedule', help='cron 表达式 (如 "0 8 * * *")')
    cron_p.add_argument('--command', help='任务命令')

    # agent — Agent 管理器
    agent_p = subparsers.add_parser('agent', help='Agent 管理')
    agent_p.add_argument('action', nargs='?', default='status', choices=['status', 'list', 'create', 'run'])

    # bench — 基准测试
    bench_p = subparsers.add_parser('bench', help='性能基准测试')
    bench_p.add_argument('action', nargs='?', default='run', choices=['run', 'list', 'info'])
    bench_p.add_argument('--iterations', '-n', type=int, default=3, help='测试轮数')

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
        with open(user_md, "r", encoding="utf-8") as f:
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
    from prometheus.config import get_prometheus_home
    from datetime import datetime

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

    print(f"\n请描述你的工作偏好。")
    answers["work_preference"] = _free_input(
        "比如：追求快速交付不求完美？还是每一行都要经过审慎测试？或者你偏好边写边学、深入理解每个细节？"
    )

    print(f"\n你希望我以什么样的风格与你互动？")
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
    from prometheus.config import get_prometheus_home
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prometheus_home = get_prometheus_home()

    user_content = f"""# 用户画像

## 基本信息
- 名字：{answers['name']}
- 首次注册：{now}

## 沟通风格
{answers['communication_style']}

## 工作偏好
{answers['work_preference']}

## 自定义区
<!-- 在此区域添加您的个人偏好 -->
"""
    user_path = prometheus_home / "memories" / "USER.md"
    with open(user_path, "w", encoding="utf-8") as f:
        f.write(user_content)

    soul_content = f"""# AI 个性定义

## 用户期望的互动风格
{answers['ai_personality']}

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
    model_cfg = config_dict.get('model', {})
    api_cfg = config_dict.get('api', {})

    model = args.model or model_cfg.get('name', '') or 'gpt-4o'
    base_url = api_cfg.get('base_url', 'https://api.openai.com/v1')
    api_key = api_cfg.get('key', '') or os.getenv('OPENAI_API_KEY', '')
    provider = model_cfg.get('provider', '')

    if provider == 'anthropic':
        api_key = api_key or os.getenv('ANTHROPIC_API_KEY', '')
    elif provider == 'openrouter':
        api_key = api_key or os.getenv('OPENROUTER_API_KEY', '')
        base_url = api_cfg.get('base_url', '') or 'https://openrouter.ai/api/v1'
    elif provider == 'deepseek':
        api_key = api_key or os.getenv('DEEPSEEK_API_KEY', '')
        base_url = api_cfg.get('base_url', '') or 'https://api.deepseek.com/v1'

    if not api_key:
        print("⚠️  未配置 API Key。请运行 'ptg setup' 或设置环境变量。")
        print("   支持的 Key: OPENAI_API_KEY, ANTHROPIC_API_KEY, OPENROUTER_API_KEY, DEEPSEEK_API_KEY")
        return

    system_prompt = args.system_prompt or (
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
        max_iterations=args.max_iterations,
    )

    if args.message:
        initial = ' '.join(args.message)
        print(f"\n>>> {initial}\n")
        result = agent.run_conversation(initial)
        print(f"\n{result['text']}\n")
        print(f"({result.get('iterations', '?')} 次迭代, {result.get('tool_calls_made', '?')} 次工具调用)")
        return

    print("  输入消息开始对话，输入 /quit 退出，/clear 清除上下文\n")
    history = []
    while True:
        try:
            user_input = input("\n>>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！🔥")
            break

        if not user_input:
            continue
        if user_input.lower() in ('/quit', '/exit', '/q'):
            print("再见！🔥")
            break
        if user_input.lower() == '/clear':
            history = []
            print("上下文已清除")
            continue

        try:
            result = agent.run_conversation(user_input, history=history)
            print(f"\n{result['text']}\n")
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": result['text']})
        except Exception as e:
            print(f"\n错误: {e}\n")


def cmd_gateway(args):
    """网关管理。"""
    from prometheus.gateway_manager import gateway_status, start_gateway, stop_gateway

    if args.action == 'status':
        status = gateway_status()
        if status['running']:
            print(f"\n\U0001f310 Gateway 运行中\n  pid: {status['pid']}\n  日志: {status.get('log_file', '')}\n")
        else:
            print("\n\U0001f310 Gateway 未运行\n")
    elif args.action == 'start':
        start_gateway(platform=args.platform)
    elif args.action == 'stop':
        stop_gateway()
    elif args.action == 'serve':
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
            from tools.cron import CronManager
        except ImportError:
            print("\n\U0001f4c5 定时任务系统未安装\n")
            return

    manager = CronManager()

    if args.action == 'list':
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
    elif args.action == 'add':
        if not args.name or not args.schedule:
            print("用法: ptg cron add --name <名称> --schedule <cron表达式> --command <命令>")
            return
        manager.add_task(args.name, args.schedule, args.command or "")
        print(f"\n✅ 已添加: {args.name}\n")
    elif args.action == 'remove':
        if not args.name:
            print("用法: ptg cron remove --name <名称>")
            return
        manager.remove_task(args.name)
        print(f"\n✅ 已移除: {args.name}\n")
    elif args.action == 'status':
        status = manager.status()
        print(f"\n\U0001f4c5 Cron 状态")
        print(f"  活跃任务: {status.get('active', 0)}")
        print(f"  总任务: {status.get('total', 0)}\n")
    elif args.action == 'run':
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

    if args.action == 'status':
        agents = mgr.list_all()
        print(f"  Agents: {len(agents)}\n")
        for a in agents:
            print(f"  · {a.name} [{a.state}]")
        print()
    elif args.action == 'list':
        agents = mgr.list_all()
        print(f"  Active agents: {len(agents)}\n")
        for a in agents:
            print(f"  · {a.name or a.agent_id} [{a.state}]")
    elif args.action == 'run':
        print("  用法: ptg agent run\n")
    else:
        print("  用法:")
        print("    ptg agent status   查看状态")
        print("    ptg agent list     列出 Agents")
        print("    ptg agent run      运行 Agent\n")


def cmd_bench(args):
    """性能基准测试。"""
    print(f"\n\U0001f4ca Prometheus Benchmark · v{__version__}\n")

    if args.action == 'run':
        print(f"  运行 {args.iterations} 轮基准测试...\n")

        benchmarks = {
            "seed_load": 0.0,
            "gene_decode": 0.0,
            "semantic_search": 0.0,
            "memory_write": 0.0,
            "memory_read": 0.0,
            "sandbox_python": 0.0,
        }

        for i in range(args.iterations):
            t0 = time.time()
            try:
                from prometheus.sandboxing import run_python
                run_python("sum(range(1000))", timeout_s=5)
            except Exception:
                pass
            benchmarks["sandbox_python"] += time.time() - t0

        for name, total in benchmarks.items():
            avg = total / max(args.iterations, 1)
            print(f"  {name:<20} {avg*1000:>8.2f} ms")

        print(f"\n  ✅ {args.iterations} 轮测试完成\n")
    elif args.action == 'list':
        print("  可用基准测试:")
        print("    · seed_load      — 种子加载速度")
        print("    · gene_decode    — 基因解码速度")
        print("    · semantic_search — 语义搜索速度")
        print("    · memory_write   — 记忆写入速度")
        print("    · memory_read    — 记忆读取速度")
        print("    · sandbox_python  — 沙箱执行速度\n")
    elif args.action == 'info':
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

    # 命令别名映射
    command_aliases = {
        's': 'setup',
        'd': 'doctor',
        'm': 'model',
        'c': 'config',
        'st': 'status',
        'se': 'seed',
        'g': 'gene',
        'mem': 'memory',
        'k': 'kb',
        'di': 'dict',
        'u': 'update',
        'sk': 'skill',
        'sp': 'snapshot',
        'ls': 'list-snapshots',
        'rs': 'restore',
        're': 'resume',
        'r': 'repl',
        'c': 'chat',
        'gw': 'gateway',
        'b': 'bench',
    }

    # 解析实际命令
    actual_command = command_aliases.get(args.command, args.command)

    # 路由到命令处理函数
    commands = {
        'setup': cmd_setup,
        'doctor': cmd_doctor,
        'model': cmd_model,
        'config': cmd_config,
        'status': cmd_status,
        'seed': cmd_seed,
        'gene': cmd_gene,
        'memory': cmd_memory,
        'kb': cmd_kb,
        'dict': cmd_dict,
        'update': cmd_update,
        'repl': cmd_repl,
        'chat': cmd_chat,
        'gateway': cmd_gateway,
        'cron': cmd_cron,
        'agent': cmd_agent,
        'bench': cmd_bench,
        'skill': cmd_skill,
        'snapshot': cmd_snapshot,
        'list-snapshots': cmd_list_snapshots,
        'restore': cmd_restore,
        'resume': cmd_resume,
    }

    if actual_command == 'skills':
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

    if action == 'list':
        # 列出技能
        category = args.category
        print(f"\n🔧 技能列表\n")
        
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
    
    elif action == 'view' and args.name:
        # 查看技能
        skill = loader.get(args.name)
        if not skill:
            print(f"\n❌ 未找到技能: {args.name}\n")
            return
        
        print(f"\n🔍 技能详情\n")
        print(f"  名称: {skill.meta.name}")
        print(f"  描述: {skill.meta.description}")
        print(f"  版本: {skill.meta.version}")
        print(f"  作者: {skill.meta.author}")
        print(f"  分类: {skill.category}")
        print(f"  标签: {', '.join(skill.meta.tags)}")
        print(f"  路径: {skill.path}")
        print(f"\n  内容:\n")
        print("  " + "\n  ".join(skill.body.split("\n")))
    
    elif action == 'search' and args.query:
        # 搜索技能
        results = loader.search(args.query)
        print(f"\n🔎 搜索: {args.query} ({len(results)} 个结果)\n")
        
        for s in results:
            print(f"  · {s.meta.name}")
            if s.meta.description:
                print(f"    {s.meta.description[:60]}")
            print()
    
    elif action == 'create':
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
    
    elif action == 'suggest':
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
        additional_state['message'] = args.message
    
    cp = cp_sys.create_snapshot(args.name, additional_state)
    session_logger.log_snapshot(cp.name)
    
    print(f"\n📸 快照已创建\n")
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
        name = s.get('name', '?')
        timestamp = s.get('timestamp', '?')
        state = s.get('state', {})
        message = state.get('message', '')
        
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
    found = cp_sys.restore_snapshot('latest')
    
    if not found:
        print("\n❌ 未找到快照\n")


if __name__ == '__main__':
    main()
