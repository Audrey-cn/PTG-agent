#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║   🔥 ptg — Prometheus CLI                                    ║
║                                                              ║
║   Teach-To-Grow 种子管理的统一命令行入口。                    ║
║                                                              ║
║   参照 Hermes Agent CLI 架构设计：                            ║
║     ptg setup     引导式初始化                               ║
║     ptg doctor    系统健康诊断                               ║
║     ptg model     模型/提供者配置                            ║
║     ptg config    配置管理                                   ║
║     ptg status    系统状态总览                               ║
║     ptg seed      种子管理                                   ║
║     ptg gene      基因编辑                                   ║
║     ptg memory    向量记忆                                   ║
║     ptg kb        知识库管理                                 ║
║     ptg dict      语义字典                                   ║
║     ptg update    自我更新                                   ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
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
    print(BANNER)
    print("📋 Prometheus Setup 引导\n")

    from config import Config as PrometheusConfig
    cfg = PrometheusConfig()

    # Step 1: 检查目录
    print("━━━ Step 1/4: 目录检查 ━━━")
    dirs_to_check = {
        "种子仓库": os.path.expanduser("~/.hermes/seed-vault"),
        "数据目录": os.path.join(_PROMETHEUS_DIR, "data"),
        "快照目录": os.path.join(_PROMETHEUS_DIR, "snapshots"),
        "Wiki 知识库": os.path.expanduser("~/.hermes/local-wiki/wiki"),
    }
    for name, path in dirs_to_check.items():
        exists = os.path.isdir(path)
        icon = "✅" if exists else "⚠️ "
        status = "已存在" if exists else "将创建"
        if not exists:
            os.makedirs(path, exist_ok=True)
        print(f"  {icon} {name}: {path} ({status})")

    # Step 2: 检查依赖
    print("\n━━━ Step 2/4: 依赖检查 ━━━")
    deps = {}
    try:
        import numpy
        deps["numpy"] = f"✅ {numpy.__version__}"
    except ImportError:
        deps["numpy"] = "❌ 未安装 (pip install numpy)"
    try:
        import yaml
        deps["pyyaml"] = f"✅ {yaml.__version__}"
    except ImportError:
        deps["pyyaml"] = "⚠️  未安装 (pip install pyyaml)"
    try:
        import sqlite3
        deps["sqlite3"] = f"✅ 内置"
    except ImportError:
        deps["sqlite3"] = "❌ 不可用"
    for name, status in deps.items():
        print(f"  {status} — {name}")

    # Step 3: Wiki 连接
    print("\n━━━ Step 3/4: Wiki 连接 ━━━")
    from knowledge import WikiConnector
    wc = WikiConnector()
    if wc.is_connected:
        print(f"  ✅ Wiki 已连接 ({wc.page_count} 页)")
    else:
        print(f"  ⚠️  Wiki 未连接，将使用本地知识库 fallback")

    # Step 4: 种子仓库
    print("\n━━━ Step 4/4: 种子仓库 ━━━")
    from knowledge import SeedIndex
    si = SeedIndex()
    ss = si.stats()
    print(f"  🌱 发现 {ss['total_seeds']} 个种子 · {ss['total_genes']} 个基因")

    print(f"\n✅ Setup 完成！使用 'ptg status' 查看系统状态。")


# ═══════════════════════════════════════════
#   Doctor 诊断
# ═══════════════════════════════════════════

def cmd_doctor(args):
    """系统健康诊断。"""
    print(BANNER)
    print("🩺 Prometheus Doctor\n")

    issues = []
    warnings = []

    # 1. Python 版本
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 10):
        print(f"  ✅ Python {py_ver}")
    else:
        print(f"  ⚠️  Python {py_ver} (建议 3.10+)")
        warnings.append(f"Python {py_ver} 版本较低")

    # 2. 核心依赖
    print("\n  依赖:")
    try:
        import numpy
        print(f"    ✅ numpy {numpy.__version__}")
    except ImportError:
        print(f"    ❌ numpy 未安装")
        issues.append("numpy 未安装 (向量记忆需要)")
    try:
        import yaml
        print(f"    ✅ pyyaml {yaml.__version__}")
    except ImportError:
        print(f"    ⚠️  pyyaml 未安装 (配置系统需要)")
        warnings.append("pyyaml 未安装")

    # 3. 数据库
    print("\n  存储:")
    db_path = os.path.join(_PROMETHEUS_DIR, "data", "prometheus.db")
    if os.path.exists(db_path):
        size_kb = os.path.getsize(db_path) / 1024
        print(f"    ✅ 主数据库 ({size_kb:.1f} KB)")
    else:
        print(f"    ⚠️  主数据库不存在 (首次使用时自动创建)")

    vec_db = os.path.join(_PROMETHEUS_DIR, "data", "vector_memory.db")
    if os.path.exists(vec_db):
        size_kb = os.path.getsize(vec_db) / 1024
        print(f"    ✅ 向量记忆 ({size_kb:.1f} KB)")
    else:
        print(f"    ⚠️  向量记忆未初始化 (首次使用时自动创建)")

    # 4. Wiki 连接
    print("\n  知识库:")
    from knowledge import WikiConnector, SeedIndex
    wc = WikiConnector()
    if wc.is_connected:
        print(f"    ✅ Wiki 连接正常 ({wc.page_count} 页)")
    else:
        print(f"    ⚠️  Wiki 未连接 (将使用本地 fallback)")
        warnings.append("Wiki 未连接")

    si = SeedIndex()
    ss = si.stats()
    print(f"    ✅ 种子索引 ({ss['total_seeds']} 种子 · {ss['total_genes']} 基因)")

    # 5. 配置
    print("\n  配置:")
    from config import Config as PrometheusConfig
    cfg = PrometheusConfig()
    config_dict = cfg.to_dict()
    if config_dict:
        print(f"    ✅ 配置已加载 ({len(config_dict)} 节)")
    else:
        print(f"    ⚠️  配置为空")
        warnings.append("配置为空")

    # 6. 种子健康
    print("\n  种子健康:")
    vault = os.path.expanduser("~/.hermes/seed-vault")
    if os.path.isdir(vault):
        ttg_files = [f for f in os.listdir(vault) if f.endswith('.ttg')]
        if ttg_files:
            print(f"    ✅ 发现 {len(ttg_files)} 个 .ttg 种子")
        else:
            print(f"    ⚠️  种子仓库为空")
            warnings.append("种子仓库为空")
    else:
        print(f"    ⚠️  种子仓库不存在")

    # 汇总
    print(f"\n{'━' * 40}")
    if not issues and not warnings:
        print("  🎉 全部通过！Prometheus 状态良好。")
    else:
        if issues:
            print(f"  ❌ {len(issues)} 个问题需要修复:")
            for i in issues:
                print(f"    · {i}")
        if warnings:
            print(f"  ⚠️  {len(warnings)} 个警告:")
            for w in warnings:
                print(f"    · {w}")
    print()


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
示例:
  ptg setup                    引导式初始化
  ptg doctor                   系统健康诊断
  ptg status                   系统状态总览
  ptg seed list                列出所有种子
  ptg seed view <路径>         查看种子 DNA
  ptg gene list <路径>         列出基因位点
  ptg memory recall <查询>     语义检索记忆
  ptg kb search <查询>         统一知识检索
  ptg config show              查看配置

