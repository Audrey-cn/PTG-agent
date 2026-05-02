# 种子管理工具使用指南

## 概述

种子管理工具是基于现有基因系统的种子管理工具，支持将各种实体（文件、项目、技能等）转换为携带基因的种子，实现知识的标准化、可进化性和代际传递。

## 安装与配置

### 前置条件

确保已安装普罗米修斯框架的所有依赖：

```bash
# 在普罗米修斯项目根目录
pip install -r requirements.txt
```

### 工具位置

种子管理工具位于：
```
prometheus/philosophy/tools/seed_manager.py
```

## 基本使用

### 命令行使用

#### 创建种子

```bash
# 创建TTG格式文件种子（默认）
python prometheus/philosophy/tools/seed_manager.py create /path/to/file.txt file standard

# 创建JSON格式文件种子（兼容性）
python prometheus/philosophy/tools/seed_manager.py create /path/to/file.txt file standard json

# 创建TTG格式项目种子
python prometheus/philosophy/tools/seed_manager.py create /path/to/project project premium

# 创建TTG格式技能种子
python prometheus/philosophy/tools/seed_manager.py create '{"skill": "python_development"}' skill excellent
```

**参数说明：**
- `create`: 创建种子命令
- `<entity>`: 要种子化的实体（文件路径、项目路径、技能数据等）
- `<entity_type>`: 实体类型（file/project/skill/concept/workflow/dataset/model）
- `[quality]`: 目标质量等级（basic/standard/premium/excellent），默认为standard
- `[format]`: 输出格式（ttg/json），默认为ttg

#### 验证种子

```bash
# 验证种子文件
python prometheus/philosophy/tools/seed_manager.py validate /path/to/seed.seed.json
```

#### 列出种子

```bash
# 列出所有种子
python prometheus/philosophy/tools/seed_manager.py list

# 列出特定类型的种子
python prometheus/philosophy/tools/seed_manager.py list file
```

### Python API使用

#### 基本示例

```python
from pathlib import Path
from prometheus.philosophy.tools.seed_manager import SeedManager

# 创建种子管理器
seed_manager = SeedManager(Path.home() / ".prometheus")

# 创建文件种子
seed_data = seed_manager.create_seed("/path/to/file.txt", "file", "standard")
print(f"种子创建成功: {seed_data['seed_id']}")

# 验证种子
validation_result = seed_manager.validate_seed(seed_data)
print(f"种子验证结果: {validation_result.is_valid}")
print(f"健康度评分: {validation_result.health_score:.2f}")

# 列出所有种子
seeds = seed_manager.list_seeds()
for seed in seeds:
    print(f"{seed['seed_id']} - {seed['entity_type']}")
```

#### 高级示例

```python
# 创建项目种子（深度优化）
project_seed = seed_manager.create_seed(
    "/path/to/project", 
    "project", 
    "premium",
    context={"optimization_level": "deep"}
)

# 批量创建种子
entities = [
    ("file1.txt", "file", "basic"),
    ("file2.py", "file", "standard"),
    ("project/", "project", "premium")
]

for entity, entity_type, quality in entities:
    seed_data = seed_manager.create_seed(entity, entity_type, quality)
    print(f"创建种子: {seed_data['seed_id']}")
```

## 实体类型支持

### 文件实体（file）

支持将单个文件转换为种子：

```python
# 文本文件
seed_data = seed_manager.create_seed("document.txt", "file", "standard")

# 代码文件
seed_data = seed_manager.create_seed("script.py", "file", "premium")

# 配置文件
seed_data = seed_manager.create_seed("config.yaml", "file", "basic")
```

### 项目实体（project）

支持将整个项目转换为种子：

```python
# Python项目
seed_data = seed_manager.create_seed("/path/to/python_project", "project", "standard")

# JavaScript项目
seed_data = seed_manager.create_seed("/path/to/js_project", "project", "premium")

# 数据科学项目
seed_data = seed_manager.create_seed("/path/to/ds_project", "project", "excellent")
```

### 技能实体（skill）

支持将技能定义转换为种子：

```python
# 编程技能
skill_data = {
    "skill": "python_development",
    "level": "advanced",
    "technologies": ["flask", "django", "pandas"]
}
seed_data = seed_manager.create_seed(skill_data, "skill", "standard")

# 数据分析技能
skill_data = {
    "skill": "data_analysis",
    "tools": ["pandas", "numpy", "matplotlib"],
    "domains": ["finance", "healthcare"]
}
seed_data = seed_manager.create_seed(skill_data, "skill", "premium")
```

