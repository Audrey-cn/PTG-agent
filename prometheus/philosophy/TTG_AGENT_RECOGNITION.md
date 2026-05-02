# TTG协议Agent识别优化设计

## 设计目标

为不同智能水平的Agent提供友好的TTG协议识别机制：

- **聪明Agent**：通过文件头魔数和内部结构快速识别
- **笨Agent**：通过文件名提示和元数据字段提供识别线索
- **所有Agent**：提供多层次的识别路径和明确的指导

## 多层次识别机制

### 第一层：文件名提示策略

#### 种子文件命名优化

```python
# 原始命名：seed_1234567890_abc123.ttg
# 优化命名：seed_1234567890_abc123.ttg.txt

# 或者使用更友好的命名：
# seed_1234567890_abc123.readable.ttg
# seed_1234567890_abc123.ttg.readme
```

**实现方案：**
1. 为TTG文件创建配套的`.readme`文件
2. 在文件名中添加提示性后缀
3. 提供友好的别名文件

#### 具体命名策略

```python
# 主要文件（标准格式）
seed_1234567890_abc123.ttg

# 辅助文件（识别提示）
seed_1234567890_abc123.ttg.readme  # 协议说明文件
seed_1234567890_abc123.preview.json  # 预览JSON文件
```

### 第二层：文件头魔数优化

#### 当前魔数设计
```python
# 通用TTG文件：b"TTGC" (TTG Compressed)
# 种子TTG文件：b"TTGS" (TTG Seed)
```

#### 优化魔数设计
```python
# 使用更易识别的魔数
# 通用TTG文件：b"TTG1" (TTG Version 1)
# 种子TTG文件：b"SEED" (Seed TTG)

# 或者使用ASCII可读魔数
# 通用TTG文件：b"TTG\x01" (TTG + 版本号)
# 种子TTG文件：b"SEED\x01" (SEED + 版本号)
```

### 第三层：元数据字段增强

#### 增强的文件头元数据

```python
@dataclass
class TTGSeedHeader:
    """优化的种子TTG文件头"""
    magic: bytes = b"SEED"       # 易识别魔数
    version: int = 1
    file_type: str = "seed"
    entity_type: str = ""
    quality_level: str = "standard"
    
    # 增强的识别字段
    protocol_name: str = "TTG"   # 协议名称
    readable_hint: str = "This is a TTG format seed file. Use TTGProtocolTool to parse."
    file_format: str = "binary"  # 文件格式提示
    content_type: str = "seed_data"  # 内容类型
    
    protocol_layers: List[TTGProtocolLayer] = field(default_factory=list)
    compression: TTGCompressionAlgorithm = TTGCompressionAlgorithm.DEFLATE
    encoding_mode: TTGEncodingMode = TTGEncodingMode.STANDARD
    checksum: bytes = b""
    metadata: Dict[str, Any] = field(default_factory=dict)
```

## 具体实现方案

### 1. 文件名提示实现

```python
class SeedNamingStrategy:
    """种子文件命名策略"""
    
    @staticmethod
    def get_primary_filename(seed_id: str) -> str:
        """主文件名（标准格式）"""
        return f"{seed_id}.ttg"
    
    @staticmethod
    def get_readme_filename(seed_id: str) -> str:
        """说明文件名"""
        return f"{seed_id}.ttg.readme"
    
    @staticmethod
    def get_preview_filename(seed_id: str) -> str:
        """预览文件名"""
        return f"{seed_id}.preview.json"
    
    @staticmethod
    def get_alias_filename(seed_id: str) -> str:
        """别名文件名（为笨Agent提供）"""
        return f"README_{seed_id}.txt"
```

### 2. 魔数优化实现

```python
class TTGMagicNumbers:
    """TTG魔数定义"""
    
    # 优化后的魔数
    TTG_GENERIC = b"TTG\x01"     # TTG + 版本1
    TTG_SEED = b"SEED\x01"       # SEED + 版本1
    
    # 魔数映射表
    MAGIC_MAPPING = {
        b"TTG\x01": "TTG通用格式",
        b"SEED\x01": "TTG种子格式",
        b"TTGC": "TTG压缩格式（旧版）",
        b"TTGS": "TTG种子格式（旧版）"
    }
    
    @classmethod
    def get_format_description(cls, magic: bytes) -> str:
        """根据魔数获取格式描述"""
        return cls.MAGIC_MAPPING.get(magic, "未知格式")
    
    @classmethod
    def is_ttg_file(cls, magic: bytes) -> bool:
        """判断是否为TTG文件"""
        return magic in [cls.TTG_GENERIC, cls.TTG_SEED, b"TTGC", b"TTGS"]
```

