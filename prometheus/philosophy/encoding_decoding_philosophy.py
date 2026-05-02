#!/usr/bin/env python3
"""编码与解码哲学的实现框架"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import hashlib
import json
import time


class EncodingLayer(Enum):
    """编码层级定义"""
    STRUCTURAL = "structural"      # 结构编码（Layer1 - 9:1压缩）
    SEMANTIC = "semantic"         # 语义编码（Layer2 - 30:1+压缩）
    CONTEXTUAL = "contextual"     # 上下文编码（动态语义压缩）
    EVOLUTIONARY = "evolutionary" # 进化编码（基因突变记录）


class DecodingStrategy(Enum):
    """解码策略"""
    FULL = "full"                 # 完整解码
    PROGRESSIVE = "progressive"   # 渐进式解码
    CONTEXT_AWARE = "context_aware" # 上下文感知解码
    ADAPTIVE = "adaptive"         # 自适应解码


@dataclass
class EncodingResult:
    """编码结果"""
    encoded_data: Any
    encoding_layer: EncodingLayer
    compression_ratio: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class DecodingResult:
    """解码结果"""
    decoded_data: Any
    decoding_strategy: DecodingStrategy
    fidelity_score: float
    reconstruction_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class HierarchicalEncoder:
    """分层编码器"""
    
    def __init__(self):
        self.encoding_pipelines = self._initialize_pipelines()
        self.context_registry: Dict[str, Any] = {}
    
    def _initialize_pipelines(self) -> Dict[EncodingLayer, Callable]:
        """初始化编码流水线"""
        return {
            EncodingLayer.STRUCTURAL: self._structural_encoding,
            EncodingLayer.SEMANTIC: self._semantic_encoding,
            EncodingLayer.CONTEXTUAL: self._contextual_encoding,
            EncodingLayer.EVOLUTIONARY: self._evolutionary_encoding
        }
    
    def encode(self, data: Any, target_layer: EncodingLayer, context_hints: Optional[Dict] = None) -> EncodingResult:
        """分层编码"""
        original_size = self._calculate_data_size(data)
        
        # 按层级逐步编码
        current_data = data
        current_layer = EncodingLayer.STRUCTURAL
        
        while current_layer.value <= target_layer.value:
            encoder = self.encoding_pipelines[current_layer]
            current_data = encoder(current_data, context_hints)
            
            if current_layer == target_layer:
                break
            
            # 移动到下一层级
            current_layer = self._get_next_layer(current_layer)
        
        encoded_size = self._calculate_data_size(current_data)
        compression_ratio = original_size / encoded_size if encoded_size > 0 else 1.0
        
        return EncodingResult(
            encoded_data=current_data,
            encoding_layer=target_layer,
            compression_ratio=compression_ratio,
            metadata={
                "original_size": original_size,
                "encoded_size": encoded_size,
                "context_hints": context_hints or {}
            }
        )
    
    def _structural_encoding(self, data: Any, context_hints: Optional[Dict]) -> Any:
        """结构编码（类似DNA碱基编码）"""
        if isinstance(data, dict):
            return self._encode_dict_structurally(data)
        elif isinstance(data, list):
            return self._encode_list_structurally(data)
        elif isinstance(data, str):
            return self._encode_string_structurally(data)
        else:
            return data
    
    def _encode_dict_structurally(self, data: Dict) -> Dict:
        """字典结构编码"""
        encoded = {}
        for key, value in data.items():
            # 键名压缩（使用哈希前缀）
            key_hash = hashlib.md5(key.encode()).hexdigest()[:8]
            compressed_key = f"{key_hash}:{key[:4]}" if len(key) > 8 else key
            
            encoded[compressed_key] = self._structural_encoding(value, None)
        
        return encoded
    
    def _encode_list_structurally(self, data: List) -> List:
        """列表结构编码"""
        return [self._structural_encoding(item, None) for item in data]
    
    def _encode_string_structurally(self, data: str) -> str:
        """字符串结构编码"""
        if len(data) <= 10:
            return data
        
        # 长字符串使用模式识别压缩
        words = data.split()
        if len(words) > 3:
            # 提取关键信息模式
            first_words = ' '.join(words[:2])
            last_words = ' '.join(words[-2:]) if len(words) > 4 else ''
            middle_hash = hashlib.md5(' '.join(words[2:-2]).encode()).hexdigest()[:6] if len(words) > 4 else ''
            
            return f"{first_words}...{middle_hash}...{last_words}"
        
        return data
    
    def _semantic_encoding(self, data: Any, context_hints: Optional[Dict]) -> Any:
        """语义编码（理解含义后的压缩）"""
        if isinstance(data, dict):
            return self._encode_dict_semantically(data, context_hints)
        elif isinstance(data, str):
            return self._encode_string_semantically(data, context_hints)
        else:
            return data
    
    def _encode_dict_semantically(self, data: Dict, context_hints: Optional[Dict]) -> Dict:
        """字典语义编码"""
        semantic_map = {
            "user_id": "uid",
            "user_name": "uname", 
            "created_at": "ct",
            "updated_at": "ut",
            "configuration": "cfg",
            "parameters": "params"
        }
        
        encoded = {}
        for key, value in data.items():
            semantic_key = semantic_map.get(key, key)
            encoded[semantic_key] = self._semantic_encoding(value, context_hints)
        
        return encoded
    
    def _encode_string_semantically(self, data: str, context_hints: Optional[Dict]) -> str:
        """字符串语义编码"""
        # 基于上下文的语义压缩
        if context_hints and "domain" in context_hints:
            domain = context_hints["domain"]
            
            if domain == "programming":
                # 编程领域语义压缩
                semantic_map = {
                    "function": "fn",
                    "variable": "var", 
                    "parameter": "param",
                    "return": "ret",
                    "import": "imp"
                }
                
                for full, short in semantic_map.items():
                    data = data.replace(full, short)
        
        return data
    
    def _contextual_encoding(self, data: Any, context_hints: Optional[Dict]) -> Any:
        """上下文编码（动态语义压缩）"""
        # 基于使用频率和上下文的动态编码
        if isinstance(data, dict):
            return self._encode_dict_contextually(data, context_hints)
        
        return data
    
    def _encode_dict_contextually(self, data: Dict, context_hints: Optional[Dict]) -> Dict:
        """字典上下文编码"""
        # 根据上下文重要性重新排序键
        importance_scores = self._calculate_importance_scores(data, context_hints)
        
        sorted_keys = sorted(data.keys(), key=lambda k: importance_scores.get(k, 0), reverse=True)
        
        encoded = {}
        for key in sorted_keys:
            encoded[key] = self._contextual_encoding(data[key], context_hints)
        
        return encoded
    
    def _calculate_importance_scores(self, data: Dict, context_hints: Optional[Dict]) -> Dict[str, float]:
        """计算键的重要性分数"""
        scores = {}
        
        for key in data.keys():
            # 基础分数基于键名长度和复杂性
            base_score = 1.0 / (len(key) + 1)
            
            # 上下文增强
            if context_hints and "important_keys" in context_hints:
                if key in context_hints["important_keys"]:
                    base_score *= 2.0
            
            scores[key] = base_score
        
        return scores
    
    def _evolutionary_encoding(self, data: Any, context_hints: Optional[Dict]) -> Any:
        """进化编码（基因突变记录）"""
        # 添加进化标记和版本信息
        evolutionary_data = {
            "data": data,
            "evolution_markers": {
                "encoding_version": "v1.0",
                "mutation_count": 0,
                "lineage_hash": hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]
            },
            "timestamp": time.time()
        }
        
        return evolutionary_data
    
    def _calculate_data_size(self, data: Any) -> int:
        """计算数据大小"""
        return len(json.dumps(data, ensure_ascii=False))
    
    def _get_next_layer(self, current_layer: EncodingLayer) -> EncodingLayer:
        """获取下一编码层级"""
        layers = list(EncodingLayer)
        current_index = layers.index(current_layer)
        
        if current_index < len(layers) - 1:
            return layers[current_index + 1]
        
        return current_layer


class HierarchicalDecoder:
    """分层解码器"""
    
    def __init__(self):
        self.decoding_strategies = self._initialize_strategies()
    
    def _initialize_strategies(self) -> Dict[DecodingStrategy, Callable]:
        """初始化解码策略"""
        return {
            DecodingStrategy.FULL: self._full_decoding,
            DecodingStrategy.PROGRESSIVE: self._progressive_decoding,
            DecodingStrategy.CONTEXT_AWARE: self._context_aware_decoding,
            DecodingStrategy.ADAPTIVE: self._adaptive_decoding
        }
    
    def decode(self, encoded_data: Any, strategy: DecodingStrategy, 
               context_hints: Optional[Dict] = None, quality_level: str = "full") -> DecodingResult:
        """分层解码"""
        start_time = time.time()
        
        decoder = self.decoding_strategies[strategy]
        decoded_data = decoder(encoded_data, context_hints, quality_level)
        
        reconstruction_time = time.time() - start_time
        fidelity_score = self._calculate_fidelity(encoded_data, decoded_data)
        
        return DecodingResult(
            decoded_data=decoded_data,
            decoding_strategy=strategy,
            fidelity_score=fidelity_score,
            reconstruction_time=reconstruction_time,
            metadata={
                "quality_level": quality_level,
                "context_hints": context_hints or {}
            }
        )
    
    def _full_decoding(self, encoded_data: Any, context_hints: Optional[Dict], quality_level: str) -> Any:
        """完整解码"""
        # 递归解码所有层级
        if isinstance(encoded_data, dict) and "evolution_markers" in encoded_data:
            # 进化编码数据
            return self._full_decoding(encoded_data["data"], context_hints, quality_level)
        elif isinstance(encoded_data, dict):
            return {k: self._full_decoding(v, context_hints, quality_level) for k, v in encoded_data.items()}
        elif isinstance(encoded_data, list):
            return [self._full_decoding(item, context_hints, quality_level) for item in encoded_data]
        else:
            return encoded_data
    
    def _progressive_decoding(self, encoded_data: Any, context_hints: Optional[Dict], quality_level: str) -> Any:
        """渐进式解码"""
        if quality_level == "outline":
            # 轮廓级解码（只解码关键结构）
            return self._decode_outline(encoded_data)
        elif quality_level == "sketch":
            # 草图级解码（解码主要内容）
            return self._decode_sketch(encoded_data)
        else:
            # 完整解码
            return self._full_decoding(encoded_data, context_hints, quality_level)
    
    def _decode_outline(self, encoded_data: Any) -> Any:
        """轮廓级解码"""
        if isinstance(encoded_data, dict):
            # 只保留前3个键
            keys = list(encoded_data.keys())[:3]
            return {k: "..." for k in keys}
        elif isinstance(encoded_data, list):
            # 只保留前2个元素
            return ["..."] * min(2, len(encoded_data))
        else:
            return str(encoded_data)[:50] + "..." if len(str(encoded_data)) > 50 else encoded_data
    
    def _decode_sketch(self, encoded_data: Any) -> Any:
        """草图级解码"""
        if isinstance(encoded_data, dict):
            return {k: self._decode_sketch(v) for k, v in list(encoded_data.items())[:10]}
        elif isinstance(encoded_data, list):
            return [self._decode_sketch(item) for item in encoded_data[:20]]
        else:
            return encoded_data
    
    def _context_aware_decoding(self, encoded_data: Any, context_hints: Optional[Dict], quality_level: str) -> Any:
        """上下文感知解码"""
        if context_hints and "preferred_structure" in context_hints:
            preferred = context_hints["preferred_structure"]
            # 根据偏好结构调整解码结果
            return self._restructure_for_context(encoded_data, preferred)
        
        return self._full_decoding(encoded_data, context_hints, quality_level)
    
    def _restructure_for_context(self, encoded_data: Any, preferred_structure: Dict) -> Any:
        """根据上下文偏好重新结构化"""
        # 简化的上下文适配
        decoded = self._full_decoding(encoded_data, None, "full")
        
        if isinstance(decoded, dict) and isinstance(preferred_structure, dict):
            # 重新排序键以匹配偏好
            reordered = {}
            for preferred_key in preferred_structure.keys():
                if preferred_key in decoded:
                    reordered[preferred_key] = decoded[preferred_key]
            
            # 添加未在偏好中的键
            for key, value in decoded.items():
                if key not in reordered:
                    reordered[key] = value
            
            return reordered
        
        return decoded
    
    def _adaptive_decoding(self, encoded_data: Any, context_hints: Optional[Dict], quality_level: str) -> Any:
        """自适应解码"""
        # 根据数据特征自动选择最佳解码策略
        data_complexity = self._assess_complexity(encoded_data)
        
        if data_complexity > 0.8:
            # 高复杂度数据使用渐进式解码
            return self._progressive_decoding(encoded_data, context_hints, "sketch")
        elif context_hints and "time_constrained" in context_hints:
            # 时间受限时使用上下文感知解码
            return self._context_aware_decoding(encoded_data, context_hints, quality_level)
        else:
            # 默认使用完整解码
            return self._full_decoding(encoded_data, context_hints, quality_level)
    
    def _assess_complexity(self, data: Any) -> float:
        """评估数据复杂度"""
        if isinstance(data, dict):
            return min(1.0, len(data) / 50.0)  # 字典键数量
        elif isinstance(data, list):
            return min(1.0, len(data) / 100.0)  # 列表长度
        else:
            return 0.0
    
    def _calculate_fidelity(self, original: Any, reconstructed: Any) -> float:
        """计算重建保真度"""
        try:
            original_str = json.dumps(original, sort_keys=True)
            reconstructed_str = json.dumps(reconstructed, sort_keys=True)
            
            if original_str == reconstructed_str:
                return 1.0
            
            # 简化的相似度计算
            from difflib import SequenceMatcher
            return SequenceMatcher(None, original_str, reconstructed_str).ratio()
        except:
            return 0.5  # 默认中等保真度


# 编码-解码哲学的核心实现
class EncodingDecodingPhilosophy:
    """编码-解码哲学的核心实现"""
    
    def __init__(self):
        self.encoder = HierarchicalEncoder()
        self.decoder = HierarchicalDecoder()
        self.encoding_history: List[EncodingResult] = []
        self.decoding_history: List[DecodingResult] = []
    
    def encode_with_philosophy(self, data: Any, target_layer: EncodingLayer, 
                             context_hints: Optional[Dict] = None) -> EncodingResult:
        """带哲学思考的编码"""
        # 编码即创造：将现实抽象为符号系统
        encoding_result = self.encoder.encode(data, target_layer, context_hints)
        
        # 记录编码历史
        self.encoding_history.append(encoding_result)
        
        return encoding_result
    
    def decode_with_philosophy(self, encoded_data: Any, strategy: DecodingStrategy,
                              context_hints: Optional[Dict] = None, quality_level: str = "full") -> DecodingResult:
        """带哲学思考的解码"""
        # 解码即理解：从符号系统还原现实意义
        decoding_result = self.decoder.decode(encoded_data, strategy, context_hints, quality_level)
        
        # 记录解码历史
        self.decoding_history.append(decoding_result)
        
        return decoding_result
    
    def demonstrate_philosophy(self):
        """演示编码-解码哲学"""
        sample_data = {
            "user_service": {
                "get_user_function": "def get_user(user_id): return db.query(User).filter(User.id == user_id).first()",
                "update_user_function": "def update_user(user_id, data): user = get_user(user_id); for k, v in data.items(): setattr(user, k, v); db.commit()",
                "configuration": {
                    "database_url": "postgresql://localhost:5432/app",
                    "cache_timeout": 3600,
                    "max_connections": 100
                }
            },
            "metadata": {
                "version": "1.0.0",
                "author": "Audrey · 001X",
                "created_at": "2026-05-02"
            }
        }
        
        print("=== 编码-解码哲学演示 ===")
        
        # 编码演示
        print("\n1. 结构编码（Layer1）:")
        structural_result = self.encode_with_philosophy(sample_data, EncodingLayer.STRUCTURAL)
        print(f"压缩比: {structural_result.compression_ratio:.2f}x")
        print(f"编码数据预览: {str(structural_result.encoded_data)[:200]}...")
        
        # 解码演示
        print("\n2. 完整解码:")
        full_decode = self.decode_with_philosophy(structural_result.encoded_data, DecodingStrategy.FULL)
        print(f"保真度: {full_decode.fidelity_score:.3f}")
        print(f"解码时间: {full_decode.reconstruction_time:.4f}s")
        
        print("\n3. 渐进式解码（轮廓级）:")
        outline_decode = self.decode_with_philosophy(structural_result.encoded_data, DecodingStrategy.PROGRESSIVE, quality_level="outline")
        print(f"轮廓保真度: {outline_decode.fidelity_score:.3f}")
        print(f"轮廓内容: {str(outline_decode.decoded_data)[:150]}...")


if __name__ == "__main__":
    philosophy = EncodingDecodingPhilosophy()
    philosophy.demonstrate_philosophy()