### 概念实体（concept）

支持将抽象概念转换为种子：

```python
# 设计模式概念
concept_data = {
    "concept": "observer_pattern",
    "category": "behavioral",
    "description": "定义对象间的一对多依赖关系"
}
seed_data = seed_manager.create_seed(concept_data, "concept", "standard")
```

### 工作流实体（workflow）

支持将工作流程转换为种子：

```python
# 数据处理工作流
workflow_data = {
    "workflow": "data_processing",
    "steps": ["extract", "transform", "load"],
    "tools": ["pandas", "sqlalchemy"]
}
seed_data = seed_manager.create_seed(workflow_data, "workflow", "premium")
```

## 质量等级

### 基础质量（basic）

只包含核心基因，适用于简单场景：

- 基因数量：最少
- 优化程度：基础
- 适用场景：快速原型、简单实体

### 标准质量（standard）

适度的基因优化，适用于大多数场景：

- 基因数量：适中
- 优化程度：标准
- 适用场景：生产环境、一般实体

### 优质质量（premium）

深度的基因优化，适用于重要场景：

- 基因数量：较多
- 优化程度：深度
- 适用场景：关键系统、重要实体

### 优秀质量（excellent）

极致的基因优化，适用于核心场景：

- 基因数量：最多
- 优化程度：极致
- 适用场景：核心系统、关键实体

## 种子文件格式

### TTG格式种子文件

种子文件采用TTG格式（.ttg后缀），这是普罗米修斯框架自创的协议标准。TTG格式提供更好的压缩效率和扩展性。

#### TTG文件结构

TTG文件包含完整的协议栈：
```
TTG文件 = TTG文件头 + 压缩数据
压缩数据 = 协议层编码(种子数据)
种子数据 = 基因编码(实体数据)
```

#### 种子专用协议栈

种子文件使用专门的协议栈：
- **结构层**：重用Layer1编解码器，提供基础结构编码
- **语义层**：重用Layer2编解码器，提供语义压缩
- **种子基因层**：种子特有的基因编码
- **种子进化层**：进化历史记录

### JSON格式种子文件（兼容性）

为保持向后兼容性，也支持JSON格式种子文件：

```json
{
  "seed_id": "seed_1234567890_abc123",
  "entity_type": "file",
  "target_quality": "standard",
  "created_at": "2026-05-02T10:30:00",
  "genes": {
    "core_genes": [...],
    "optimized_genes": [...],
    "metadata": {...}
  },
  "metadata": {
    "original_entity": "/path/to/file.txt",
    "gene_count": 25,
    "compression_ratio": 0.85
  },
  "file_info": {
    "path": "/path/to/file.txt",
    "size": 1024
  }
}
```

### 种子文件命名

#### TTG格式命名规则：
```
{seed_id}.ttg
```
示例：`seed_1234567890_abc123.ttg`

#### JSON格式命名规则：
```
{seed_id}.seed.json
```
示例：`seed_1234567890_abc123.seed.json`

## 存储位置

### 种子存储目录

种子文件存储在普罗米修斯主目录下的seeds子目录中：
```
~/.prometheus/seeds/
```

### 按类型分类存储

种子文件按实体类型分类存储：
```
~/.prometheus/seeds/
├── files/           # 文件种子
├── projects/        # 项目种子
├── skills/          # 技能种子
├── concepts/        # 概念种子
├── workflows/       # 工作流种子
├── datasets/        # 数据集种子
└── models/          # 模型种子
```

## 验证与健康检查

### 种子验证

种子管理工具提供完整的验证功能：

```python
# 验证种子
validation_result = seed_manager.validate_seed(seed_data)

if validation_result.is_valid:
    print("种子验证通过")
    print(f"健康度: {validation_result.health_score:.2f}")
else:
    print("种子验证失败")
    for warning in validation_result.warnings:
        print(f"警告: {warning}")
    for recommendation in validation_result.recommendations:
        print(f"建议: {recommendation}")
```

### 健康度评分

健康度评分基于以下因素：

- **基因完整性**：核心基因是否完整
- **基因健康度**：基因是否存在问题
- **结构合理性**：种子结构是否合理
- **依赖关系**：依赖关系是否清晰

评分范围：0.0 - 1.0，越高表示越健康

## 高级功能

### 批量处理

支持批量创建和管理种子：

