# TTG协议单文件识别优化设计

## 设计原则

### 核心原则：单文件传输整个生命
- **自包含性**：一个TTG文件包含所有必要信息
- **完整性**：文件本身提供足够的识别线索
- **简洁性**：不依赖外部文件或复杂结构

### 设计目标
- **聪明Agent**：通过文件内部结构快速识别
- **笨Agent**：通过文件开头提供明显的识别线索
- **所有Agent**：在单文件内获得足够的识别信息

## 单文件内识别机制设计

### 1. 文件开头设计优化

#### 当前设计问题
```python
# 当前：二进制魔数 + JSON头
magic = b"TTGS"
header_json = "{\"version\":1,...}"
```

#### 优化设计：人类可读前缀
```python
# 优化：人类可读前缀 + 二进制魔数 + JSON头
human_readable_prefix = "TTG_SEED_FILE v1.0\n"
magic = b"TTGS"
header_json = "{\"version\":1,...}"
```

### 2. 文件结构重新设计

#### 新的TTG文件结构
```
TTG文件 = 人类可读前缀 + TTG文件头 + 压缩数据

人类可读前缀: "TTG_SEED_FILE v1.0\n" (UTF-8编码)
TTG文件头: JSON格式的完整元数据
压缩数据: 经过协议栈编码的种子数据
```

#### 具体实现
```python
class TTGFileStructure:
    """TTG文件结构设计"""
    
    @staticmethod
    def create_ttg_file(header: Dict[str, Any], compressed_data: bytes) -> bytes:
        """创建TTG文件"""
        
        # 1. 人类可读前缀
        human_prefix = "TTG_SEED_FILE v1.0\nPROTOCOL: TTG\nFORMAT: binary_with_json_header\n\n"
        prefix_bytes = human_prefix.encode('utf-8')
        
        # 2. JSON文件头
        header_json = json.dumps(header, ensure_ascii=False)
        header_bytes = header_json.encode('utf-8')
        
        # 3. 添加长度前缀
        header_length = len(header_bytes).to_bytes(4, byteorder='big')
        
        # 4. 组合所有部分
        ttg_data = prefix_bytes + header_length + header_bytes + compressed_data
        
        return ttg_data
    
    @staticmethod
    def parse_ttg_file(ttg_data: bytes) -> Tuple[Dict[str, Any], bytes]:
        """解析TTG文件"""
        
        # 1. 跳过人类可读前缀（直到第一个空行）
        prefix_end = ttg_data.find(b'\n\n')
        if prefix_end == -1:
            raise ValueError("无效的TTG文件格式")
        
        # 2. 解析文件头长度
        header_length_start = prefix_end + 2  # 跳过两个换行符
        header_length = int.from_bytes(ttg_data[header_length_start:header_length_start+4], byteorder='big')
        
        # 3. 解析JSON文件头
        header_start = header_length_start + 4
        header_json = ttg_data[header_start:header_start+header_length].decode('utf-8')
        header = json.loads(header_json)
        
        # 4. 提取压缩数据
        compressed_data = ttg_data[header_start+header_length:]
        
        return header, compressed_data
```

### 3. 增强的文件头设计

#### 当前文件头
```python
{
    "magic": "TTGS",
    "version": 1,
    "file_type": "seed"
}
```

#### 增强的文件头（提供完整识别信息）
```python
{
    # 基础识别信息
    "file_format": "TTG",
    "protocol_version": "1.0",
    "content_type": "seed_data",
    "creation_tool": "SeedManager",
    
    # 人类可读描述
    "readable_description": "这是一个TTG格式的种子文件，包含基因编码的种子数据",
    "recommended_action": "使用TTGProtocolTool.parse_seed_ttg()解析",
    
    # 技术信息
    "magic": "TTGS",
    "version": 1,
    "file_type": "seed",
    "entity_type": "file",
    "quality_level": "standard",
    
    # 协议信息
    "protocol_layers": ["structural", "semantic", "seed_genetic", "seed_evolution"],
    "compression": "deflate",
    "encoding_mode": "standard",
    
    # 内容预览
    "content_preview": {
        "has_genes": true,
        "has_metadata": true,
        "gene_count": 25,
        "health_score": 0.85
    },
    
    # 校验信息
    "checksum": "abc123...",
    "original_size": 1024,
    "compressed_size": 256
}
```

### 4. Agent识别路径设计

#### 聪明Agent识别路径
```python
def smart_agent_recognize_ttg(file_data: bytes) -> bool:
    """聪明Agent识别TTG文件（单文件内）"""
    
    # 1. 检查人类可读前缀
    if file_data.startswith(b"TTG_SEED_FILE"):
        return True
    
    # 2. 检查文件扩展名（如果可用）
    # 注意：这是可选的，因为TTG文件可能没有扩展名
    
    # 3. 解析文件头验证
    try:
        header, _ = TTGFileStructure.parse_ttg_file(file_data)
        return header.get("file_format") == "TTG"
    except:
        pass
    
    return False
```

#### 笨Agent识别路径
```python
def simple_agent_recognize_ttg(file_data: bytes) -> bool:
    """笨Agent识别TTG文件（单文件内）"""
    
    # 1. 检查文件开头的人类可读文本
    try:
        first_100_bytes = file_data[:100].decode('utf-8', errors='ignore')
        
        # 明显的识别关键词
        keywords = ["TTG", "SEED", "seed", "protocol", "基因", "种子"]
        if any(keyword in first_100_bytes for keyword in keywords):
            return True
    except:
        pass
    
    # 2. 检查文件大小和模式（简单启发式）
    if 100 < len(file_data) < 10*1024*1024:  # 合理的大小范围
        # 检查是否有明显的JSON结构（文件头）
        try:
            # 寻找JSON开始标记
            json_start = file_data.find(b'{"')
            if json_start != -1 and json_start < 1000:  # JSON在文件开头附近
                return True
        except:
            pass
    
    return False
```