### 3. 元数据增强实现

```python
class TTGRecognitionHelper:
    """TTG识别辅助工具"""
    
    @staticmethod
    def create_enhanced_header(seed_data: Dict[str, Any], 
                             entity_type: str, 
                             target_quality: str) -> TTGSeedHeader:
        """创建增强的TTG文件头"""
        
        return TTGSeedHeader(
            magic=TTGMagicNumbers.TTG_SEED,
            version=1,
            file_type="seed",
            entity_type=entity_type,
            quality_level=target_quality,
            
            # 增强的识别字段
            protocol_name="TTG",
            readable_hint=(
                "This is a TTG format seed file. "
                "It contains encoded seed data with genetic information. "
                "Use TTGProtocolTool.parse_seed_ttg() to decode."
            ),
            file_format="binary_with_json_header",
            content_type="seed_data_with_genes",
            
            protocol_layers=SEED_PROTOCOL_STACK,
            compression=TTGCompressionAlgorithm.DEFLATE,
            encoding_mode=TTGEncodingMode.STANDARD,
            metadata={
                "creation_tool": "SeedManager",
                "protocol_version": "1.0",
                "recommended_tools": ["TTGProtocolTool", "SeedManager"],
                "file_purpose": "seed_storage",
                "content_description": f"{entity_type} seed with genetic encoding"
            }
        )
    
    @staticmethod
    def generate_readme_file(seed_id: str, seed_data: Dict[str, Any]) -> str:
        """生成说明文件内容"""
        
        readme_content = f"""# TTG种子文件说明

## 文件信息
- 种子ID: {seed_id}
- 实体类型: {seed_data.get('entity_type', 'unknown')}
- 质量等级: {seed_data.get('target_quality', 'standard')}
- 创建时间: {seed_data.get('created_at', 'unknown')}

## 文件格式
这是一个TTG（Tiny Text Gene）格式的种子文件。TTG是我们自创的协议标准，用于高效存储基因编码的种子数据。

## 如何读取

### 方法1：使用TTG协议工具（推荐）
```python
from prometheus.philosophy.tools.ttg_protocol_tool import TTGProtocolTool

tool = TTGProtocolTool()
result = tool.parse_seed_ttg(ttg_data)
seed_data = result.decoded_data
```

### 方法2：使用种子管理工具
```python
from prometheus.philosophy.tools.seed_manager import SeedManager

manager = SeedManager()
# 工具会自动识别TTG格式
```

### 方法3：手动解析（高级）
文件结构：TTG文件头（JSON） + 压缩数据
魔数：SEED\\x01 (TTG种子格式)

## 内容概述
这个种子文件包含以下信息：
- 基因编码数据
- 实体元数据
- 进化历史记录
- 质量评估信息

如需更多帮助，请参考TTG协议文档。
"""
        
        return readme_content
```

### 4. 预览文件生成

```python
class PreviewGenerator:
    """预览文件生成器"""
    
    @staticmethod
    def generate_preview(seed_data: Dict[str, Any]) -> Dict[str, Any]:
        """生成种子预览数据"""
        
        return {
            "seed_id": seed_data.get("seed_id"),
            "entity_type": seed_data.get("entity_type"),
            "target_quality": seed_data.get("target_quality"),
            "created_at": seed_data.get("created_at"),
            "gene_count": seed_data.get("metadata", {}).get("gene_count", 0),
            "health_score": seed_data.get("genes", {}).get("health_score", 0.0),
            "file_purpose": "seed_data_storage",
            "recommended_action": "parse_with_ttg_tool",
            "content_preview": {
                "has_genes": "genes" in seed_data,
                "has_metadata": "metadata" in seed_data,
                "has_evolution": "evolution_history" in seed_data
            }
        }
```

## Agent识别指南

### 聪明Agent识别路径

```python
def smart_agent_recognize_ttg(file_path: Path) -> bool:
    """聪明Agent识别TTG文件"""
    
    # 1. 检查文件扩展名
    if file_path.suffix == '.ttg':
        return True
    
    # 2. 读取文件头魔数
    with open(file_path, 'rb') as f:
        magic = f.read(4)
        if TTGMagicNumbers.is_ttg_file(magic):
            return True
    
    # 3. 检查配套文件
    readme_file = file_path.with_suffix('.ttg.readme')
    if readme_file.exists():
        return True
    
    return False
```

