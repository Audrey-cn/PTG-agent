#!/usr/bin/env python3
"""综合代码审查测试"""

import sys
import tempfile
from pathlib import Path

print('Python版本:', sys.version)
print()

# 1. 验证核心模块导入
print('=== 1. 核心模块导入测试 ===')
try:
    from prometheus.config import (
        PrometheusConfig, load_config, save_config,
        migrate_json_to_yaml, DEFAULT_CONFIG, cfg_get
    )
    print('✓ prometheus.config 导入成功')
except Exception as e:
    print(f'✗ prometheus.config 导入失败: {e}')
    sys.exit(1)

try:
    from prometheus.cli.config import (
        PrometheusConfig as CLI_PrometheusConfig,
        load_config as CLI_load_config,
        save_config as CLI_save_config
    )
    print('✓ prometheus.cli.config 导入成功')
except Exception as e:
    print(f'✗ prometheus.cli.config 导入失败: {e}')
    sys.exit(1)

try:
    from prometheus.agent.lazy_imports import LazyModule, LazyClass, lazy_import
    print('✓ prometheus.agent.lazy_imports 导入成功')
except Exception as e:
    print(f'✗ prometheus.agent.lazy_imports 导入失败: {e}')
    sys.exit(1)

# 2. 验证主模块导出
print()
print('=== 2. 主模块导出测试 ===')
import prometheus
print(f'prometheus.PrometheusConfig: {hasattr(prometheus, "PrometheusConfig")}')
print(f'prometheus.load_config: {hasattr(prometheus, "load_config")}')
print(f'prometheus.save_config: {hasattr(prometheus, "save_config")}')

# 3. 验证配置类功能
print()
print('=== 3. 配置类功能测试 ===')
import yaml

with tempfile.TemporaryDirectory() as tmpdir:
    config_path = Path(tmpdir) / 'config.yaml'
    
    # 测试加载
    config = PrometheusConfig.load(path=config_path)
    assert config.get('model.name') == '', '默认值应该为空字符串'
    print('✓ 加载默认配置成功')
    
    # 测试设置
    config.set('model.name', 'gpt-4')
    assert config.get('model.name') == 'gpt-4'
    print('✓ 设置配置值成功')
    
    # 测试保存
    config.save()
    assert config_path.exists()
    print('✓ 保存配置成功')
    
    # 验证文件格式为 YAML
    with open(config_path, 'r') as f:
        content = f.read()
    assert 'name: gpt-4' in content
    print('✓ 文件格式为 YAML')
    
    # 测试加载已保存的配置
    config2 = PrometheusConfig.load(path=config_path)
    assert config2.get('model.name') == 'gpt-4'
    print('✓ 重新加载配置成功')

# 4. 验证兼容性函数
print()
print('=== 4. 兼容性函数测试 ===')
import prometheus.config as config_mod

with tempfile.TemporaryDirectory() as tmpdir:
    config_path = Path(tmpdir) / 'config.yaml'
    original_func = config_mod.get_config_path
    config_mod.get_config_path = lambda: config_path
    
    try:
        # 测试 load_config()
        cfg = load_config()
        assert isinstance(cfg, dict)
        assert 'model' in cfg
        print('✓ load_config() 返回正确的字典')
        
        # 测试 save_config()
        save_config({'model': {'name': 'test'}})
        with open(config_path, 'r') as f:
            loaded = yaml.safe_load(f)
        assert loaded['model']['name'] == 'test'
        assert '_config_version' in loaded  # 应该合并默认值
        print('✓ save_config() 保存为 YAML 并合并默认值')
    finally:
        config_mod.get_config_path = original_func

# 5. 验证验证功能
print()
print('=== 5. 配置验证功能测试 ===')
with tempfile.TemporaryDirectory() as tmpdir:
    config_path = Path(tmpdir) / 'config.yaml'
    config = PrometheusConfig.load(path=config_path)
    
    errors = config.validate()
    assert len(errors) == 0, f'默认配置应该验证通过，但得到: {errors}'
    print('✓ 默认配置验证通过')
    
    # 测试无效配置
    config.set('model.temperature', 5.0)
    errors = config.validate()
    assert len(errors) > 0
    assert any('temperature' in err for err in errors)
    print('✓ 无效配置被正确检测')

# 6. 验证变更监听器
print()
print('=== 6. 变更监听器测试 ===')
changes = []

def on_change(key, value):
    changes.append((key, value))

PrometheusConfig.add_change_listener(on_change)

with tempfile.TemporaryDirectory() as tmpdir:
    config_path = Path(tmpdir) / 'config.yaml'
    config = PrometheusConfig.load(path=config_path)
    config.set('model.name', 'listening-test')
    
    assert len(changes) > 0
    assert changes[0] == ('model.name', 'listening-test')
    print('✓ 变更监听器工作正常')

PrometheusConfig.remove_change_listener(on_change)

print()
print('=' * 50)
print('✅ 所有代码审查测试通过！')
print('=' * 50)
