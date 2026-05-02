# TTG协议重新设计规范

## 设计原则

### 核心原则
1. **统一格式**：所有种子文件必须使用TTG格式（.ttg后缀）
2. **协议分层**：TTG协议包含完整的协议栈，JSON只是其中一种编码模式
3. **向后兼容**：支持从现有JSON格式平滑迁移到TTG格式

### 文件格式规范

#### 种子文件命名
```
{seed_id}.ttg
```
示例：`seed_1234567890_abc123.ttg`

#### TTG文件结构
```
TTG文件 = TTG文件头 + 压缩数据
压缩数据 = 协议层编码(种子数据)
种子数据 = 基因编码(实体数据)
```

## TTG协议栈重新设计

### 协议层级定义

```python
class TTGProtocolLayer(Enum):
    """TTG协议层级 - 重新设计"""
    # 基础层级（重用现有功能）
    STRUCTURAL = "structural"    # 结构层：重用Layer1编解码器
    SEMANTIC = "semantic"        # 语义层：重用Layer2编解码器
    
    # 种子专用层级（新增）
    SEED_GENETIC = "seed_genetic"  # 种子基因层：种子特有的基因编码
    SEED_EVOLUTION = "seed_evolution" # 种子进化层：进化历史记录
    
    # 高级层级（概念性）
    CONTEXTUAL = "contextual"    # 上下文层
    QUANTUM = "quantum"          # 量子层
```

### 种子专用协议栈

对于种子文件，使用专门的协议栈：

```python
# 种子文件的默认协议栈
SEED_PROTOCOL_STACK = [
    TTGProtocolLayer.STRUCTURAL,    # 基础结构编码
    TTGProtocolLayer.SEMANTIC,      # 语义压缩
    TTGProtocolLayer.SEED_GENETIC,  # 种子基因编码
    TTGProtocolLayer.SEED_EVOLUTION # 种子进化记录
]
```

## 种子TTG格式详细规范

### TTG文件头规范

```python
@dataclass
class TTGSeedHeader:
    """种子TTG文件头"""
    magic: bytes = b"TTGS"       # 魔数：TTG Seed（区别于通用的TTGC）
    version: int = 1             # 版本号
    file_type: str = "seed"      # 文件类型：固定为"seed"
    entity_type: str = ""        # 实体类型：file/project/skill等
    quality_level: str = "standard" # 质量等级
    protocol_layers: List[TTGProtocolLayer] = field(default_factory=list)
    compression: TTGCompressionAlgorithm = TTGCompressionAlgorithm.DEFLATE
    encoding_mode: TTGEncodingMode = TTGEncodingMode.STANDARD
    checksum: bytes = b""
    metadata: Dict[str, Any] = field(default_factory=dict)
```

### 种子数据编码规范

```python
@dataclass 
class SeedTTGData:
    """种子TTG数据格式"""
    # 种子基本信息
    seed_id: str
    entity_type: str
    target_quality: str
    created_at: str
    
    # 基因数据（经过TTG协议编码）
    genetic_data: bytes  # 经过协议栈编码的基因数据
    
    # 元数据
    metadata: Dict[str, Any]
    
    # 进化历史
    evolution_history: List[Dict[str, Any]] = field(default_factory=list)
```

## 实现方案

### 1. 修改种子管理工具

```python
class SeedManager:
    def create_seed(self, entity, entity_type, target_quality="standard"):
        """创建TTG格式的种子"""
        
        # 1. 生成种子数据（JSON格式）
        seed_json_data = self._build_seed_json_data(entity, entity_type, target_quality)
        
        # 2. 应用TTG协议栈编码
        ttg_tool = TTGProtocolTool()
        ttg_result = ttg_tool.create_ttg_file(
            seed_json_data,
            protocol_layers=SEED_PROTOCOL_STACK,
            file_type="seed"
        )
        
        # 3. 保存为.ttg文件
        seed_filename = f"{seed_json_data['seed_id']}.ttg"
        seed_path = self.seeds_dir / entity_type / seed_filename
        
        with open(seed_path, 'wb') as f:
            f.write(ttg_result.ttg_data)
        
        return ttg_result
```

