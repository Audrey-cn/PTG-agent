#!/usr/bin/env python3
"""万物解构与片段化框架"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import re
import json


class DeconstructionLevel(Enum):
    """解构层级定义"""
    ATOMIC = "atomic"      # 原子级（不可再分的最小单元）
    MOLECULAR = "molecular" # 分子级（功能组合体）
    CELLULAR = "cellular"   # 细胞级（独立功能模块）
    ORGAN = "organ"        # 器官级（系统组件）
    ORGANISM = "organism"   # 有机体级（完整系统）


class ConcernType(Enum):
    """关注点类型"""
    STRUCTURAL = "structural"    # 结构关注点
    BEHAVIORAL = "behavioral"    # 行为关注点
    DATA = "data"               # 数据关注点
    INTERFACE = "interface"     # 接口关注点
    CONTEXT = "context"         # 上下文关注点


@dataclass
class Fragment:
    """片段基类"""
    id: str
    content: Any
    concern: ConcernType
    level: DeconstructionLevel
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "content": self.content,
            "concern": self.concern.value,
            "level": self.level.value,
            "dependencies": self.dependencies,
            "metadata": self.metadata
        }


class UniversalFragmenter:
    """万物片段化引擎"""
    
    def __init__(self):
        self.fragment_registry: Dict[str, Fragment] = {}
        self.reassembly_patterns: Dict[str, List[str]] = {}
        self.concern_patterns = self._initialize_concern_patterns()
    
    def _initialize_concern_patterns(self) -> Dict[ConcernType, re.Pattern]:
        """初始化关注点识别模式"""
        return {
            ConcernType.STRUCTURAL: re.compile(r'(class|def|struct|interface)\s+\w+'),
            ConcernType.BEHAVIORAL: re.compile(r'(def|function|method)\s+\w+\s*\('),
            ConcernType.DATA: re.compile(r'(data|model|schema|config)\s*[=:{]'),
            ConcernType.INTERFACE: re.compile(r'(api|endpoint|route|export)\s+\w+'),
            ConcernType.CONTEXT: re.compile(r'(context|env|config|setting)s?\s*[=:]')
        }
    
    def fragment_by_concern(self, entity: Any, concern_level: DeconstructionLevel = DeconstructionLevel.ATOMIC) -> List[Fragment]:
        """按关注点分离原则进行片段化"""
        fragments = []
        
        if isinstance(entity, str):
            # 文本内容片段化
            fragments.extend(self._fragment_text(entity, concern_level))
        elif isinstance(entity, dict):
            # 字典结构片段化
            fragments.extend(self._fragment_dict(entity, concern_level))
        elif hasattr(entity, '__dict__'):
            # 对象片段化
            fragments.extend(self._fragment_object(entity, concern_level))
        
        return fragments
    
    def _fragment_text(self, text: str, level: DeconstructionLevel) -> List[Fragment]:
        """文本内容片段化"""
        fragments = []
        lines = text.split('\n')
        
        current_fragment = []
        current_concern = None
        
        for i, line in enumerate(lines):
            line_concern = self._detect_concern(line)
            
            if current_concern != line_concern and current_fragment:
                # 创建新片段
                fragment_id = f"text_frag_{len(fragments)}"
                fragments.append(Fragment(
                    id=fragment_id,
                    content='\n'.join(current_fragment),
                    concern=current_concern or ConcernType.STRUCTURAL,
                    level=level,
                    metadata={"line_range": (i - len(current_fragment), i)}
                ))
                current_fragment = []
            
            current_fragment.append(line)
            current_concern = line_concern
        
        # 处理最后一个片段
        if current_fragment:
            fragment_id = f"text_frag_{len(fragments)}"
            fragments.append(Fragment(
                id=fragment_id,
                content='\n'.join(current_fragment),
                concern=current_concern or ConcernType.STRUCTURAL,
                level=level,
                metadata={"line_range": (len(lines) - len(current_fragment), len(lines))}
            ))
        
        return fragments
    
    def _fragment_dict(self, data_dict: Dict[str, Any], level: DeconstructionLevel) -> List[Fragment]:
        """字典结构片段化"""
        fragments = []
        
        for key, value in data_dict.items():
            concern = self._detect_concern_from_key(key)
            fragment_id = f"dict_frag_{key}"
            
            fragments.append(Fragment(
                id=fragment_id,
                content=value,
                concern=concern,
                level=level,
                metadata={"key": key, "type": type(value).__name__}
            ))
        
        return fragments
    
    def _fragment_object(self, obj: Any, level: DeconstructionLevel) -> List[Fragment]:
        """对象片段化"""
        fragments = []
        
        # 按属性片段化
        for attr_name in dir(obj):
            if not attr_name.startswith('_'):
                try:
                    attr_value = getattr(obj, attr_name)
                    if not callable(attr_value):
                        concern = self._detect_concern_from_key(attr_name)
                        fragment_id = f"obj_frag_{attr_name}"
                        
                        fragments.append(Fragment(
                            id=fragment_id,
                            content=attr_value,
                            concern=concern,
                            level=level,
                            metadata={"attribute": attr_name, "type": type(attr_value).__name__}
                        ))
                except:
                    continue
        
        return fragments
    
    def _detect_concern(self, text: str) -> Optional[ConcernType]:
        """检测文本的关注点类型"""
        for concern_type, pattern in self.concern_patterns.items():
            if pattern.search(text):
                return concern_type
        return None
    
    def _detect_concern_from_key(self, key: str) -> ConcernType:
        """从键名检测关注点类型"""
        key_lower = key.lower()
        
        if any(word in key_lower for word in ['config', 'setting', 'param']):
            return ConcernType.CONTEXT
        elif any(word in key_lower for word in ['data', 'model', 'schema']):
            return ConcernType.DATA
        elif any(word in key_lower for word in ['api', 'interface', 'endpoint']):
            return ConcernType.INTERFACE
        elif any(word in key_lower for word in ['method', 'function', 'behavior']):
            return ConcernType.BEHAVIORAL
        else:
            return ConcernType.STRUCTURAL
    
    def register_fragment(self, fragment: Fragment):
        """注册片段"""
        self.fragment_registry[fragment.id] = fragment
    
    def define_reassembly_pattern(self, pattern_name: str, fragment_ids: List[str]):
        """定义重组模式"""
        self.reassembly_patterns[pattern_name] = fragment_ids
    
    def reassemble_by_context(self, fragment_ids: List[str], context: Dict[str, Any]) -> Any:
        """按上下文重新组装片段"""
        fragments = [self.fragment_registry.get(fid) for fid in fragment_ids if fid in self.fragment_registry]
        fragments = [f for f in fragments if f is not None]
        
        # 按关注点类型排序
        fragments.sort(key=lambda f: list(ConcernType).index(f.concern))
        
        # 根据上下文选择重组策略
        reassembly_strategy = context.get('strategy', 'sequential')
        
        if reassembly_strategy == 'sequential':
            return self._reassemble_sequential(fragments)
        elif reassembly_strategy == 'hierarchical':
            return self._reassemble_hierarchical(fragments)
        else:
            return self._reassemble_default(fragments)
    
    def _reassemble_sequential(self, fragments: List[Fragment]) -> str:
        """顺序重组"""
        result = []
        for fragment in fragments:
            if isinstance(fragment.content, str):
                result.append(fragment.content)
            else:
                result.append(str(fragment.content))
        return '\n'.join(result)
    
    def _reassemble_hierarchical(self, fragments: List[Fragment]) -> Dict[str, Any]:
        """层次化重组"""
        result = {}
        for fragment in fragments:
            key = f"{fragment.concern.value}_{fragment.id}"
            result[key] = fragment.content
        return result
    
    def _reassemble_default(self, fragments: List[Fragment]) -> Any:
        """默认重组策略"""
        if all(isinstance(f.content, str) for f in fragments):
            return self._reassemble_sequential(fragments)
        else:
            return self._reassemble_hierarchical(fragments)


# 使用示例
def demonstrate_deconstruction():
    """演示解构框架的使用"""
    fragmenter = UniversalFragmenter()
    
    # 示例文本
    sample_text = """
    class UserService:
        def get_user(self, user_id):
            # 获取用户数据
            return self.db.query(User).filter(User.id == user_id).first()
        
        def update_user(self, user_id, data):
            # 更新用户信息
            user = self.get_user(user_id)
            for key, value in data.items():
                setattr(user, key, value)
            self.db.commit()
    
    config = {
        'database_url': 'postgresql://localhost:5432/app',
        'cache_timeout': 3600
    }
    """
    
    # 片段化
    fragments = fragmenter.fragment_by_concern(sample_text, DeconstructionLevel.MOLECULAR)
    
    print("=== 片段化结果 ===")
    for fragment in fragments:
        print(f"ID: {fragment.id}")
        print(f"关注点: {fragment.concern.value}")
        print(f"层级: {fragment.level.value}")
        print(f"内容预览: {fragment.content[:100]}...")
        print("-" * 50)
    
    # 注册片段并定义重组模式
    for fragment in fragments:
        fragmenter.register_fragment(fragment)
    
    fragmenter.define_reassembly_pattern("full_service", [f.id for f in fragments])
    
    # 重组
    reassembled = fragmenter.reassemble_by_context(
        [f.id for f in fragments], 
        {"strategy": "sequential"}
    )
    
    print("=== 重组结果 ===")
    print(reassembled)


if __name__ == "__main__":
    demonstrate_deconstruction()