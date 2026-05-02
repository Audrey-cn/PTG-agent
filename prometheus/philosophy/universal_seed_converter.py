#!/usr/bin/env python3
"""万物种子化转换框架"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Type
import os
import re
import json
import hashlib
import inspect
from pathlib import Path


class SeedableEntityType(Enum):
    """可种子化实体类型"""
    FILE = "file"              # 单文件种子化
    PROJECT = "project"        # 项目种子化
    SKILL = "skill"            # 技能种子化
    CONCEPT = "concept"        # 概念种子化
    WORKFLOW = "workflow"      # 工作流种子化
    DATASET = "dataset"        # 数据集种子化
    MODEL = "model"            # 模型种子化


class SeedQualityLevel(Enum):
    """种子质量等级"""
    BASIC = "basic"           # 基础质量（包含核心基因）
    STANDARD = "standard"     # 标准质量（包含可执行性）
    PREMIUM = "premium"       # 优质质量（包含进化性）
    EXCELLENT = "excellent"   # 优秀质量（包含传承性）


@dataclass
class SeedGene:
    """种子基因"""
    gene_id: str
    gene_type: str
    content: Any
    importance: float  # 重要性分数（0-1）
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SeedConversionResult:
    """种子转换结果"""
    seed_data: Dict[str, Any]
    entity_type: SeedableEntityType
    quality_level: SeedQualityLevel
    gene_count: int
    conversion_metrics: Dict[str, Any]
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class UniversalSeedConverter:
    """万物种子化转换器"""
    
    def __init__(self):
        self.gene_extractors = self._initialize_gene_extractors()
        self.quality_validators = self._initialize_quality_validators()
        self.seed_templates = self._initialize_seed_templates()
    
    def _initialize_gene_extractors(self) -> Dict[SeedableEntityType, Callable]:
        """初始化基因提取器"""
        return {
            SeedableEntityType.FILE: self._extract_file_genes,
            SeedableEntityType.PROJECT: self._extract_project_genes,
            SeedableEntityType.SKILL: self._extract_skill_genes,
            SeedableEntityType.CONCEPT: self._extract_concept_genes,
            SeedableEntityType.WORKFLOW: self._extract_workflow_genes,
            SeedableEntityType.DATASET: self._extract_dataset_genes,
            SeedableEntityType.MODEL: self._extract_model_genes
        }
    
    def _initialize_quality_validators(self) -> Dict[SeedQualityLevel, Callable]:
        """初始化质量验证器"""
        return {
            SeedQualityLevel.BASIC: self._validate_basic_quality,
            SeedQualityLevel.STANDARD: self._validate_standard_quality,
            SeedQualityLevel.PREMIUM: self._validate_premium_quality,
            SeedQualityLevel.EXCELLENT: self._validate_excellent_quality
        }
    
    def _initialize_seed_templates(self) -> Dict[SeedableEntityType, Dict]:
        """初始化种子模板"""
        return {
            SeedableEntityType.FILE: self._create_file_seed_template(),
            SeedableEntityType.PROJECT: self._create_project_seed_template(),
            SeedableEntityType.SKILL: self._create_skill_seed_template(),
            SeedableEntityType.CONCEPT: self._create_concept_seed_template(),
            SeedableEntityType.WORKFLOW: self._create_workflow_seed_template(),
            SeedableEntityType.DATASET: self._create_dataset_seed_template(),
            SeedableEntityType.MODEL: self._create_model_seed_template()
        }
    
    def convert_to_seed(self, entity: Any, entity_type: SeedableEntityType, 
                       target_quality: SeedQualityLevel = SeedQualityLevel.STANDARD,
                       context: Optional[Dict] = None) -> SeedConversionResult:
        """将实体转换为种子"""
        
        # 提取基因
        gene_extractor = self.gene_extractors[entity_type]
        genes = gene_extractor(entity, context or {})
        
        # 构建种子数据
        seed_template = self.seed_templates[entity_type]
        seed_data = self._build_seed_data(seed_template, genes, entity_type, context)
        
        # 质量验证
        quality_validator = self.quality_validators[target_quality]
        validation_result = quality_validator(seed_data, genes)
        
        # 计算转换指标
        conversion_metrics = self._calculate_conversion_metrics(entity, seed_data, genes)
        
        return SeedConversionResult(
            seed_data=seed_data,
            entity_type=entity_type,
            quality_level=target_quality,
            gene_count=len(genes),
            conversion_metrics=conversion_metrics,
            warnings=validation_result.get("warnings", []),
            recommendations=validation_result.get("recommendations", [])
        )
    
    def _extract_file_genes(self, file_path: str, context: Dict) -> List[SeedGene]:
        """提取文件基因"""
        genes = []
        
        try:
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 提取文件基本信息基因
            file_info_gene = SeedGene(
                gene_id="file_info",
                gene_type="metadata",
                content={
                    "file_path": file_path,
                    "file_size": len(content),
                    "file_extension": Path(file_path).suffix,
                    "line_count": content.count('\n') + 1
                },
                importance=0.8
            )
            genes.append(file_info_gene)
            
            # 提取代码结构基因（如果是代码文件）
            if self._is_code_file(file_path):
                structure_genes = self._extract_code_structure_genes(content, file_path)
                genes.extend(structure_genes)
            
            # 提取语义基因
            semantic_genes = self._extract_semantic_genes(content, file_path)
            genes.extend(semantic_genes)
            
        except Exception as e:
            # 创建错误基因
            error_gene = SeedGene(
                gene_id="extraction_error",
                gene_type="error",
                content={"error": str(e), "file_path": file_path},
                importance=0.1
            )
            genes.append(error_gene)
        
        return genes
    
    def _extract_project_genes(self, project_path: str, context: Dict) -> List[SeedGene]:
        """提取项目基因"""
        genes = []
        
        # 项目结构基因
        structure_gene = SeedGene(
            gene_id="project_structure",
            gene_type="structure",
            content=self._analyze_project_structure(project_path),
            importance=0.9
        )
        genes.append(structure_gene)
        
        # 依赖关系基因
        dependencies_gene = SeedGene(
            gene_id="dependencies",
            gene_type="dependencies",
            content=self._extract_project_dependencies(project_path),
            importance=0.7
        )
        genes.append(dependencies_gene)
        
        # 配置基因
        config_gene = SeedGene(
            gene_id="configuration",
            gene_type="config",
            content=self._extract_project_config(project_path),
            importance=0.6
        )
        genes.append(config_gene)
        
        return genes
    
    def _extract_skill_genes(self, skill_data: Any, context: Dict) -> List[SeedGene]:
        """提取技能基因"""
        genes = []
        
        # 技能定义基因
        definition_gene = SeedGene(
            gene_id="skill_definition",
            gene_type="definition",
            content={
                "name": skill_data.get("name", "unknown"),
                "description": skill_data.get("description", ""),
                "category": skill_data.get("category", "general")
            },
            importance=0.9
        )
        genes.append(definition_gene)
        
        # 能力基因
        capability_gene = SeedGene(
            gene_id="capabilities",
            gene_type="capability",
            content=skill_data.get("capabilities", []),
            importance=0.8
        )
        genes.append(capability_gene)
        
        # 执行逻辑基因
        if "implementation" in skill_data:
            implementation_gene = SeedGene(
                gene_id="implementation",
                gene_type="implementation",
                content=skill_data["implementation"],
                importance=0.7
            )
            genes.append(implementation_gene)
        
        return genes
    
    def _extract_concept_genes(self, concept_data: Any, context: Dict) -> List[SeedGene]:
        """提取概念基因"""
        genes = []
        
        # 概念定义基因
        definition_gene = SeedGene(
            gene_id="concept_definition",
            gene_type="definition",
            content={
                "name": concept_data.get("name", "unknown"),
                "description": concept_data.get("description", ""),
                "category": concept_data.get("category", "abstract")
            },
            importance=0.9
        )
        genes.append(definition_gene)
        
        # 关系基因
        relationships_gene = SeedGene(
            gene_id="relationships",
            gene_type="relationship",
            content=concept_data.get("relationships", {}),
            importance=0.7
        )
        genes.append(relationships_gene)
        
        # 示例基因
        examples_gene = SeedGene(
            gene_id="examples",
            gene_type="example",
            content=concept_data.get("examples", []),
            importance=0.6
        )
        genes.append(examples_gene)
        
        return genes
    
    def _extract_workflow_genes(self, workflow_data: Any, context: Dict) -> List[SeedGene]:
        """提取工作流基因"""
        genes = []
        
        # 工作流定义基因
        definition_gene = SeedGene(
            gene_id="workflow_definition",
            gene_type="definition",
            content={
                "name": workflow_data.get("name", "unknown"),
                "description": workflow_data.get("description", ""),
                "steps": workflow_data.get("steps", [])
            },
            importance=0.9
        )
        genes.append(definition_gene)
        
        # 执行逻辑基因
        logic_gene = SeedGene(
            gene_id="execution_logic",
            gene_type="logic",
            content=workflow_data.get("logic", {}),
            importance=0.8
        )
        genes.append(logic_gene)
        
        # 条件基因
        conditions_gene = SeedGene(
            gene_id="conditions",
            gene_type="condition",
            content=workflow_data.get("conditions", {}),
            importance=0.7
        )
        genes.append(conditions_gene)
        
        return genes
    
    def _extract_dataset_genes(self, dataset_data: Any, context: Dict) -> List[SeedGene]:
        """提取数据集基因"""
        genes = []
        
        # 数据集元数据基因
        metadata_gene = SeedGene(
            gene_id="dataset_metadata",
            gene_type="metadata",
            content={
                "name": dataset_data.get("name", "unknown"),
                "size": dataset_data.get("size", 0),
                "format": dataset_data.get("format", "unknown"),
                "schema": dataset_data.get("schema", {})
            },
            importance=0.9
        )
        genes.append(metadata_gene)
        
        # 统计基因
        stats_gene = SeedGene(
            gene_id="statistics",
            gene_type="statistics",
            content=dataset_data.get("statistics", {}),
            importance=0.7
        )
        genes.append(stats_gene)
        
        return genes
    
    def _extract_model_genes(self, model_data: Any, context: Dict) -> List[SeedGene]:
        """提取模型基因"""
        genes = []
        
        # 模型定义基因
        definition_gene = SeedGene(
            gene_id="model_definition",
            gene_type="definition",
            content={
                "name": model_data.get("name", "unknown"),
                "type": model_data.get("type", "unknown"),
                "architecture": model_data.get("architecture", {})
            },
            importance=0.9
        )
        genes.append(definition_gene)
        
        # 参数基因
        parameters_gene = SeedGene(
            gene_id="parameters",
            gene_type="parameters",
            content=model_data.get("parameters", {}),
            importance=0.8
        )
        genes.append(parameters_gene)
        
        # 性能基因
        performance_gene = SeedGene(
            gene_id="performance",
            gene_type="performance",
            content=model_data.get("performance", {}),
            importance=0.7
        )
        genes.append(performance_gene)
        
        return genes
    
    def _is_code_file(self, file_path: str) -> bool:
        """判断是否为代码文件"""
        code_extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs', '.php'}
        return Path(file_path).suffix.lower() in code_extensions
    
    def _extract_code_structure_genes(self, content: str, file_path: str) -> List[SeedGene]:
        """提取代码结构基因"""
        genes = []
        
        # 函数定义基因
        function_patterns = {
            'python': r'def\s+(\w+)\s*\(',
            'javascript': r'function\s+(\w+)\s*\(',
            'java': r'(public|private|protected)\s+\w+\s+(\w+)\s*\('
        }
        
        # 根据文件类型选择模式
        file_ext = Path(file_path).suffix.lower()
        if file_ext == '.py':
            pattern = function_patterns['python']
        elif file_ext in ['.js', '.ts']:
            pattern = function_patterns['javascript']
        elif file_ext == '.java':
            pattern = function_patterns['java']
        else:
            pattern = r'\b(?:def|function)\s+(\w+)\s*\('
        
        functions = re.findall(pattern, content)
        if functions:
            function_gene = SeedGene(
                gene_id="functions",
                gene_type="structure",
                content=functions,
                importance=0.7
            )
            genes.append(function_gene)
        
        # 类定义基因
        class_pattern = r'class\s+(\w+)'
        classes = re.findall(class_pattern, content)
        if classes:
            class_gene = SeedGene(
                gene_id="classes",
                gene_type="structure",
                content=classes,
                importance=0.8
            )
            genes.append(class_gene)
        
        return genes
    
    def _extract_semantic_genes(self, content: str, file_path: str) -> List[SeedGene]:
        """提取语义基因"""
        genes = []
        
        # 注释基因
        comment_patterns = {
            'single_line': r'#\s*(.+)',
            'multi_line': r'"""([\s\S]*?)"""|\'\'\'([\s\S]*?)\'''
        }
        
        single_line_comments = re.findall(comment_patterns['single_line'], content)
        multi_line_comments = re.findall(comment_patterns['multi_line'], content)
        
        comments = single_line_comments + [cmt for group in multi_line_comments for cmt in group if cmt]
        
        if comments:
            comment_gene = SeedGene(
                gene_id="comments",
                gene_type="semantic",
                content=comments,
                importance=0.6
            )
            genes.append(comment_gene)
        
        # 导入/包含基因
        import_pattern = r'(?:import|from|require|include)\s+[^;\n]+'
        imports = re.findall(import_pattern, content)
        
        if imports:
            import_gene = SeedGene(
                gene_id="imports",
                gene_type="dependency",
                content=imports,
                importance=0.5
            )
            genes.append(import_gene)
        
        return genes
    
    def _analyze_project_structure(self, project_path: str) -> Dict:
        """分析项目结构"""
        structure = {"files": [], "directories": []}
        
        try:
            for root, dirs, files in os.walk(project_path):
                # 记录目录
                for d in dirs:
                    structure["directories"].append(os.path.join(root, d))
                
                # 记录文件
                for f in files:
                    structure["files"].append({
                        "path": os.path.join(root, f),
                        "size": os.path.getsize(os.path.join(root, f))
                    })
        except:
            pass
        
        return structure
    
    def _extract_project_dependencies(self, project_path: str) -> Dict:
        """提取项目依赖"""
        dependencies = {}
        
        # 检查常见的依赖文件
        dependency_files = {
            "requirements.txt": "python",
            "package.json": "javascript",
            "pom.xml": "java",
            "build.gradle": "java",
            "Cargo.toml": "rust",
            "go.mod": "go"
        }
        
        for file_name, language in dependency_files.items():
            file_path = os.path.join(project_path, file_name)
            if os.path.exists(file_path):
                dependencies[language] = {"file": file_name, "exists": True}
        
        return dependencies
    
    def _extract_project_config(self, project_path: str) -> Dict:
        """提取项目配置"""
        config = {}
        
        # 检查常见的配置文件
        config_files = ["config.json", "settings.py", ".env", "config.yaml", "config.yml"]
        
        for file_name in config_files:
            file_path = os.path.join(project_path, file_name)
            if os.path.exists(file_path):
                config[file_name] = {"exists": True, "path": file_path}
        
        return config
    
    def _build_seed_data(self, template: Dict, genes: List[SeedGene], 
                        entity_type: SeedableEntityType, context: Dict) -> Dict:
        """构建种子数据"""
        seed_data = template.copy()
        
        # 添加基因数据
        seed_data["genes"] = {}
        for gene in genes:
            seed_data["genes"][gene.gene_id] = {
                "type": gene.gene_type,
                "content": gene.content,
                "importance": gene.importance,
                "dependencies": gene.dependencies,
                "metadata": gene.metadata
            }
        
        # 添加实体类型信息
        seed_data["entity_type"] = entity_type.value
        seed_data["conversion_context"] = context
        seed_data["conversion_timestamp"] = self._get_timestamp()
        
        return seed_data
    
    def _validate_basic_quality(self, seed_data: Dict, genes: List[SeedGene]) -> Dict:
        """验证基础质量"""
        warnings = []
        recommendations = []
        
        # 检查核心基因完整性
        core_genes_present = any(gene.importance >= 0.8 for gene in genes)
        if not core_genes_present:
            warnings.append("缺少核心基因（重要性>=0.8）")
        
        # 检查基因数量
        if len(genes) < 3:
            warnings.append("基因数量过少，可能无法完整表达实体特征")
        
        return {"warnings": warnings, "recommendations": recommendations}
    
    def _validate_standard_quality(self, seed_data: Dict, genes: List[SeedGene]) -> Dict:
        """验证标准质量"""
        result = self._validate_basic_quality(seed_data, genes)
        
        # 检查可执行性基因
        executable_genes = [gene for gene in genes if gene.gene_type in ["implementation", "logic"]]
        if not executable_genes:
            result["warnings"].append("缺少可执行性基因")
        
        return result
    
    def _validate_premium_quality(self, seed_data: Dict, genes: List[SeedGene]) -> Dict:
        """验证优质质量"""
        result = self._validate_standard_quality(seed_data, genes)
        
        # 检查进化性基因
        evolutionary_genes = [gene for gene in genes if gene.gene_type in ["relationship", "dependency"]]
        if len(evolutionary_genes) < 2:
            result["warnings"].append("进化性基因不足")
        
        return result
    
    def _validate_excellent_quality(self, seed_data: Dict, genes: List[SeedGene]) -> Dict:
        """验证优秀质量"""
        result = self._validate_premium_quality(seed_data, genes)
        
        # 检查传承性基因
        heritage_genes = [gene for gene in genes if gene.gene_type in ["semantic", "example"]]
        if len(heritage_genes) < 3:
            result["warnings"].append("传承性基因不足")
        
        return result
    
    def _calculate_conversion_metrics(self, original_entity: Any, seed_data: Dict, genes: List[SeedGene]) -> Dict:
        """计算转换指标"""
        return {
            "gene_count": len(genes),
            "average_importance": sum(gene.importance for gene in genes) / len(genes) if genes else 0,
            "gene_type_diversity": len(set(gene.gene_type for gene in genes)),
            "seed_size": len(json.dumps(seed_data, ensure_ascii=False))
        }
    
    def _get_timestamp(self) -> str:
        """获取时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    # 种子模板创建方法
    def _create_file_seed_template(self) -> Dict:
        return {
            "seed_type": "file",
            "version": "1.0",
            "framework": "prometheus",
            "genes": {}
        }
    
    def _create_project_seed_template(self) -> Dict:
        return {
            "seed_type": "project", 
            "version": "1.0",
            "framework": "prometheus",
            "genes": {}
        }
    
    def _create_skill_seed_template(self) -> Dict:
        return {
            "seed_type": "skill",
            "version": "1.0", 
            "framework": "prometheus",
            "genes": {}
        }
    
    def _create_concept_seed_template(self) -> Dict:
        return {
            "seed_type": "concept",
            "version": "1.0",
            "framework": "prometheus", 
            "genes": {}
        }
    
    def _create_workflow_seed_template(self) -> Dict:
        return {
            "seed_type": "workflow",
            "version": "1.0",
            "framework": "prometheus",
            "genes": {}
        }
    
    def _create_dataset_seed_template(self) -> Dict:
        return {
            "seed_type": "dataset", 
            "version": "1.0",
            "framework": "prometheus",
            "genes": {}
        }
    
    def _create_model_seed_template(self) -> Dict:
        return {
            "seed_type": "model",
            "version": "1.0",
            "framework": "prometheus", 
            "genes": {}
        }


