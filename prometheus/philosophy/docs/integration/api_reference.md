# API参考文档

## 概述

本文档提供普罗米修斯哲学概念相关API的详细参考，包括类、方法、参数和返回值说明。

## 核心类参考

### UniversalFragmenter

万物片段化引擎，负责系统的解构和重组。

#### 构造函数

```python
UniversalFragmenter()
```

#### 方法

##### fragment_by_concern

```python
def fragment_by_concern(
    self, 
    entity: Any, 
    concern_level: str = "atomic"
) -> List[Fragment]
```

按关注点分离原则进行片段化。

**参数：**
- `entity` (Any): 要解构的实体
- `concern_level` (str): 解构层级，可选值："atomic", "molecular", "cellular", "organ", "organism"

**返回值：**
- `List[Fragment]`: 片段列表

**示例：**
```python
fragmenter = UniversalFragmenter()
fragments = fragmenter.fragment_by_concern(codebase, "molecular")
```

##### reassemble_by_context

```python
def reassemble_by_context(
    self, 
    fragments: List[Fragment], 
    context: Dict[str, Any]
) -> Any
```

按上下文重新组装片段。

**参数：**
- `fragments` (List[Fragment]): 要重组的片段列表
- `context` (Dict[str, Any]): 重组上下文信息

**返回值：**
- `Any`: 重组后的实体

**示例：**
```python
reassembled = fragmenter.reassemble_by_context(fragments, {"strategy": "hierarchical"})
```

### HierarchicalEncoder

分层编码器，负责数据的编码处理。

#### 构造函数

```python
HierarchicalEncoder()
```

#### 方法

##### encode

```python
def encode(
    self, 
    data: Any, 
    target_layer: EncodingLayer, 
    context_hints: Optional[Dict] = None
) -> EncodingResult
```

分层编码数据。

**参数：**
- `data` (Any): 要编码的数据
- `target_layer` (EncodingLayer): 目标编码层级
- `context_hints` (Optional[Dict]): 上下文提示信息

**返回值：**
- `EncodingResult`: 编码结果

**示例：**
```python
encoder = HierarchicalEncoder()
result = encoder.encode(data, EncodingLayer.SEMANTIC)
```

### UniversalSeedConverter

万物种子化转换器，负责实体的种子化转换。

#### 构造函数

```python
UniversalSeedConverter(prometheus_home: Path)
```

**参数：**
- `prometheus_home` (Path): 普罗米修斯主目录路径

#### 方法

##### convert_to_seed

```python
def convert_to_seed(
    self, 
    entity: Any, 
    entity_type: str, 
    target_quality: str = "standard",
    context: Optional[Dict] = None
) -> SeedConversionResult
```

将实体转换为种子。

**参数：**
- `entity` (Any): 要转换的实体
- `entity_type` (str): 实体类型，可选值："file", "project", "skill", "concept", "workflow", "dataset", "model"
- `target_quality` (str): 目标质量等级，可选值："basic", "standard", "premium", "excellent"
- `context` (Optional[Dict]): 转换上下文信息

**返回值：**
- `SeedConversionResult`: 种子转换结果

**示例：**
```python
converter = UniversalSeedConverter(Path.home() / ".prometheus")
result = converter.convert_to_seed(file_path, "file", "standard")
```

##### validate_seed

```python
def validate_seed(self, seed_data: Dict[str, Any]) -> SeedValidationResult
```

验证种子的有效性。

**参数：**
- `seed_data` (Dict[str, Any]): 种子数据

**返回值：**
- `SeedValidationResult`: 验证结果

**示例：**
```python
validation_result = converter.validate_seed(seed_data)
```

### TTGProtocolTool

TTG协议工具，负责TTG文件的创建和解析。

#### 构造函数

```python
TTGProtocolTool()
```

#### 方法

##### create_ttg_file

```python
def create_ttg_file(
    self, 
    data: Any, 
    protocol_layers: Optional[List[TTGProtocolLayer]] = None,
    compression: TTGCompressionAlgorithm = TTGCompressionAlgorithm.DEFLATE,
    encoding_mode: TTGEncodingMode = TTGEncodingMode.STANDARD,
    custom_options: Optional[Dict] = None
) -> TTGProtocolResult
```

创建TTG文件。

**参数：**
- `data` (Any): 要编码的数据
- `protocol_layers` (Optional[List[TTGProtocolLayer]]): 协议层级列表
- `compression` (TTGCompressionAlgorithm): 压缩算法
- `encoding_mode` (TTGEncodingMode): 编码模式
- `custom_options` (Optional[Dict]): 自定义选项

**返回值：**
- `TTGProtocolResult`: TTG协议处理结果

**示例：**
```python
ttg_tool = TTGProtocolTool()
result = ttg_tool.create_ttg_file(data, [TTGProtocolLayer.STRUCTURAL, TTGProtocolLayer.SEMANTIC])
```

##### parse_ttg_file

```python
def parse_ttg_file(self, ttg_data: bytes) -> TTGProtocolResult
```

解析TTG文件。

**参数：**
- `ttg_data` (bytes): TTG文件数据

**返回值：**
- `TTGProtocolResult`: TTG协议处理结果

**示例：**
```python
result = ttg_tool.parse_ttg_file(ttg_data)
```

## 数据结构参考

### Fragment

片段数据结构，表示解构后的功能单元。

**属性：**
- `fragment_id` (str): 片段ID
- `content` (Any): 片段内容
- `concern_type` (str): 关注点类型
- `metadata` (Dict[str, Any]): 元数据

### EncodingResult

编码结果数据结构。

