#!/usr/bin/env python3
"""
星门阵列连通性诊断工具
用于测试 Progenitor 星门通道的可用性
"""

import sys
import time
from urllib import request, error

DEFAULT_GATEWAYS = [
    "https://raw.githubusercontent.com/Audrey-cn/progenitor-registry/main/genes/",
    "https://ghproxy.com/https://raw.githubusercontent.com/Audrey-cn/progenitor-registry/main/genes/",
    "https://mirror.ghproxy.com/https://raw.githubusercontent.com/Audrey-cn/progenitor-registry/main/genes/",
    "https://ipfs.io/ipfs/",
    "https://dweb.link/ipfs/",
    "https://cloudflare-ipfs.com/ipfs/",
]

AKASHIC_INDEX = "https://raw.githubusercontent.com/Audrey-cn/progenitor-registry/main/.akashic_index.json"


def test_gateway(gateway_url, timeout=10):
    """测试单个网关连通性"""
    start = time.perf_counter()
    try:
        req = request.Request(gateway_url)
        with request.urlopen(req, timeout=timeout) as resp:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return {
                "gateway": gateway_url,
                "status": "✅ ONLINE",
                "response_ms": elapsed_ms,
                "status_code": resp.status,
            }
    except error.HTTPError as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return {
            "gateway": gateway_url,
            "status": f"⚠️ HTTP {e.code}",
            "response_ms": elapsed_ms,
            "error": str(e),
        }
    except error.URLError as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return {
            "gateway": gateway_url,
            "status": "❌ UNREACHABLE",
            "response_ms": elapsed_ms,
            "error": str(e),
        }
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return {
            "gateway": gateway_url,
            "status": f"❌ ERROR",
            "response_ms": elapsed_ms,
            "error": str(e),
        }


def test_akashic_index():
    """测试阿卡夏索引获取"""
    return test_gateway(AKASHIC_INDEX)


def main():
    print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
     🌌 Progenitor 星门阵列连通性诊断
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """)

    print("📡 测试星门通道...")
    results = []

    for i, gateway in enumerate(DEFAULT_GATEWAYS, 1):
        print(f"\n[{i}/{len(DEFAULT_GATEWAYS)}] 测试: {gateway[:60]}...")
        result = test_gateway(gateway)
        results.append(result)
        print(f"    {result['status']} ({result.get('response_ms', 0):.1f}ms)")

    print("\n\n📖 测试阿卡夏索引...")
    index_result = test_akashic_index()
    results.append(index_result)
    print(f"    {index_result['status']} ({index_result.get('response_ms', 0):.1f}ms)")

    print("\n" + "=" * 80)
    print("📊 汇总")
    print("=" * 80)

    online = sum(1 for r in results if "✅" in r["status"])
    warning = sum(1 for r in results if "⚠️" in r["status"])
    failed = sum(1 for r in results if "❌" in r["status"])

    print(f"  ✅ 在线: {online}")
    print(f"  ⚠️ 受限: {warning}")
    print(f"  ❌ 失败: {failed}")
    print("=" * 80)

    if online >= 2:
        print("\n🎉 星门阵列状态：良好！至少 2 个网关可用。")
    elif online == 1:
        print("\n⚠️ 星门阵列状态：降级运行，仅 1 个网关可用。")
    else:
        print("\n🔴 星门阵列状态：危急！所有网关均不可用。")

    return 0 if online >= 1 else 1


if __name__ == "__main__":
    sys.exit(main())