```python
# 批量创建种子
entities_to_seed = [
    ("file1.txt", "file", "standard"),
    ("file2.py", "file", "premium"),
    ("project/", "project", "excellent")
]

for entity, entity_type, quality in entities_to_seed:
    seed_data = seed_manager.create_seed(entity, entity_type, quality)
    print(f"创建种子: {seed_data['seed_id']}")

# 批量验证种子
seed_files = seed_manager.list_seeds("file")
for seed_file in seed_files:
    validation_result = seed_manager.validate_seed(seed_file)
    print(f"{seed_file['seed_id']}: {validation_result.health_score:.2f}")
```

### 自定义基因提取

支持自定义基因提取策略：

```python
from prometheus.philosophy.tools.seed_manager import SeedManager

class CustomSeedManager(SeedManager):
    def _custom_gene_extraction(self, entity, entity_type):
        """自定义基因提取逻辑"""
        # 实现自定义基因提取
        custom_genes = self._extract_custom_genes(entity)
        return custom_genes

# 使用自定义种子管理器
custom_manager = CustomSeedManager(Path.home() / ".prometheus")
seed_data = custom_manager.create_seed(entity, entity_type, quality)
```

### 种子进化

种子支持进化功能：

```python
# 获取种子进化历史
evolution_history = seed_data.get("evolution_history", [])
for evolution in evolution_history:
    print(f"第{evolution['generation']}代: {evolution['fitness']}")

# 种子变异
mutated_seed = seed_manager.mutate_seed(seed_data, mutation_rate=0.01)
```

## 性能优化

### 内存优化

对于大型实体，建议使用流式处理：

```python
# 流式处理大文件
with open("large_file.txt", "r") as f:
    # 分块处理
    for chunk in read_in_chunks(f):
        seed_data = seed_manager.create_seed(chunk, "file_chunk", "standard")
```

### 缓存机制

种子管理工具支持缓存机制：

```python
# 启用缓存
seed_manager.enable_cache()

# 创建种子（使用缓存）
seed_data = seed_manager.create_seed(entity, entity_type, quality)

# 清除缓存
seed_manager.clear_cache()
```

## 错误处理

### 常见错误

#### 实体类型错误

```python
try:
    seed_data = seed_manager.create_seed(entity, "invalid_type", "standard")
except InvalidEntityTypeError as e:
    print(f"无效的实体类型: {e}")
```

#### 文件不存在错误

```python
try:
    seed_data = seed_manager.create_seed("nonexistent.txt", "file", "standard")
except FileNotFoundError as e:
    print(f"文件不存在: {e}")
```

#### 种子验证错误

```python
try:
    validation_result = seed_manager.validate_seed(invalid_seed_data)
    if not validation_result.is_valid:
        for warning in validation_result.warnings:
            print(f"警告: {warning}")
except SeedValidationError as e:
    print(f"种子验证错误: {e}")
```

### 错误恢复

种子管理工具提供错误恢复机制：

```python
# 尝试创建种子，失败时使用备用策略
try:
    seed_data = seed_manager.create_seed(entity, entity_type, quality)
except Exception as e:
    print(f"创建种子失败: {e}")
    # 使用基础质量重试
    seed_data = seed_manager.create_seed(entity, entity_type, "basic")
```

## 最佳实践

### 1. 选择合适的质量等级

根据实体重要性选择质量等级：

- **核心系统组件**：使用excellent质量
- **一般生产代码**：使用premium或standard质量
- **原型和测试代码**：使用basic质量

### 2. 定期验证种子

定期验证种子的健康度：

```python
# 定期健康检查
seeds = seed_manager.list_seeds()
for seed in seeds:
    validation_result = seed_manager.validate_seed(seed)
    if validation_result.health_score < 0.7:
        print(f"种子 {seed['seed_id']} 健康度较低，建议优化")
```

### 3. 备份种子文件

定期备份种子文件：

```bash
# 备份种子目录
cp -r ~/.prometheus/seeds/ /backup/location/seeds_backup/
```

### 4. 版本控制

将重要的种子文件纳入版本控制：

```bash
# 添加种子文件到Git
git add ~/.prometheus/seeds/important_seed.seed.json
git commit -m "Add important seed"
```

## 总结

种子管理工具为知识管理提供了强大的标准化能力：

- **标准化表示**：统一的种子格式
- **基因优化**：基于基因系统的优化
- **健康检查**：完整的验证机制
- **进化支持**：支持种子进化
- **类型丰富**：支持多种实体类型

通过合理使用种子管理工具，可以实现知识的标准化管理和持续进化。