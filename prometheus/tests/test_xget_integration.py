#!/usr/bin/env python3
"""
Xget 集成模块测试
"""

import unittest
import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.xget_integration import (
    XgetIntegration,
    Platform,
    get_xget,
    xget_convert,
)


class TestXgetIntegration(unittest.TestCase):
    """Xget 集成模块测试"""

    def setUp(self):
        """测试前准备"""
        self.config = {
            "enabled": True,
            "default_instance": "https://xget.xi-xu.me",
            "fallback_enabled": True,
            "request_timeout_seconds": 10,
            "max_retries": 2,
            "retry_delay_seconds": 0.5,
            "instances": [
                {"url": "https://xget.xi-xu.me", "priority": 0, "weight": 3},
            ],
        }
        self.xget = XgetIntegration(self.config)

    def test_identify_github_platform(self):
        """测试识别 GitHub 平台"""
        url = "https://github.com/xixu-me/xget"
        platform, config = self.xget.identify_platform(url)
        self.assertEqual(platform, Platform.GITHUB)
        self.assertIsNotNone(config)

    def test_identify_huggingface_platform(self):
        """测试识别 Hugging Face 平台"""
        url = "https://huggingface.co/bert-base-uncased"
        platform, config = self.xget.identify_platform(url)
        self.assertEqual(platform, Platform.HUGGING_FACE)
        self.assertIsNotNone(config)

    def test_identify_unknown_platform(self):
        """测试识别未知平台"""
        url = "https://example.com/test"
        platform, config = self.xget.identify_platform(url)
        self.assertIsNone(platform)
        self.assertIsNone(config)

    def test_convert_github_url(self):
        """测试转换 GitHub URL"""
        url = "https://github.com/xixu-me/xget"
        converted = self.xget.convert_url(url)
        self.assertIsNotNone(converted)
        self.assertIn("xget.xi-xu.me", converted)
        self.assertIn("xixu-me/xget", converted)

    def test_convert_huggingface_url(self):
        """测试转换 Hugging Face URL"""
        url = "https://huggingface.co/bert-base-uncased"
        converted = self.xget.convert_url(url)
        self.assertIsNotNone(converted)
        self.assertIn("xget.xi-xu.me", converted)
        self.assertIn("bert-base-uncased", converted)

    def test_convert_unknown_url(self):
        """测试转换未知平台 URL"""
        url = "https://example.com/test"
        converted = self.xget.convert_url(url)
        self.assertIsNone(converted)

    def test_select_instance(self):
        """测试选择实例"""
        instance = self.xget.select_instance()
        self.assertIsNotNone(instance)
        self.assertEqual(instance.url, "https://xget.xi-xu.me")

    def test_get_status(self):
        """测试获取状态"""
        status = self.xget.get_status()
        self.assertIn("enabled", status)
        self.assertIn("instances", status)
        self.assertIn("platforms", status)
        self.assertTrue(status["enabled"])

    def test_singleton(self):
        """测试单例模式"""
        xget1 = get_xget()
        xget2 = get_xget()
        self.assertIs(xget1, xget2)

    def test_convenience_function(self):
        """测试便捷函数"""
        url = "https://github.com/xixu-me/xget"
        converted = xget_convert(url)
        self.assertIsNotNone(converted)


class TestXgetIntegrationAsync(unittest.IsolatedAsyncioTestCase):
    """Xget 集成模块异步测试"""

    async def asyncSetUp(self):
        """异步测试前准备"""
        self.config = {
            "enabled": True,
            "default_instance": "https://xget.xi-xu.me",
            "fallback_enabled": True,
            "request_timeout_seconds": 5,
            "max_retries": 1,
            "retry_delay_seconds": 0.1,
            "instances": [
                {"url": "https://xget.xi-xu.me", "priority": 0, "weight": 3},
            ],
        }
        self.xget = XgetIntegration(self.config)

    async def test_request_with_fallback(self):
        """测试请求（可能会 fallback）"""
        # 使用一个简单的 URL 测试
        url = "https://github.com/xixu-me/xget"
        result = await self.xget.request(url)
        self.assertIsNotNone(result)
        # 我们不假设一定成功，因为网络可能不稳定
        # 但结果对象应该存在
        self.assertIn("success", dir(result))
        self.assertIn("url", dir(result))

    async def test_request_direct_fallback(self):
        """测试禁用 Xget 时的直接请求"""
        config = self.config.copy()
        config["enabled"] = False
        xget_disabled = XgetIntegration(config)
        url = "https://github.com/xixu-me/xget"
        result = await xget_disabled.request(url)
        self.assertIsNotNone(result)
        self.assertFalse(result.fallback_used)  # 因为 Xget 被禁用，直接请求


def run_tests():
    """运行测试"""
    # 同步测试
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestXgetIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestXgetIntegrationAsync))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