# 使用示例
def demonstrate_seed_conversion():
    """演示种子转换"""
    converter = UniversalSeedConverter()
    
    # 示例：文件种子化
    print("=== 文件种子化演示 ===")
    
    # 创建一个示例文件
    sample_file_content = """
    # 用户服务模块
    class UserService:
        def get_user(self, user_id):
            '''根据用户ID获取用户信息'''
            return self.db.query(User).filter(User.id == user_id).first()
        
        def update_user(self, user_id, data):
            '''更新用户信息'''
            user = self.get_user(user_id)
            for key, value in data.items():
                setattr(user, key, value)
            self.db.commit()
    
    # 配置信息
    config = {
        'database_url': 'postgresql://localhost:5432/app',
        'cache_timeout': 3600
    }
    """
    
    # 写入临时文件
    temp_file = "/tmp/sample_user_service.py"
    with open(temp_file, 'w') as f:
        f.write(sample_file_content)
    
    # 转换为种子
    result = converter.convert_to_seed(
        temp_file, 
        SeedableEntityType.FILE, 
        SeedQualityLevel.STANDARD
    )
    
    print(f"实体类型: {result.entity_type.value}")
    print(f"质量等级: {result.quality_level.value}")
    print(f"基因数量: {result.gene_count}")
    print(f"转换指标: {result.conversion_metrics}")
    
    if result.warnings:
        print(f"警告: {result.warnings}")
    
    if result.recommendations:
        print(f"建议: {result.recommendations}")
    
    # 清理临时文件
    os.unlink(temp_file)


if __name__ == "__main__":
    demonstrate_seed_conversion()