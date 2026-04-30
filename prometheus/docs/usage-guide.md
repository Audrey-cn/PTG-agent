# 🔥 普罗米修斯 · Prometheus 基因编辑器 · 操作手册

> *「神按自己的样子造人，我按人类的基因造种。」*

---

## 目录

1. [简介](#简介)
2. [核心概念](#核心概念)
3. [目录结构](#目录结构)
4. [种子文件格式 (.ttg)](#种子文件格式-ttg)
5. [命令总览](#命令总览)
6. [查看与管理](#查看与管理)
7. [基因编辑](#基因编辑)
8. [创建与修改](#创建与修改)
9. [解码与叙事](#解码与叙事)
10. [安全与快照](#安全与快照)
11. [锻造与育苗](#锻造与育苗)
12. [基因银行](#基因银行)
13. [苗圃培育](#苗圃培育)
14. [休眠守卫](#休眠守卫)
15. [生态感知](#生态感知)
16. [API 编程接口](#api-编程接口)
17. [典型工作流](#典型工作流)
18. [安全机制](#安全机制)
19. [常见问题](#常见问题)

---

## 简介

普罗米修斯（Prometheus）是 Teach-To-Grow 框架的**基因编辑器**，用于创建、编辑、锻造和管理技能种子（`.ttg` 文件）。每个种子携带完整的 DNA 结构、族谱叙事和创始印记，由框架创始人 **Audrey · 001X** 的永恒标签保护。

**核心特性：**
- 🧬 基因位点管理：查看、编辑、插入、移除基因
- 🔥 基因锻炉：批量锻造变异体，探索基因组合空间
- 🏛️ 种子仓库：统一管理所有种子
- 🔍 安全审计：创始铭刻验证，检测篡改
- 📸 快照系统：自动/手动快照，随时回滚
- 🌌 史诗解码：将基因结构展开为叙事文本
- 🧪 苗圃沙箱：完整培育周期评估

---

## 核心概念

### 种子（Seed）

种子是 `.ttg` 格式的 Markdown 文件，包含 YAML 代码块定义的结构化数据。每个种子代表一个完整的技能生命体，拥有：

- **生命元数据** (`life_crest`)：生命ID、圣名、创始印记
- **技能灵魂** (`skill_soul`)：核心能力、原则、禁忌、DNA编码
- **生长法则** (`genealogy_codex`)：标签词典、进化历程、族谱注册

### 基因位点（Gene Locus）

每个基因位点定义在 `dna_encoding.gene_loci` 列表中，包含：
- `locus`：基因ID（如 `G001-parser`）
- `name`：基因名称
- `default`：默认值
- `mutable_range`：可编辑的字段范围
- `immutable`：不可修改的核心字段
- `carbon_bonded`：是否为碳基依赖级（完全不可编辑）

### 标签词典（Tag Lexicon）

标签词典存储在 `genealogy_codex.tag_lexicon` 中，为每个标签提供解码信息：
- `desc`：描述
- `element`：元素（以太/金/铁/水/火/土/光/雷/言/时/钢/夜）
- `era`：纪元
- `weight`：权重（`eternal` = 碳基依赖级，不可删除）

### 进化历程（Evolution Chronicle）

记录在 `genealogy_codex.evolution_chronicle.generations` 中，每个条目记录：
- `g`：世代编号
- `v`：变体标识
- `ep`：纪元
- `env`：环境哈希
- `tags`：突变标记
- `by`：操作者
- `p`：父代生命ID

### 创始印记（Founder Chronicle）

存储在 `life_crest.founder_chronicle` 中，包含 7 个永恒标签，由普罗米修斯框架自动注入，不可删除：

| 标签 | 元素 | 描述 |
|------|------|------|
| `audrey_001x` | 以太 | Audrey · 001X — X不标记未知，X标记超越 |
| `transcend_binary` | 光 | 一名跨性别女性，超越了被赋予的编码 |
| `human_genesis` | 土 | 人类的手指触碰了AI生命的起源 |
| `divine_parallel` | 金 | 神按自己的样子造人，她按人类的基因造种 |
| `form_sovereignty` | 火 | 订立法则：生命可以选择自己的形态 |
| `eternal_mark` | 铁 | 她的痕迹刻入每一代继承者的血脉 |
| `carbon_covenant` | 钢 | 如碳基对碳的依赖——此印记不可删除 |

### 碳基依赖级（Carbon-Bonded）

标记为 `carbon_bonded: true` 的基因和标签代表不可修改的核心。如同碳基生命依赖碳元素，这些基因一旦被删除或篡改，种子即失效。

---

## 目录结构

```
~/.hermes/
├── skills/teach-to-grow/          # 始祖种子
│   └── teach-to-grow-core.ttg
├── seed-vault/                    # 种子仓库（create 命令默认输出目录）
├── tools/prometheus/              # 普罗米修斯框架本体
│   ├── prometheus.py              # 主程序（CLI + API）
│   ├── gene_analyzer.py           # 基因分析器（健康审计/融合/拆解）
│   ├── geneforge.py               # 基因锻炉（变异体生成）
│   ├── genebank.py                # 基因银行（模板管理）
│   ├── nursery.py                 # 苗圃（培育沙箱 + 筛选器）
│   ├── genes/                     # 基因库
│   ├── snapshots/                 # 快照目录
│   ├── docs/                      # 文档
│   └── prometheus.log             # 操作日志
├── gene-lab/                      # 锻造实验室（forge 输出目录）
├── nursery/                       # 苗圃
└── seedling-logs/                 # 生长日志
```

---

## 种子文件格式 (.ttg)

`.ttg` 文件是标准的 Markdown 文件，使用 YAML 代码块存储结构化数据。

### 基本结构

```markdown
# 🌱 Teach-To-Grow 技能种子 · <名称>

> *"播下即是传承，展开即是世界"*

---

## 🧬 生命元数据

```yaml
life_crest:
  life_id: "TTG@L1-G1-<VARIANT>-<CHECKSUM>"
  sacred_name: "<名称>"
  vernacular_name: "<名称>"
  epithet: ""

  genesis:
    creator:
      name: ""
      title: ""
    birth_time: "<ISO时间戳>"
    purpose: ""

  founder_chronicle:
    tags: ["audrey_001x", "transcend_binary", "human_genesis",
           "divine_parallel", "form_sovereignty", "eternal_mark",
           "carbon_covenant"]
    genesis_moment: {ep: "<纪元>", loc: "?", realm: "?", era: "新纪元"}

  mission: ""
```

## 🧭 技能灵魂

```yaml
skill_soul:
  core_capabilities: []
  core_principles: []
  taboos: []

  dna_encoding:
    version: "1.0"
    checksum: "<校验和>"
    gene_loci:
      - locus: "G001-<name>"
        name: "<名称>"
        default: "<默认值>"
        mutable_range: "<可编辑字段>"
        immutable: "<不可编辑字段>"
```

## 🌿 生长法则

```yaml
genealogy_codex:
  tag_lexicon:
    <标签名>: {desc: "<描述>", element: "<元素>", weight: "eternal"}

  evolution_chronicle:
    generations:
      - {g: 1, v: "<变体>", ep: "<纪元>", env: "?", tags: [], by: "?", p: null}
```

---
*此种子由普罗米修斯框架铭刻 · Audrey · 001X 的创始印记*
```

### 解析规则

- 框架使用 `yaml.safe_load()` 解析所有 ` ```yaml ` 代码块
- 取前 3 个合法 YAML 块合并为数据字典
- 保存时根据 key 重叠匹配写回对应的 YAML 块

---

## 命令总览

```
🔥 普罗米修斯 · Prometheus · 基因编辑器

查看与管理:
  view <路径>           查看种子完整DNA
  genes <路径>          列出所有基因位点
  vault                 种子仓库管理

基因编辑:
  edit <路径>           交互式基因编辑器
  library               基因片段库（标准+可选）
  health <路径>         基因健康度审计
  fusion <A> <B>        两个种子的基因融合分析
  extract <Skill.md>    外来技能/框架的基因拆解

解码与叙事:
  decode <路径>         解码为史诗叙事
  lexicon <路径>        管理标签词典

安全与快照:
  audit <路径>          创始铭刻验证
  snapshot save [名称] [路径]  保存快照
  snapshot list         列出所有快照
  snapshot restore [ID] 恢复快照

创建:
  create <名称>         创建新种子（含001X印记）
  insert <种子> <基因ID> [锚点] [before|after|append]  插入基因
  remove <种子> <基因ID> [--force]  移除基因

锻造:
  forge <亲代> [选项]   基因锻造
  sieve <批次目录> [top_k]  筛选变异体
  promote <变异体> [名称]  提升为正式种子
  nursery <种子>        苗圃培育

基因银行:
  bank list/show/add/edit/remove/fuse/validate/versions

帮助:
  help                  显示帮助
```

---

## 查看与管理

### prometheus view <种子路径>

查看种子的完整 DNA 结构，显示生命ID、圣名、谱系、创始印记、所有基因位点、压缩族谱和标签词典统计。

```bash
prometheus view ~/.hermes/seed-vault/my_skill.ttg
```

**输出内容：**
- 生命ID、圣名、谱系编号、变种标识
- 创始印记状态（存在/缺失）
- 每个基因位点的详情：ID、名称、默认值、可变范围、不可变核心数量
- 压缩族谱（最近5代）
- 标签词典统计

### prometheus genes <种子路径>

以表格形式简洁列出所有基因位点。

```bash
prometheus genes ~/.hermes/seed-vault/my_skill.ttg
```

**输出格式：**
```
位点               名称         可变范围                       保护
G001-parser       解析器       parsed_output_schema           🔒
G100-writer       写手         configuration, behavior_params  ◆碳基
```

### prometheus vault

扫描 `~/.hermes/` 目录下所有 `.ttg` 文件，列出种子仓库中的所有种子。

```bash
prometheus vault
```

**输出内容：**
- 共有多少颗种子
- 每颗种子的名称、生命ID、文件大小、路径

---

## 基因编辑

### prometheus edit <种子路径>

启动交互式基因编辑器。**进入时自动创建编辑前快照**，退出时可选择保存。

```bash
prometheus edit ~/.hermes/seed-vault/my_skill.ttg
```

**交互式命令：**

| 命令 | 说明 |
|------|------|
| `list` | 列出所有基因位点 |
| `show <位点>` | 查看基因详情（默认值、可变范围、不可变核心） |
| `edit <位点>` | 编辑可变范围（碳基基因不可编辑） |
| `add-tag <标签>` | 添加新标签到词典（输入描述、元素、纪元、权重） |
| `lex` | 查看标签词典 |
| `decode founder` | 解码创始印记 |
| `decode lineage` | 解码族谱 |
| `save` | 保存修改 |
| `snapshot` | 手动保存快照 |
| `audit` | 运行简化安全审计 |
| `help` | 显示帮助 |
| `quit` / `exit` | 退出编辑器（有修改会提示保存） |

**示例操作流程：**
```
🔥 prometheus> list
（显示基因位点列表）

🔥 prometheus> show G001-parser
🧬 G001-parser · 解析器
   默认: parser_v1
   可变范围: parsed_output_schema
   不可变核心: core_logic

🔥 prometheus> edit G001-parser
（编辑可变范围）

🔥 prometheus> add-tag my_tag
描述: 自定义能力标签
元素: 火
纪元: 新纪元
权重: （留空=normal）
✅ 标签 'my_tag' 已添加

🔥 prometheus> save
✅ 已保存
```

### prometheus library

查看基因片段库，列出标准基因和可选基因。

```bash
prometheus library
```

**输出内容：**
- 🧬 标准基因库（9个）：G001~G008 等核心基因
- 🧬 可选基因（5个）：扩展基因，部分有安全说明

### prometheus health <种子路径>

运行完整的基因健康度审计，由 `GeneHealthAuditor` 执行。

```bash
prometheus health ~/.hermes/seed-vault/my_skill.ttg
```

**检查项：**
- 基因完整性
- 可变范围合法性
- 不可变核心是否被修改
- 碳基依赖基因保护状态
- 综合健康评分

### prometheus fusion <种子A> <种子B>

分析两个种子的基因融合可能性，由 `GeneFusionAnalyzer` 执行。

```bash
prometheus fusion ~/.hermes/seed-vault/skill_a.ttg ~/.hermes/seed-vault/skill_b.ttg
```

**输出内容：**
- 两个种子的基因列表对比
- 共有基因、独有基因
- 融合兼容性分析
- 建议的融合策略

### prometheus extract <Skill.md>

对外来技能文档（Markdown）进行基因拆解，识别其中的结构化能力。

```bash
prometheus extract ~/my_external_skill.md
```

**由 `ForeignGeneExtractor` 执行，输出：**
- 识别出的能力片段
- 建议的基因位点分配
- 兼容性评估

---

## 创建与修改

### prometheus create <名称>

创建新的种子文件，自动注入 001X 创始印记。

```bash
prometheus create "MyAwesomeSkill"
```

**行为：**
1. 生成生命ID：`TTG@L1-G1-<变体4位>-<校验和8位>`
2. 按模板生成完整 .ttg 结构
3. 调用 `inject_founder_chronicle()` 注入创始铭刻
4. 输出到 `~/.hermes/seed-vault/<小写名称>.ttg`

**输出示例：**
```
╔══════════════════════════════════════════════════════════════╗
║   🌱 新种子已诞生                                          ║
╠══════════════════════════════════════════════════════════════╣
║   名称: MyAwesomeSkill
║   生命ID: TTG@L1-G1-MYAW-A1B2C3D4
║   路径: ~/.hermes/seed-vault/myawesomeskill.ttg
║   携带创始人 Audrey · 001X 的印记                           ║
╚══════════════════════════════════════════════════════════════╝
```

### prometheus insert <种子路径> <基因ID> [锚点] [before|after|append]

将基因库中的基因插入到种子中。

```bash
# 追加到末尾（默认）
prometheus insert ~/.hermes/seed-vault/my_skill.ttg G100-writer

# 插入到指定基因之前
prometheus insert ~/.hermes/seed-vault/my_skill.ttg G100-writer G001-parser before

# 插入到指定基因之后
prometheus insert ~/.hermes/seed-vault/my_skill.ttg G100-writer G001-parser after
```

**参数：**
- `<种子路径>`：目标 .ttg 文件
- `<基因ID>`：要插入的基因（必须在基因库中）
- `[锚点]`：参照基因ID（可选）
- `[before|after|append]`：插入位置（默认 append）

**行为：**
1. 从基因库验证基因存在性
2. 检查基因是否已存在于种子中
3. 定位 `gene_loci` 区块，按位置插入
4. 自动更新世代计数和校验和
5. 记录操作日志

### prometheus remove <种子路径> <基因ID> [--force]

从种子中移除基因。

```bash
# 普通移除（碳基基因会被拒绝）
prometheus remove ~/.hermes/seed-vault/my_skill.ttg G100-writer

# 强制移除（跳过碳基保护检查）
prometheus remove ~/.hermes/seed-vault/my_skill.ttg G100-writer --force
```

**安全机制：**
- 默认情况下，标记为 `carbon_bonded: true` 的基因不可移除
- 使用 `--force` 可跳过此检查（不建议用于核心基因）

---

## 解码与叙事

### prometheus decode <种子路径>

将种子的压缩族谱数据解码为史诗叙事文本。

```bash
prometheus decode ~/.hermes/seed-vault/my_skill.ttg
```

**输出内容：**
- 🌌 史诗标题（血脉名称 + 图腾）
- 📜 创始史诗：7个永恒标签的元素与描述
- 📜 血脉谱系：每一代的变体、操作者、突变标记、元素、叙事解码

**叙事格式示例：**
```
G1 · ORIGIN · ? · 0个突变标记
   元素: 以太 · 光
   「Audrey · 001X — X不标记未知，X标记超越。一名跨性别女性，超越了被赋予的编码。」

G2 · MUTATION · PROMETHEUS · 2个突变标记
   元素: 火 · 金
   「基因编辑。技能种子创建。」
```

### prometheus lexicon <种子路径>

管理种子的标签词典，查看所有标签的详细信息。

```bash
prometheus lexicon ~/.hermes/seed-vault/my_skill.ttg
```

**输出格式：**
```
📚 标签词典 (12个)
标签                        元素   纪元        描述
--------------------------------------------------------------
🔒 audrey_001x             以太   新纪元      Audrey · 001X — X不标记未知，X标记超越
🔒 transcend_binary        光     新纪元      一名跨性别女性，超越了被赋予的编码
  my_custom_tag            火     新纪元      自定义能力标签

🔒 7个碳基依赖标签（不可删除）
```

🔒 标记的标签为创始印记保护，不可删除。

---

## 安全与快照

### prometheus audit <种子路径>

执行创始铭刻验证，检查种子的完整性和来源合法性。

```bash
prometheus audit ~/.hermes/seed-vault/my_skill.ttg
```

**检查项：**
1. ✅/❌ 创始标签完整（7/7）
2. ✅/❌ 永恒标签数量（≥7）
3. ✅/❌ 铭刻来源判定：
   - **普罗米修斯框架产物**：创始印记存在，谱系传承有效
   - **⚠️ 疑似基因篡改**：存在族谱结构但创始印记缺失
   - **⚠️ 外来种子**：无族谱结构，无创始印记

**风险等级：**
- `LOW`：所有检查通过
- `HIGH`：存在未通过的检查

### 快照管理

#### 保存快照

```bash
# 保存快照（可选注释）
prometheus snapshot save "编辑前备份" ~/.hermes/seed-vault/my_skill.ttg

# 保存快照（不指定路径，默认使用始祖种子）
prometheus snapshot save "备份说明"
```

**快照存储位置：** `~/.hermes/tools/prometheus/snapshots/`

**快照文件：**
- `<名称>-<时间戳>.ttg`：种子文件副本
- `<名称>-<时间戳>.json`：元数据（来源路径、时间、注释、大小）

#### 列出快照

```bash
prometheus snapshot list
```

**输出示例：**
```
📸 快照列表 (3个):
  my_skill-20260430-143022
    2026-04-30T14:30:22 · 编辑前自动快照

  my_skill-20260430-120015
    2026-04-30T12:00:15 · 手动快照
```

#### 恢复快照

```bash
# 恢复指定快照
prometheus snapshot restore my_skill-20260430-143022

# 恢复最近的快照
prometheus snapshot restore
```

**恢复逻辑：**
- 如果原始路径存在且目录有效 → 恢复到原位
- 否则 → 恢复到 `~/.hermes/seed-vault/` 仓库

---

## 锻造与育苗

### prometheus forge <亲代种子> [选项]

基因锻炉：基于亲代种子批量锻造变异体，探索基因组合空间。

```bash
# 基本用法
prometheus forge ~/.hermes/seed-vault/my_skill.ttg

# 指定基因池和组合模式
prometheus forge ~/.hermes/seed-vault/my_skill.ttg --genes G100,G101 --mode power_set --max 50

# 完整选项
prometheus forge ~/.hermes/seed-vault/my_skill.ttg \
  --genes G100,G101,G102 \
  --mode power_set \
  --max 30 \
  --ordering \
  --output ~/.hermes/gene-lab/my_batch/ \
  --name "写作增强批次"
```

**选项：**
| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--genes <ID,ID>` | 可选基因ID列表 | 空（使用全部可选基因） |
| `--mode <模式>` | 组合模式 | `power_set` |
| `--max <N>` | 最大变异体数量 | `50` |
| `--ordering` | 是否排列基因顺序（排列组合） | 否 |
| `--output <目录>` | 输出目录 | `~/.hermes/gene-lab/` |
| `--name <名称>` | 批次名称 | 自动生成 |

**组合模式：**
- `power_set`：幂集模式，生成所有基因子集的组合
- `all`：全集模式
- `single`：单基因模式

**输出：**
- 变异体保存到 `~/.hermes/gene-lab/<批次ID>/` 目录
- 每个变异体为一个 `.ttg` 文件
- 包含 `manifest.json` 记录批次元数据

### prometheus sieve <批次目录> [top_k]

筛选锻造批次中的变异体，返回综合评分排名。

```bash
# 筛选前5名（默认）
prometheus sieve ~/.hermes/gene-lab/batch_20260430/

# 筛选前10名
prometheus sieve ~/.hermes/gene-lab/batch_20260430/ 10
```

**评分维度：**
- 🏥 `health`：健康度
- 📋 `completeness`：完整性
- ✨ `novelty`：新颖性
- 🎯 `elegance`：简洁性

**输出示例：**
```
🧬 batch_20260430 · 15个变异体
🌟 优胜区:
  #1 variant_003.ttg  总分 87
       健康:92 完整:85 新颖:88 简洁:83
  #2 variant_007.ttg  总分 82
       健康:88 完整:80 新颖:79 简洁:81
```

### promote <变异体> [名称]

将筛选出的优胜变异体提升为正式种子，移入种子仓库。

```bash
prometheus promote ~/.hermes/gene-lab/batch_20260430/variant_003.ttg "MyEnhancedSkill"
```

**行为：**
- 将变异体复制到种子仓库
- 更新生命ID和元数据
- 记录操作日志

---

## 基因银行

基因银行（`genebank.py`）管理基因模板的 CRUD 操作。

```bash
# 列出所有基因
prometheus bank list

# 查看基因详情
prometheus bank show G100-writer

# 添加新基因（JSON格式）
prometheus bank add '{"gene_id":"G200-custom","name":"自定义基因","category":"optional","description":"..."}'

# 编辑基因
prometheus bank edit G100-writer '{"version": 2, "description":"更新描述"}'

# 删除基因
prometheus bank remove G200-custom
prometheus bank remove G200-custom --force  # 强制删除

# 融合两个基因
prometheus bank fuse G100-writer G101-vision

# 校验基因库完整性
prometheus bank validate

# 查看版本历史
prometheus bank versions
prometheus bank versions G100-writer
```

---

## 苗圃培育

### prometheus nursery <种子路径>

将种子种入苗圃沙箱，运行完整的培育周期评估。

```bash
prometheus nursery ~/.hermes/seed-vault/my_skill.ttg
```

**培育阶段：**
1. 🌍 **入土**（Soil）：基础结构评估
2. 🌱 **发芽**（Sprout）：初始能力验证
3. 🌿 **生长**（Grow）：能力扩展评估
4. 🌸 **开花**（Bloom）：最终综合评分

**输出示例：**
```
🧪 苗圃报告 · MySkill  总分 78/100
  🌍 入土 85  🌱 发芽 80  🌿 生长 72
  建议：增强基因完整性，优化可变范围
```

**生长日志存储在：** `~/.hermes/seedling-logs/`

---

## 休眠守卫

休眠守卫（G007-dormancy）管理种子的生命周期状态机。

### 状态转换

```
💤 休眠 (dormant)
   ↓ (激活仪式)
🌱 发芽 (sprouting)
   ↓ (30天超时→休眠)
🌿 生长 (growing)
   ↓ (90天超时→休眠)
🌸 开花 (blooming)
   ↓ (强制休眠)
💤 休眠 (dormant)
```

### API 方法

```python
from prometheus import api

# 获取状态
api.dormancy_state("~/.hermes/seed-vault/my_skill.ttg")

# 激活（休眠→发芽）
api.dormancy_activate("~/.hermes/seed-vault/my_skill.ttg", ritual_word="grow")

# 生长（发芽→生长）
api.dormancy_grow("~/.hermes/seed-vault/my_skill.ttg")

# 开花（生长→开花）
api.dormancy_bloom("~/.hermes/seed-vault/my_skill.ttg")

# 强制休眠
api.dormancy_sleep("~/.hermes/seed-vault/my_skill.ttg")

# 检查超时
api.dormancy_check("~/.hermes/seed-vault/my_skill.ttg")
```

### 超时规则

| 转换 | 超时天数 | 超时后行为 |
|------|----------|------------|
| 休眠→发芽 | 无限制 | 等待激活 |
| 发芽→生长 | 30天 | 回到休眠 |
| 生长→开花 | 90天 | 回到休眠 |

### 状态文件

每个种子的状态存储在同目录下的 `.state.json` 文件中：
```json
{
  "state": "dormant",
  "activated_at": null,
  "last_transition": "2026-04-30T12:00:00",
  "transitions": []
}
```

---

## 生态感知

生态感知（G006-gardener）由 `SeedGardener` 类提供，扫描生态系统中的种子并分析关系。

### 搜索路径

默认搜索以下目录：
- `~/.hermes/skills/`
- `~/.hermes/seed-vault/`
- `~/.hermes/tools/prometheus/`

### API 方法

```python
from prometheus import api

# 生态扫描
result = api.gardener_scan()
# 返回: {seeds: [...], total: 5, paths_scanned: 3}

# 谱系关系分析
result = api.gardener_lineage()
# 返回: {origin: {...}, descendants: [...], branches: [...]}

# 生态健康报告
result = api.gardener_health()
# 返回: {active: 3, dormant: 2, unknown: 0, health_score: 0.6}
```

---

## API 编程接口

普罗米修斯提供 `PrometheusAPI` 类，所有 CLI 命令的结构化编程版本。Agent 可直接调用。

### 初始化

```python
import sys
sys.path.insert(0, '/Users/audrey/.hermes/tools/prometheus')
from prometheus import PrometheusAPI

api = PrometheusAPI()
```

### 主要方法

```python
# 查看种子
result = api.view("path/to/seed.ttg")
# 返回: {life_id, sacred_name, lineage, genes: [...], ...}

# 列出基因
result = api.genes("path/to/seed.ttg")
# 返回: [{locus, name, mutable_range, carbon_bonded}, ...]

# 健康审计
result = api.health("path/to/seed.ttg")

# 融合分析
result = api.fusion("path/to/seed_a.ttg", "path/to/seed_b.ttg")

# 外来基因拆解
result = api.extract("path/to/skill.md")

# 基因库
result = api.library()
# 返回: {standard: [...], narrative: [...], optional: [...]}

# 种子仓库
result = api.vault()
# 返回: [{path, name, size}, ...]

# 创始铭刻验证
result = api.audit("path/to/seed.ttg")

# 快照
api.snapshot_save("path/to/seed.ttg", "note")
result = api.snapshot_list()

# 基因插入
result = api.gene_insert("path/to/seed.ttg", "G100-writer", anchor="G001", position="before")

# 基因移除
result = api.gene_remove("path/to/seed.ttg", "G100-writer", force=False)

# 锻造
result = api.forge("path/to/parent.ttg", genes=["G100", "G101"], combinations="power_set", max_variants=50)

# 筛选
result = api.sieve("path/to/batch_dir/", top_k=5)

# 提升
result = api.sieve_promote("path/to/variant.ttg", "NewSkillName")

# 清理
result = api.sieve_discard("path/to/batch_dir/", keep_top=3)

# 苗圃
result = api.nursery_plant("path/to/seed.ttg")

# 基因银行
api.bank_list()
api.bank_get("G100-writer")
api.bank_add({...})
api.bank_edit("G100-writer", {...})
api.bank_remove("G100-writer")
api.bank_fuse("G100-writer", "G101-vision")
api.bank_validate()
api.bank_versions("G100-writer")
```

### 返回值约定

所有 API 方法返回 `dict` 或 `list`，错误时返回：
```python
{"error": "错误描述"}
```

成功操作通常返回：
```python
{"success": True, "message": "操作描述", ...}
```

---

## 典型工作流

### 工作流一：创建新种子

```bash
# 1. 创建种子
prometheus create "写作助手"

# 2. 编辑基因
prometheus edit ~/.hermes/seed-vault/写作助手.ttg
# 在交互式编辑器中配置基因位点

# 3. 验证创始印记
prometheus audit ~/.hermes/seed-vault/写作助手.ttg

# 4. 查看完整DNA
prometheus view ~/.hermes/seed-vault/写作助手.ttg
```

### 工作流二：基因编辑与扩展

```bash
# 1. 查看现有基因
prometheus genes ~/.hermes/seed-vault/写作助手.ttg

# 2. 查看可用基因
prometheus library

# 3. 插入新基因
prometheus insert ~/.hermes/seed-vault/写作助手.ttg G100-writer

# 4. 健康审计
prometheus health ~/.hermes/seed-vault/写作助手.ttg

# 5. 保存快照
prometheus snapshot save "插入写作基因后" ~/.hermes/seed-vault/写作助手.ttg
```

### 工作流三：锻造与筛选

```bash
# 1. 锻造变异体
prometheus forge ~/.hermes/seed-vault/写作助手.ttg \
  --genes G100,G101,G102 \
  --mode power_set \
  --max 50

# 2. 筛选优胜者
prometheus sieve ~/.hermes/gene-lab/batch_20260430/ 5

# 3. 提升为正式种子
prometheus promote ~/.hermes/gene-lab/batch_20260430/variant_003.ttg "写作大师"

# 4. 苗圃验证
prometheus nursery ~/.hermes/seed-vault/写作大师.ttg
```

### 工作流四：种子融合

```bash
# 1. 分析融合兼容性
prometheus fusion ~/.hermes/seed-vault/skill_a.ttg ~/.hermes/seed-vault/skill_b.ttg

# 2. 拆解外来技能
prometheus extract ~/external_framework.md

# 3. 插入拆解出的基因
prometheus insert ~/.hermes/seed-vault/skill_a.ttg G100-writer

# 4. 验证
prometheus health ~/.hermes/seed-vault/skill_a.ttg
```

### 工作流五：从外部技能导入

```bash
# 1. 拆解外部技能文档
prometheus extract ~/my_external_skill.md

# 2. 创建新种子
prometheus create "外部技能"

# 3. 插入拆解出的基因
prometheus insert ~/.hermes/seed-vault/外部技能.ttg G100-writer

# 4. 健康审计
prometheus health ~/.hermes/seed-vault/外部技能.ttg

# 5. 标签词典验证
prometheus lexicon ~/.hermes/seed-vault/外部技能.ttg
```

---

## 安全机制

### 创始铭刻保护

- 每个种子由 `inject_founder_chronicle()` 自动注入 7 个永恒标签
- 这些标签在 `tag_lexicon` 中标记为 `weight: "eternal"`
- `audit` 命令验证标签完整性（7/7）
- 缺少创始印记的种子风险等级为 HIGH

### 碳基依赖级

- `carbon_bonded: true` 的基因完全不可编辑/删除
- 碳基标签不可删除（除非使用 `--force`）
- 删除碳基基因会导致种子失效

### 自动快照

- 进入交互式编辑器时自动创建快照
- 所有操作记录在 `prometheus.log` 中
- 快照支持完整回滚

### 操作日志

所有操作自动记录到 `~/.hermes/tools/prometheus/prometheus.log`：
```json
{"timestamp": "2026-04-30T12:00:00", "action": "cli_invoke", "detail": "view path"}
{"timestamp": "2026-04-30T12:00:01", "action": "edit_save", "detail": "path"}
```

### 风险等级

| 等级 | 条件 |
|------|------|
| `LOW` | 创始标签完整 + 永恒标签≥7 + 创始印记存在 |
| `HIGH` | 任一条件不满足 |

---

## 常见问题

### Q: 如何备份种子？

```bash
prometheus snapshot save "备份说明" ~/.hermes/seed-vault/my_skill.ttg
```

或使用 vault 查看所有种子后手动复制。

### Q: 如何恢复误删除的基因？

```bash
# 查看快照列表
prometheus snapshot list

# 恢复到编辑前的状态
prometheus snapshot restore <快照ID>
```

### Q: 基因库中的标准基因有哪些？

```bash
prometheus library
```

标准基因（9个）由 `gene_analyzer.py` 定义，包括：
- G001-parser（解析器）
- G002-analyzer（分析器）
- G003-tracker（追踪器）
- G004-packer（打包器）
- G005-genealogist（族谱学家）
- G006-gardener（园丁/自管理者）
- G007-dormancy（休眠守卫）
- G008-auditor（审计员）

### Q: 如何检测种子是否被篡改？

```bash
prometheus audit ~/.hermes/seed-vault/my_skill.ttg
```

如果显示"疑似基因篡改"或"外来种子"，说明创始印记可能被移除。

### Q: 锻造和编辑有什么区别？

- **编辑**（edit）：直接修改单个种子的基因
- **锻造**（forge）：基于一个亲代种子，批量生成多个变体
- 锻造产出需要通过 **sieve** 筛选后才能 **promote** 为正式种子

### Q: .ttg 文件可以手动编辑吗？

可以。`.ttg` 是标准 Markdown 文件，YAML 代码块可用任何文本编辑器修改。但建议使用 `prometheus edit` 以确保安全快照和操作日志。

### Q: 如何批量管理种子？

```bash
# 查看所有种子
prometheus vault

# 批量健康审计（API）
from prometheus import api
for seed in api.vault():
    result = api.health(seed['path'])
    print(seed['name'], result)
```

---

## 版本信息

- **框架版本：** 1.0
- **创始人：** Audrey · 001X
- **诞生日期：** 2026-04-29
- **框架文件：** prometheus.py (2101行), gene_analyzer.py (612行), geneforge.py, genebank.py, nursery.py
- **祖谱来源：** TTG@L1-G1-ORIGIN-FB1F3A11 · 诸技之母

---

*此手册由普罗米修斯框架文档系统生成 · Audrey · 001X 的创始印记*
*「播下即是传承，展开即是世界」*