### 2. 增强TTG协议工具

```python
class TTGProtocolTool:
    def create_seed_ttg(self, seed_data, entity_type, target_quality="standard"):
        """专门创建种子TTG文件"""
        
        # 使用种子专用协议栈
        return self.create_ttg_file(
            seed_data,
            protocol_layers=SEED_PROTOCOL_STACK,
            file_type="seed",
            custom_options={
                "entity_type": entity_type,
                "quality_level": target_quality
            }
        )
    
    def parse_seed_ttg(self, ttg_data):
        """解析种子TTG文件"""
        result = self.parse_ttg_file(ttg_data)
        
        # 验证是否为种子文件
        if result.metadata.get("file_type") != "seed":
            raise ValueError("不是有效的种子TTG文件")
        
        return result
```

### 3. 格式转换工具

```python
class SeedFormatConverter:
    """种子格式转换工具"""
    
    def json_to_ttg(self, json_seed_file, output_ttg_file):
        """将JSON格式种子转换为TTG格式"""
        with open(json_seed_file, 'r') as f:
            seed_data = json.load(f)
        
        ttg_tool = TTGProtocolTool()
        result = ttg_tool.create_seed_ttg(
            seed_data,
            seed_data.get("entity_type", "unknown"),
            seed_data.get("target_quality", "standard")
        )
        
        with open(output_ttg_file, 'wb') as f:
            f.write(result.ttg_data)
    
    def ttg_to_json(self, ttg_seed_file, output_json_file):
        """将TTG格式种子转换为JSON格式（用于兼容性）"""
        with open(ttg_seed_file, 'rb') as f:
            ttg_data = f.read()
        
        ttg_tool = TTGProtocolTool()
        result = ttg_tool.parse_seed_ttg(ttg_data)
        
        with open(output_json_file, 'w') as f:
            json.dump(result.decoded_data, f, indent=2)
```

## 迁移策略

### 阶段1：双格式支持（过渡期）
- 种子管理工具同时支持JSON和TTG格式
- 新创建的种子默认使用TTG格式
- 提供格式转换工具

### 阶段2：TTG格式为主
- 所有新种子必须使用TTG格式
- 逐步迁移现有JSON格式种子
- 工具链全面支持TTG格式

### 阶段3：TTG格式唯一
- 移除JSON格式支持
- 所有种子文件统一为TTG格式
- 优化TTG协议性能

## 技术优势

### 1. 统一的协议标准
- 所有种子文件使用统一的TTG格式
- 便于工具链的统一处理
- 提高系统的整体一致性

### 2. 更好的压缩效率
- TTG协议栈提供多层压缩
- 相比纯JSON有更好的压缩比
- 支持多种压缩算法

### 3. 更强的扩展性
- 协议栈支持按需扩展
- 支持种子特有的基因编码层
- 便于未来功能扩展

### 4. 更好的错误处理
- TTG文件头包含完整的元数据
- 支持校验和验证
- 提供更好的错误恢复机制

## 实现计划

### 立即实施
1. 重新设计TTG协议栈，添加种子专用层级
2. 修改种子管理工具，支持TTG格式输出
3. 增强TTG协议工具，支持种子文件处理

### 短期目标
1. 实现格式转换工具
2. 更新相关文档
3. 进行兼容性测试

### 长期目标
1. 逐步迁移到纯TTG格式
2. 优化TTG协议性能
3. 扩展TTG协议功能

## 总结

通过重新设计TTG协议，我们实现了：

1. **格式统一**：所有种子文件使用TTG格式
2. **协议完整**：完整的TTG协议栈支持
3. **平滑迁移**：提供从JSON到TTG的迁移路径
4. **技术优势**：更好的压缩效率、扩展性和错误处理

这一设计确保了TTG协议作为我们自创标准的技术先进性和统一性。