创始人: Audrey · 001X
""",
    )
    parser.add_argument('--version', '-V', action='version', version=f'ptg {__version__}')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')

    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # setup
    subparsers.add_parser('setup', help='引导式初始化')

    # doctor
    subparsers.add_parser('doctor', help='系统健康诊断')

    # model
    model_p = subparsers.add_parser('model', help='模型配置')
    model_p.add_argument('action', nargs='?', default='show', choices=['show', 'set', 'providers'])
    model_p.add_argument('key', nargs='?')
    model_p.add_argument('value', nargs='?')

    # config
    config_p = subparsers.add_parser('config', help='配置管理')
    config_p.add_argument('action', nargs='?', default='show', choices=['show', 'set', 'path'])
    config_p.add_argument('key', nargs='?')
    config_p.add_argument('value', nargs='?')

    # status
    subparsers.add_parser('status', help='系统状态总览')

    # seed
    seed_p = subparsers.add_parser('seed', help='种子管理')
    seed_p.add_argument('action', choices=['list', 'search', 'view', 'decode', 'health', 'vault', 'create'])
    seed_p.add_argument('seed_path', nargs='?')
    seed_p.add_argument('--query', '-q')

    # gene
    gene_p = subparsers.add_parser('gene', help='基因编辑')
    gene_p.add_argument('action', choices=['list', 'library', 'edit', 'fusion'])
    gene_p.add_argument('seed_path', nargs='?')
    gene_p.add_argument('--other', '-o')

    # memory
    mem_p = subparsers.add_parser('memory', help='向量记忆')
    mem_p.add_argument('action', choices=['remember', 'recall', 'status', 'dump'])
    mem_p.add_argument('text', nargs='*')
    mem_p.add_argument('--query', '-q')
    mem_p.add_argument('--limit', '-l', type=int, default=10)

    # kb
    kb_p = subparsers.add_parser('kb', help='知识库')
    kb_p.add_argument('action', choices=['search', 'stats', 'add', 'wiki'])
    kb_p.add_argument('query', nargs='*')
    kb_p.add_argument('--title', '-t')
    kb_p.add_argument('--content', '-c')

    # dict
    dict_p = subparsers.add_parser('dict', help='语义字典')
    dict_p.add_argument('action', choices=['scan', 'view'])
    dict_p.add_argument('filepath', nargs='?')
    dict_p.add_argument('seed_path', nargs='?')

    # update
    subparsers.add_parser('update', help='检查更新')

    # skills
    subparsers.add_parser('skills', help='列出 Skill 工作流')
    
    # repl
    subparsers.add_parser('repl', help='交互式 REPL 模式')

    return parser


def cmd_repl(args):
    """启动交互式 REPL。"""
    from prometheus.repl import main as repl_main
    repl_main()


def main():
    """CLI 主入口。"""
    parser = build_parser()

    if len(sys.argv) < 2:
        print(BANNER)
        parser.print_help()
        return

    args = parser.parse_args()

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
    }

    if args.command == 'skills':
        cmd_skills()
    elif args.command in commands:
        commands[args.command](args)
    else:
        print(BANNER)
        parser.print_help()


def cmd_skills():
    """列出可用 Skill 工作流。"""
    from skill_loader import SkillLoader
    loader = SkillLoader()
    skills = loader.scan()
    print(f"\n🔧 Skill 工作流 ({len(skills)} 个)\n")
    for s in sorted(skills, key=lambda x: x.get('name', '')):
        name = s.get('name', '?')
        desc = s.get('description', '')[:60]
        print(f"  · {name}")
        if desc:
            print(f"    {desc}")


if __name__ == '__main__':
    main()
