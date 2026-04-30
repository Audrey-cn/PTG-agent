#!/usr/bin/env python3
"""
混合存储系统测试
"""

import os
import sys
import unittest
import tempfile
import shutil
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.storage import HybridStorage, MemoryRecord
from memory.sync import SyncManager
from memory.backup import BackupManager
from memory.context import ContextManager
from memory.knowledge import CompiledKnowledgeManager


class TestHybridStorage(unittest.TestCase):
    """混合存储测试"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.storage = HybridStorage(data_dir=self.temp_dir)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_save_and_load(self):
        """测试保存和加载"""
        record = MemoryRecord(
            memory_id="",
            content="测试内容",
            layer="working",
            importance=0.8,
            source="test",
            tags=["test", "unit"],
        )
        
        memory_id = self.storage.save(record)
        self.assertTrue(memory_id.startswith("mem_"))
        
        loaded = self.storage.load(memory_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.content, "测试内容")
        self.assertEqual(loaded.layer, "working")
        self.assertEqual(loaded.importance, 0.8)
    
    def test_md_file_created(self):
        """测试 MD 文件创建"""
        record = MemoryRecord(
            memory_id="",
            content="测试 MD 文件",
            layer="working",
        )
        
        memory_id = self.storage.save(record)
        
        md_path = os.path.join(self.temp_dir, "working", f"{memory_id}.md")
        self.assertTrue(os.path.exists(md_path))
        
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        self.assertIn("---", content)
        self.assertIn("测试 MD 文件", content)
    
    def test_delete(self):
        """测试删除"""
        record = MemoryRecord(
            memory_id="",
            content="要删除的内容",
            layer="working",
        )
        
        memory_id = self.storage.save(record)
        self.assertIsNotNone(self.storage.load(memory_id))
        
        result = self.storage.delete(memory_id)
        self.assertTrue(result)
        self.assertIsNone(self.storage.load(memory_id))
    
    def test_search(self):
        """测试搜索"""
        for i in range(5):
            record = MemoryRecord(
                memory_id="",
                content=f"测试内容 {i}",
                layer="working",
                importance=0.5 + i * 0.1,
            )
            self.storage.save(record)
        
        results = self.storage.search("测试", limit=3)
        self.assertGreater(len(results), 0)


class TestSyncManager(unittest.TestCase):
    """同步管理器测试"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.storage = HybridStorage(data_dir=self.temp_dir)
        self.sync = SyncManager(storage=self.storage)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_sync_from_md(self):
        """测试从 MD 同步"""
        record = MemoryRecord(
            memory_id="test_sync_001",
            content="同步测试",
            layer="working",
        )
        self.storage._save_to_md(record)
        
        result = self.sync.sync_from_md()
        
        self.assertGreater(result["synced"], 0)
        
        loaded = self.storage._load_from_sqlite("test_sync_001")
        self.assertIsNotNone(loaded)
    
    def test_reconcile(self):
        """测试差异检测"""
        record = MemoryRecord(
            memory_id="test_reconcile_001",
            content="差异测试",
            layer="working",
        )
        self.storage._save_to_md(record)
        
        diff = self.sync.reconcile()
        
        self.assertIn("test_reconcile_001", diff["md_only"])


class TestBackupManager(unittest.TestCase):
    """备份管理器测试"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = os.path.join(self.temp_dir, "data")
        os.makedirs(self.data_dir)
        
        test_file = os.path.join(self.data_dir, "test.txt")
        with open(test_file, 'w') as f:
            f.write("test content")
        
        self.backup = BackupManager(data_dir=self.data_dir)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_backup_hourly(self):
        """测试每小时备份"""
        info = self.backup.backup_hourly()
        
        self.assertIsNotNone(info)
        self.assertEqual(info.backup_type, "hourly")
        self.assertTrue(os.path.exists(info.path))
    
    def test_backup_daily(self):
        """测试每日备份"""
        info = self.backup.backup_daily()
        
        self.assertIsNotNone(info)
        self.assertEqual(info.backup_type, "daily")
    
    def test_backup_manual(self):
        """测试手动备份"""
        info = self.backup.backup_manual("test_backup")
        
        self.assertIsNotNone(info)
        self.assertEqual(info.backup_type, "manual")
        self.assertIn("test_backup", info.name)
    
    def test_list_backups(self):
        """测试列出备份"""
        self.backup.backup_hourly()
        self.backup.backup_daily()
        
        backups = self.backup.list_backups()
        
        self.assertGreater(len(backups), 0)


class TestContextManager(unittest.TestCase):
    """上下文管理器测试"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.ctx = ContextManager(data_dir=self.temp_dir)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_add_and_recall(self):
        """测试添加和检索"""
        result = self.ctx.add(
            content="测试记忆",
            layer="working",
            importance=0.8,
            tags=["test"],
        )
        
        self.assertIn("id", result)
        
        memories = self.ctx.recall(query="测试")
        self.assertGreater(len(memories), 0)
    
    def test_budget_status(self):
        """测试预算状态"""
        self.ctx.add("测试内容", layer="working")
        
        status = self.ctx.budget_status()
        
        self.assertIn("working", status)
        self.assertIn("total", status)


class TestCompiledKnowledgeManager(unittest.TestCase):
    """知识管理器测试"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.km = CompiledKnowledgeManager(data_dir=self.temp_dir)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_add_source(self):
        """测试添加素材"""
        source_id = self.km.add_source(
            content="这是原始素材内容",
            title="测试素材",
            tags=["test"],
        )
        
        self.assertTrue(source_id.startswith("src_"))
    
    def test_add_knowledge(self):
        """测试添加知识"""
        entry_id = self.km.add_knowledge(
            title="测试知识",
            content="这是知识内容",
            entry_type="concept",
            maturity="draft",
        )
        
        self.assertTrue(entry_id.startswith("know_"))
    
    def test_search(self):
        """测试搜索知识"""
        self.km.add_knowledge(
            title="Python 编程",
            content="Python 是一种编程语言",
            tags=["programming"],
        )
        
        results = self.km.search("Python")
        
        self.assertGreater(len(results), 0)


def run_tests():
    """运行所有测试"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestHybridStorage))
    suite.addTests(loader.loadTestsFromTestCase(TestSyncManager))
    suite.addTests(loader.loadTestsFromTestCase(TestBackupManager))
    suite.addTests(loader.loadTestsFromTestCase(TestContextManager))
    suite.addTests(loader.loadTestsFromTestCase(TestCompiledKnowledgeManager))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
