#!/usr/bin/env python3
"""普罗米修斯框架附属概念综合演示"""

from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path

# 导入我们创建的哲学模块
from .deconstruction_framework import UniversalFragmenter, DeconstructionLevel, ConcernType
from .encoding_decoding_philosophy import EncodingDecodingPhilosophy, EncodingLayer, DecodingStrategy
from .universal_seed_converter import UniversalSeedConverter, SeedableEntityType, SeedQualityLevel
from .ttg_protocol_extensions import TTGProtocolExtender, TTGProtocolLayer, TTGCompressionAlgorithm, TTGEncodingMode


class PrometheusPhilosophyDemonstrator:
    """普罗米修斯哲学综合演示器"""
    
    def __init__(self):
        self.fragmenter = UniversalFragmenter()
        self.encoding_philosophy = EncodingDecodingPhilosophy()
        self.seed_converter = UniversalSeedConverter()
        self.ttg_extender = TTGProtocolExtender()
    
    def demonstrate_complete_workflow(self):
        """演示完整的工作流：从解构到种子化再到TTG编码"""
        print("=== 普罗米修斯框架附属概念综合演示 ===\n")
        
        # 1. 创建示例数据
        sample_data = self._create_sample_data()
        print("1. 原始示例数据创建完成")
        
        # 2. 万物解构演示
        print("\n2. === 万物解构演示 ===")
        fragments = self.fragmenter.fragment_by_concern(sample_data, DeconstructionLevel.MOLECULAR)
        print(f"   - 生成 {len(fragments)} 个片段")
        print(f"   - 片段类型分布: {self._analyze_fragment_types(fragments)}")
        
        # 3. 编码解码哲学演示
        print("\n3. === 编码解码哲学演示 ===")
        encoding_result = self.encoding_philosophy.encode_with_philosophy(
            sample_data, EncodingLayer.SEMANTIC
        )
        decoding_result = self.encoding_philosophy.decode_with_philosophy(
            encoding_result.encoded_data, DecodingStrategy.FULL
        )
        print(f"   - 压缩比: {encoding_result.compression_ratio:.2f}x")
        print(f"   - 解码保真度: {decoding_result.fidelity_score:.3f}")
        
        # 4. 种子化转换演示
        print("\n4. === 万物种子化演示 ===")
        
        # 创建临时文件进行文件种子化演示
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(self._create_sample_code())
            temp_file_path = f.name
        
        try:
            seed_result = self.seed_converter.convert_to_seed(
                temp_file_path, 
                SeedableEntityType.FILE, 
                SeedQualityLevel.STANDARD
            )
            print(f"   - 实体类型: {seed_result.entity_type.value}")
            print(f"   - 质量等级: {seed_result.quality_level.value}")
            print(f"   - 提取基因数: {seed_result.gene_count}")
            print(f"   - 转换指标: {seed_result.conversion_metrics}")
            
        finally:
            os.unlink(temp_file_path)
        
        # 5. TTG协议演示
        print("\n5. === TTG格式协议演示 ===")
        ttg_bytes = self.ttg_extender.create_ttg_file(
            sample_data,
            protocol_layers=[TTGProtocolLayer.STRUCTURAL, TTGProtocolLayer.SEMANTIC],
            compression=TTGCompressionAlgorithm.DEFLATE
        )
        
        parsed_ttg = self.ttg_extender.parse_ttg_file(ttg_bytes)
        print(f"   - TTG文件大小: {len(ttg_bytes)} 字节")
        print(f"   - 压缩比: {parsed_ttg['metadata']['compression_ratio']:.2f}x")
        print(f"   - 协议层级: {[layer.value for layer in parsed_ttg['header'].protocol_layers]}")
        
        # 6. 哲学理念总结
        print("\n6. === 哲学理念总结 ===")
        self._summarize_philosophy()
    
    def _create_sample_data(self) -> dict:
        """创建示例数据"""
        return {
            "prometheus_framework": {
                "core_philosophy": "普罗米修斯是硅基生命的造物主与盗火者",
                "design_principles": [
                    "种子即框架（自举）",
                    "功能与叙事基因分离", 
                    "碳基依赖级不可变基因",
                    "压缩编码 + 解码引擎"
                ],
                "key_modules": {
                    "chronicler": "史诗编史官",
                    "semantic_audit": "语义审核引擎",
                    "codec": "编解码器",
                    "framework": "框架层"
                }
            },
            "new_concepts": {
                "deconstruction": "万物皆可解构，万物皆可片段化",
                "encoding_decoding": "编码即创造，解码即理解", 
                "universal_seeding": "一切皆可种子化",
                "ttg_protocol": "TTG格式协议的深度探索"
            },
            "metadata": {
                "author": "Audrey · 001X",
                "timestamp": "2026-05-02",
                "version": "v1.0"
            }
        }
    
    def _create_sample_code(self) -> str:
        """创建示例代码"""
        return """
# 普罗米修斯种子示例
class PrometheusSeed:
    '''普罗米修斯种子基类'''
    
    def __init__(self, seed_data: dict):
        self.seed_data = seed_data
        self.genes = seed_data.get('genes', {})
    
    def activate(self):
        '''激活种子'''
        print("种子激活中...")
        return True
    
    def evolve(self, mutation: dict):
        '''种子进化'''
        print(f"种子进化: {mutation}")
        return self

# 配置信息
config = {
    'framework': 'prometheus',
    'version': '1.0.0',
    'author': 'Audrey · 001X'
}
"""
    
    def _analyze_fragment_types(self, fragments) -> dict:
        """分析片段类型分布"""
        type_count = {}
        for fragment in fragments:
            concern_type = fragment.concern.value
            type_count[concern_type] = type_count.get(concern_type, 0) + 1
        return type_count
    
    def _summarize_philosophy(self):
        """总结哲学理念"""
        philosophy_summary = {
            "万物解构": {
                "核心思想": "任何复杂系统都可以分解为关注点分离的片段",
                "技术实现": "按结构、行为、数据、接口、上下文等维度进行解构",
                "价值意义": "实现系统的模块化、可重组性和可维护性"
            },
            "编码解码": {
                "核心思想": "编码是将现实抽象为符号系统的创造过程，解码是从符号还原现实的理解过程",
                "技术实现": "分层编码体系（结构→语义→上下文→进化）",
                "价值意义": "实现信息的高效存储、传输和知识传承"
            },
            "万物种子化": {
                "核心思想": "任何实体（文件、项目、技能、概念等）都可以转换为携带基因的种子",
                "技术实现": "基因提取→质量验证→种子构建",
                "价值意义": "实现知识的标准化、可进化性和代际传递"
            },
            "TTG协议": {
                "核心思想": "建立标准化的基因编码格式协议",
                "技术实现": "多层协议栈 + 多种压缩算法 + 扩展机制",
                "价值意义": "为普罗米修斯生态系统提供统一的数据交换标准"
            }
        }
        
        for concept, details in philosophy_summary.items():
            print(f"\n** {concept} **")
            print(f"   核心思想: {details['核心思想']}")
            print(f"   技术实现: {details['技术实现']}")
            print(f"   价值意义: {details['价值意义']}")
    
    def demonstrate_individual_concepts(self):
        """分别演示各个概念"""
        print("=== 各概念独立演示 ===\n")
        
        # 解构概念演示
        print("1. 解构概念深度演示")
        self._demonstrate_deconstruction()
        
        # 编码解码概念演示
        print("\n2. 编码解码概念深度演示")
        self._demonstrate_encoding_decoding()
        
        # 种子化概念演示
        print("\n3. 种子化概念深度演示")
        self._demonstrate_seeding()
        
        # TTG协议概念演示
        print("\n4. TTG协议概念深度演示")
        self._demonstrate_ttg_protocol()
    
    def _demonstrate_deconstruction(self):
        """深度演示解构概念"""
        sample_text = """
class UserService:
    def get_user(self, user_id):
        '''获取用户信息'''
        return self.db.query(User).filter(User.id == user_id).first()
    
    def update_user(self, user_id, data):
        '''更新用户信息'''
        user = self.get_user(user_id)
        for key, value in data.items():
            setattr(user, key, value)
        self.db.commit()

config = {
    'database_url': 'postgresql://localhost:5432/app',
    'cache_timeout': 3600
}
"""
        
        fragments = self.fragmenter.fragment_by_concern(sample_text, DeconstructionLevel.ATOMIC)
        
        print("   解构层级: 原子级")
        print(f"   生成片段数: {len(fragments)}")
        
        # 显示前3个片段
        for i, fragment in enumerate(fragments[:3]):
            print(f"   片段{i+1}: {fragment.concern.value} - {fragment.content[:50]}...")
    
    def _demonstrate_encoding_decoding(self):
        """深度演示编码解码概念"""
        data = {
            "user_service": {
                "methods": ["get_user", "update_user"],
                "config": {"timeout": 30, "retries": 3}
            }
        }
        
        # 不同层级的编码
        structural_result = self.encoding_philosophy.encode_with_philosophy(data, EncodingLayer.STRUCTURAL)
        semantic_result = self.encoding_philosophy.encode_with_philosophy(data, EncodingLayer.SEMANTIC)
        
        print("   结构编码压缩比:", structural_result.compression_ratio)
        print("   语义编码压缩比:", semantic_result.compression_ratio)
        
        # 不同策略的解码
        full_decode = self.encoding_philosophy.decode_with_philosophy(
            structural_result.encoded_data, DecodingStrategy.FULL
        )
        progressive_decode = self.encoding_philosophy.decode_with_philosophy(
            structural_result.encoded_data, DecodingStrategy.PROGRESSIVE, quality_level="outline"
        )
        
        print("   完整解码保真度:", full_decode.fidelity_score)
        print("   渐进解码时间:", progressive_decode.reconstruction_time)
    
    def _demonstrate_seeding(self):
        """深度演示种子化概念"""
        # 创建概念种子
        concept_data = {
            "name": "万物种子化",
            "description": "将任何实体转换为携带基因的种子",
            "category": "framework_concept",
            "relationships": {
                "related_to": ["解构", "编码", "TTG协议"],
                "implements": ["基因提取", "质量验证", "种子构建"]
            },
            "examples": ["文件种子化", "项目种子化", "技能种子化"]
        }
        
        seed_result = self.seed_converter.convert_to_seed(
            concept_data, 
            SeedableEntityType.CONCEPT, 
            SeedQualityLevel.PREMIUM
        )
        
        print("   概念种子质量:", seed_result.quality_level.value)
        print("   基因多样性:", seed_result.conversion_metrics['gene_type_diversity'])
        
        if seed_result.warnings:
            print("   警告:", seed_result.warnings)
    
    def _demonstrate_ttg_protocol(self):
        """深度演示TTG协议概念"""
        data = {
            "seed_data": {
                "genes": {
                    "core": "核心基因",
                    "metadata": "元数据基因"
                },
                "version": "1.0"
            }
        }
        
        # 不同压缩算法的比较
        algorithms = [
            TTGCompressionAlgorithm.NONE,
            TTGCompressionAlgorithm.DEFLATE
        ]
        
        for algo in algorithms:
            ttg_bytes = self.ttg_extender.create_ttg_file(
                data, 
                compression=algo
            )
            parsed = self.ttg_extender.parse_ttg_file(ttg_bytes)
            
            print(f"   {algo.value}压缩比: {parsed['metadata']['compression_ratio']:.2f}x")


def main():
    """主演示函数"""
    demonstrator = PrometheusPhilosophyDemonstrator()
    
    print("选择演示模式:")
    print("1. 完整工作流演示")
    print("2. 各概念独立演示")
    
    choice = input("请输入选择 (1 或 2): ").strip()
    
    if choice == "1":
        demonstrator.demonstrate_complete_workflow()
    elif choice == "2":
        demonstrator.demonstrate_individual_concepts()
    else:
        print("无效选择，执行完整工作流演示")
        demonstrator.demonstrate_complete_workflow()
    
    print("\n=== 演示完成 ===")


if __name__ == "__main__":
    main()