### 5. 文件内容预览机制

#### 在文件头中提供预览信息
```python
def generate_content_preview(seed_data: Dict[str, Any]) -> Dict[str, Any]:
    """生成内容预览信息（嵌入文件头）"""
    
    return {
        "has_genes": "genes" in seed_data,
        "has_metadata": "metadata" in seed_data,
        "has_evolution": "evolution_history" in seed_data,
        "gene_count": seed_data.get("metadata", {}).get("gene_count", 0),
        "health_score": seed_data.get("genes", {}).get("health_score", 0.0),
        "entity_type": seed_data.get("entity_type", "unknown"),
        "quality_level": seed_data.get("target_quality", "standard"),
        "created_at": seed_data.get("created_at", "unknown")
    }
```

### 6. 完整的TTG文件创建流程

```python
class SingleFileTTGManager:
    """单文件TTG管理器"""
    
    def create_seed_ttg(self, seed_data: Dict[str, Any], 
                       entity_type: str, target_quality: str) -> bytes:
        """创建单文件TTG种子"""
        
        # 1. 准备文件头
        header = self._prepare_enhanced_header(seed_data, entity_type, target_quality)
        
        # 2. 应用TTG协议栈编码
        compressed_data = self._apply_ttg_protocol(seed_data)
        
        # 3. 创建完整的TTG文件
        ttg_file = TTGFileStructure.create_ttg_file(header, compressed_data)
        
        return ttg_file
    
    def _prepare_enhanced_header(self, seed_data: Dict[str, Any], 
                               entity_type: str, target_quality: str) -> Dict[str, Any]:
        """准备增强的文件头"""
        
        return {
            # 基础识别信息
            "file_format": "TTG",
            "protocol_version": "1.0",
            "content_type": "seed_data",
            "creation_tool": "SeedManager",
            
            # 人类可读描述
            "readable_description": (
                f"这是一个TTG格式的{entity_type}种子文件，"
                f"包含基因编码的种子数据，质量等级：{target_quality}"
            ),
            "recommended_action": "使用TTGProtocolTool.parse_seed_ttg()解析",
            
            # 技术信息
            "magic": "TTGS",
            "version": 1,
            "file_type": "seed",
            "entity_type": entity_type,
            "quality_level": target_quality,
            
            # 协议信息
            "protocol_layers": ["structural", "semantic", "seed_genetic", "seed_evolution"],
            "compression": "deflate",
            "encoding_mode": "standard",
            
            # 内容预览
            "content_preview": generate_content_preview(seed_data),
            
            # 种子特定信息
            "seed_id": seed_data.get("seed_id"),
            "created_at": seed_data.get("created_at"),
            
            # 校验信息
            "original_size": len(str(seed_data).encode('utf-8')),
            "compressed_size": 0  # 将在压缩后更新
        }
    
    def _apply_ttg_protocol(self, data: Any) -> bytes:
        """应用TTG协议栈编码"""
        # 重用现有的TTG协议工具
        ttg_tool = TTGProtocolTool()
        result = ttg_tool.create_ttg_file(data)
        return result.ttg_data
```

### 7. 文件命名策略（保持简洁）

#### 单文件命名
```python
# 保持简洁，不创建辅助文件
seed_1234567890_abc123.ttg

# 或者使用更描述性的命名（可选）
seed_file_1234567890_abc123.ttg
seed_project_python_1234567890.ttg
```

### 8. Agent操作指南（嵌入文件头）

#### 在文件头中提供操作指南
```python
{
    "operation_guide": {
        "python": "from prometheus.philosophy.tools.ttg_protocol_tool import TTGProtocolTool; tool = TTGProtocolTool(); result = tool.parse_seed_ttg(file_data)",
        "description": "使用TTG协议工具解析此文件",
        "example_output": "解析后将得到包含基因数据的字典"
    }
}
```

## 技术优势

### 1. **真正的单文件传输**
- 一个文件包含所有必要信息
- 不依赖外部文件
- 保持协议的简洁性

### 2. **智能识别机制**
- 人类可读前缀提供明显线索
- 增强的文件头包含完整信息
- 内容预览帮助理解文件内容

### 3. **友好的Agent体验**
- 聪明Agent：快速准确识别
- 笨Agent：通过明显提示识别
- 所有Agent：获得足够操作指导

### 4. **保持技术先进性**
- 不牺牲TTG协议的核心特性
- 提供完整的自包含性
- 支持各种使用场景

## 实施计划

### 第一阶段：文件结构优化
1. 实现人类可读前缀
2. 优化文件头设计
3. 提供内容预览机制

### 第二阶段：识别机制实现
1. 实现聪明Agent识别路径
2. 实现笨Agent识别路径
3. 提供操作指南嵌入

### 第三阶段：集成测试
1. 测试各种Agent的识别效果
2. 优化识别算法
3. 验证单文件完整性

## 总结

通过这个单文件内的识别机制设计，我们真正实现了TTG协议"单文件传输整个生命"的理念：

1. **自包含性**：一个文件包含所有识别和操作信息
2. **智能识别**：通过文件内部结构提供多层次的识别线索
3. **用户友好**：为不同智能水平的Agent提供适当的指导
4. **技术先进**：保持TTG协议的核心特性和简洁性

这个设计确保了TTG协议既保持了技术先进性，又提供了友好的用户体验，真正实现了"单文件传输整个生命"的设计目标。