"""
[Shared Module] 基因联邦常量 - 跨模块共享的不可变铁律

此模块包含跨项目共享的不可变常量：
- ALLOWED_LINEAGES: 允许的血脉前缀白名单
- ALLOWED_CREATORS: 允许的创造者白名单

零依赖，仅使用 Python 标准库。
"""

import os

ALLOWED_LINEAGES_ENV = os.environ.get(
    "PROGENITOR_ALLOWED_LINEAGES",
    "PGN@"
)

ALLOWED_CREATORS_ENV = os.environ.get(
    "PROGENITOR_ALLOWED_CREATORS",
    "Audrey"
)

ALLOWED_LINEAGES = [x.strip() for x in ALLOWED_LINEAGES_ENV.split(",") if x.strip()]
ALLOWED_CREATORS = [x.strip() for x in ALLOWED_CREATORS_ENV.split(",") if x.strip()]