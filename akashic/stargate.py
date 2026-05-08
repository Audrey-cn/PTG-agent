"""
[Shared Module] 星门阵列工具 - 统一的星门轮询逻辑

此模块提供统一的星门交互接口，消除 protocol 和 akashic 之间的代码重复。
"""

import time
from urllib import request
from typing import List


def fetch_from_stargates(cid: str, stargate_array: List[str],
                         timeout_sec: int = 15, retry_policy: dict = None) -> bytes:
    """
    遍历星门阵列，从远端拉取基因数据。

    Args:
        cid: 内容标识符
        stargate_array: 星门URL列表
        timeout_sec: 超时时间
        retry_policy: 重试策略 {"max_retries": int, "backoff_factor": float}

    Returns:
        基因数据字节流

    Raises:
        RuntimeError: 所有星门都失败时
    """
    retry_policy = retry_policy or {"max_retries": 3, "backoff_factor": 1.0}

    for gateway in stargate_array:
        for attempt in range(retry_policy["max_retries"] + 1):
            try:
                url = f"{gateway.rstrip('/')}/{cid.strip()}"
                req = request.Request(url, timeout=timeout_sec)
                with request.urlopen(req) as response:
                    return response.read()
            except Exception as e:
                if attempt < retry_policy["max_retries"]:
                    delay = retry_policy["backoff_factor"] * (2 ** attempt)
                    time.sleep(delay)
                else:
                    pass
        continue

    raise RuntimeError(f"所有星门均无法访问 CID: {cid}")