### 笨Agent识别路径

```python
def simple_agent_recognize_ttg(file_path: Path) -> bool:
    """简单Agent识别TTG文件"""
    
    # 1. 检查明显的提示文件
    hint_files = [
        file_path.with_suffix('.ttg.readme'),
        file_path.with_suffix('.preview.json'),
        file_path.parent / f"README_{file_path.stem}.txt"
    ]
    
    for hint_file in hint_files:
        if hint_file.exists():
            return True
    
    # 2. 检查文件名中的提示
    filename = file_path.name.lower()
    if any(hint in filename for hint in ['.ttg', 'seed_', 'readable']):
        return True
    
    # 3. 尝试读取文件开头（简单文本检查）
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            first_lines = ''.join([next(f) for _ in range(3)])
            if any(keyword in first_lines for keyword in 
                   ['TTG', 'SEED', 'seed', 'protocol']):
                return True
    except:
        pass
    
    return False
```

## 集成到种子管理工具

### 修改种子保存逻辑

```python
class EnhancedSeedManager(SeedManager):
    """增强的种子管理器"""
    
    def _save_ttg_seed_file(self, seed_data: Dict[str, Any], entity_type: str) -> Path:
        """保存TTG格式种子文件（增强版）"""
        
        seed_id = seed_data["seed_id"]
        
        # 1. 生成主TTG文件
        primary_path = self._save_primary_ttg_file(seed_data, entity_type)
        
        # 2. 生成辅助文件
        self._generate_support_files(seed_id, seed_data)
        
        return primary_path
    
    def _save_primary_ttg_file(self, seed_data: Dict[str, Any], entity_type: str) -> Path:
        """保存主TTG文件"""
        seed_id = seed_data["seed_id"]
        seed_filename = SeedNamingStrategy.get_primary_filename(seed_id)
        seed_path = self.seeds_dir / entity_type / seed_filename
        
        # 使用增强的TTG协议工具
        ttg_tool = TTGProtocolTool()
        ttg_result = ttg_tool.create_seed_ttg(
            seed_data, entity_type, seed_data.get("target_quality", "standard")
        )
        
        with open(seed_path, 'wb') as f:
            f.write(ttg_result.ttg_data)
        
        return seed_path
    
    def _generate_support_files(self, seed_id: str, seed_data: Dict[str, Any]):
        """生成辅助文件"""
        entity_type = seed_data.get("entity_type", "unknown")
        entity_dir = self.seeds_dir / entity_type
        
        # 1. 生成说明文件
        readme_content = TTGRecognitionHelper.generate_readme_file(seed_id, seed_data)
        readme_path = entity_dir / SeedNamingStrategy.get_readme_filename(seed_id)
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        
        # 2. 生成预览文件
        preview_data = PreviewGenerator.generate_preview(seed_data)
        preview_path = entity_dir / SeedNamingStrategy.get_preview_filename(seed_id)
        with open(preview_path, 'w', encoding='utf-8') as f:
            json.dump(preview_data, f, ensure_ascii=False, indent=2)
        
        # 3. 生成别名文件
        alias_content = f"种子文件: {seed_id}.ttg\n使用TTG工具解析此文件。"
        alias_path = entity_dir / SeedNamingStrategy.get_alias_filename(seed_id)
        with open(alias_path, 'w', encoding='utf-8') as f:
            f.write(alias_content)
```

## 实施计划

### 第一阶段：基础识别优化
1. 实现文件名提示策略
2. 优化魔数设计
3. 添加基础元数据字段

### 第二阶段：辅助文件生成
1. 实现说明文件生成
2. 实现预览文件生成
3. 实现别名文件生成

### 第三阶段：Agent识别指南
1. 创建聪明Agent识别路径
2. 创建笨Agent识别路径
3. 提供识别工具函数

## 总结

通过这个多层次的识别机制，我们为不同智能水平的Agent提供了友好的TTG协议识别方案：

1. **文件名提示**：通过文件命名提供直观线索
2. **魔数优化**：使用易识别的魔数设计
3. **元数据增强**：在文件头中添加识别信息
4. **辅助文件**：生成配套的说明和预览文件
5. **识别指南**：提供不同层次的识别路径

这样设计确保了：
- 聪明Agent可以快速准确地识别TTG文件
- 笨Agent也能通过明显的提示识别文件类型
- 所有Agent都能获得足够的识别线索和指导
- 保持了TTG协议的技术先进性和简洁性