**属性：**
- `encoded_data` (Any): 编码后的数据
- `encoding_layer` (EncodingLayer): 编码层级
- `compression_ratio` (float): 压缩比
- `metadata` (Dict[str, Any]): 元数据

### SeedConversionResult

种子转换结果数据结构。

**属性：**
- `seed_data` (Dict[str, Any]): 种子数据
- `entity_type` (str): 实体类型
- `quality_level` (str): 质量等级
- `gene_count` (int): 基因数量
- `conversion_metrics` (Dict[str, Any]): 转换指标

### TTGProtocolResult

TTG协议处理结果数据结构。

**属性：**
- `success` (bool): 处理是否成功
- `ttg_data` (Optional[bytes]): TTG数据
- `original_size` (int): 原始大小
- `compressed_size` (int): 压缩后大小
- `compression_ratio` (float): 压缩比
- `protocol_layers` (List[TTGProtocolLayer]): 协议层级
- `error_message` (Optional[str]): 错误信息

## 枚举类型参考

### EncodingLayer

编码层级枚举。

**值：**
- `STRUCTURAL`: 结构编码
- `SEMANTIC`: 语义编码
- `CONTEXTUAL`: 上下文编码
- `EVOLUTIONARY`: 进化编码

### TTGProtocolLayer

TTG协议层级枚举。

**值：**
- `STRUCTURAL`: 结构层
- `SEMANTIC`: 语义层
- `CONTEXTUAL`: 上下文层
- `EVOLUTIONARY`: 进化层
- `QUANTUM`: 量子层

### TTGCompressionAlgorithm

TTG压缩算法枚举。

**值：**
- `NONE`: 无压缩
- `DEFLATE`: DEFLATE压缩
- `LZ4`: LZ4压缩
- `ZSTD`: ZSTD压缩
- `BROTLI`: Brotli压缩

### TTGEncodingMode

TTG编码模式枚举。

**值：**
- `STANDARD`: 标准模式
- `COMPACT`: 紧凑模式
- `HUMAN_READABLE`: 人类可读模式
- `BINARY`: 二进制模式
- `QUANTUM`: 量子模式

## 工具类参考

### SeedManager

种子管理工具，基于现有基因系统的种子管理。

#### 构造函数

```python
SeedManager(prometheus_home: Path)
```

**参数：**
- `prometheus_home` (Path): 普罗米修斯主目录路径

#### 方法

##### create_seed

```python
def create_seed(
    self, 
    entity: Any, 
    entity_type: str, 
    target_quality: str = "standard"
) -> Dict[str, Any]
```

创建种子。

**参数：**
- `entity` (Any): 要种子化的实体
- `entity_type` (str): 实体类型
- `target_quality` (str): 目标质量等级

**返回值：**
- `Dict[str, Any]`: 种子数据

##### validate_seed

```python
def validate_seed(self, seed_data: Dict[str, Any]) -> SeedValidationResult
```

验证种子。

**参数：**
- `seed_data` (Dict[str, Any]): 种子数据

**返回值：**
- `SeedValidationResult`: 验证结果

##### list_seeds

```python
def list_seeds(self, entity_type: Optional[str] = None) -> List[Dict[str, Any]]
```

列出种子。

**参数：**
- `entity_type` (Optional[str]): 实体类型过滤器

**返回值：**
- `List[Dict[str, Any]]`: 种子列表

## 错误处理

### 常见错误

#### 编码错误

- **InvalidEncodingLayerError**: 无效的编码层级
- **EncodingFailedError**: 编码失败
- **CompressionError**: 压缩错误

#### 种子化错误

- **InvalidEntityTypeError**: 无效的实体类型
- **SeedConversionError**: 种子转换错误
- **SeedValidationError**: 种子验证错误

#### TTG协议错误

- **TTGHeaderError**: TTG文件头错误
- **TTGChecksumError**: TTG校验和错误
- **TTGParseError**: TTG解析错误

### 错误处理示例

```python
try:
    result = encoder.encode(data, EncodingLayer.SEMANTIC)
    if not result.success:
        logger.error(f"编码失败: {result.error_message}")
        
except InvalidEncodingLayerError as e:
    logger.error(f"无效的编码层级: {e}")
    
except EncodingFailedError as e:
    logger.error(f"编码失败: {e}")
```

## 性能考虑

### 内存使用

- 大型实体的解构可能消耗较多内存
- 建议使用流式处理或分块处理
- 考虑使用内存映射文件处理大文件

### 处理时间

- 复杂实体的编码可能需要较长时间
- 建议使用异步处理或进度指示
- 考虑使用缓存机制优化重复处理

### 并发安全

- 大多数类不是线程安全的
- 在多线程环境中使用需要额外的同步机制
- 建议每个线程使用独立的实例

## 扩展指南

### 自定义解构策略

```python
class CustomFragmenter(UniversalFragmenter):
    def _custom_fragmentation_strategy(self, entity):
        # 实现自定义解构逻辑
        pass
```

### 自定义编码器

```python
class CustomEncoder(HierarchicalEncoder):
    def _custom_encoding_method(self, data):
        # 实现自定义编码方法
        pass
```

### 自定义种子转换器

```python
class CustomSeedConverter(UniversalSeedConverter):
    def _custom_conversion_method(self, entity):
        # 实现自定义转换方法
        pass
```

## 总结

本文档提供了普罗米修斯哲学概念相关API的完整参考，包括核心类、方法、数据结构和错误处理。通过合理使用这些API，可以充分发挥哲学概念的技术价值，同时确保与现有框架的良好集成。