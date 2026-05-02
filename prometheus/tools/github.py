"""
Prometheus GitHub 搜索工具
使用 curl 直接调用 GitHub API，对标 Prometheus 的实现方式
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

from .registry import registry, tool_error, tool_result


def github_search_repos(
    query: str,
    sort: str = "stars",
    order: str = "desc",
    per_page: int = 10,
) -> dict[str, Any]:
    """
    搜索 GitHub 仓库

    Args:
        query: 搜索关键词
        sort: 排序方式（stars/forks/updated）
        order: 排序顺序（asc/desc）
        per_page: 返回结果数量

    Returns:
        包含仓库列表的字典
    """
    try:
        encoded_query = query.replace(" ", "+")
        url = (
            f"https://api.github.com/search/repositories"
            f"?q={encoded_query}&sort={sort}&order={order}&per_page={per_page}"
        )

        cmd = [
            "curl",
            "-s",
            "-H", "Accept: application/vnd.github.v3+json",
            url,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return tool_error(f"curl 执行失败: {result.stderr}")

        data = json.loads(result.stdout)

        if "items" not in data:
            return tool_error(f"GitHub API 返回异常: {data}")

        repos = []
        for item in data["items"][:per_page]:
            repos.append({
                "name": item["full_name"],
                "description": item.get("description", ""),
                "stars": item["stargazers_count"],
                "forks": item["forks_count"],
                "language": item.get("language", ""),
                "url": item["html_url"],
                "updated_at": item.get("updated_at", ""),
            })

        return tool_result({
            "total_count": data.get("total_count", 0),
            "repos": repos,
        })

    except subprocess.TimeoutExpired:
        return tool_error("请求超时")
    except json.JSONDecodeError:
        return tool_error("JSON 解析失败")
    except Exception as e:
        return tool_error(f"搜索失败: {str(e)}")


def github_get_repo(owner: str, repo: str) -> dict[str, Any]:
    """
    获取 GitHub 仓库详情

    Args:
        owner: 仓库所有者
        repo: 仓库名称

    Returns:
        仓库详情字典
    """
    try:
        url = f"https://api.github.com/repos/{owner}/{repo}"

        cmd = [
            "curl",
            "-s",
            "-H", "Accept: application/vnd.github.v3+json",
            url,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return tool_error(f"curl 执行失败: {result.stderr}")

        data = json.loads(result.stdout)

        if "message" in data and data["message"].startswith("Not Found"):
            return tool_error(f"仓库不存在: {owner}/{repo}")

        return tool_result({
            "name": data["full_name"],
            "description": data.get("description", ""),
            "stars": data["stargazers_count"],
            "forks": data["forks_count"],
            "language": data.get("language", ""),
            "url": data["html_url"],
            "created_at": data.get("created_at", ""),
            "updated_at": data.get("updated_at", ""),
            "topics": data.get("topics", []),
        })

    except subprocess.TimeoutExpired:
        return tool_error("请求超时")
    except json.JSONDecodeError:
        return tool_error("JSON 解析失败")
    except Exception as e:
        return tool_error(f"获取失败: {str(e)}")


def github_search_code(
    query: str,
    per_page: int = 10,
) -> dict[str, Any]:
    """
    搜索 GitHub 代码

    Args:
        query: 搜索关键词
        per_page: 返回结果数量

    Returns:
        代码搜索结果字典
    """
    try:
        encoded_query = query.replace(" ", "+")
        url = (
            f"https://api.github.com/search/code"
            f"?q={encoded_query}&per_page={per_page}"
        )

        cmd = [
            "curl",
            "-s",
            "-H", "Accept: application/vnd.github.v3+json",
            url,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return tool_error(f"curl 执行失败: {result.stderr}")

        data = json.loads(result.stdout)

        if "items" not in data:
            return tool_error(f"GitHub API 返回异常: {data}")

        results = []
        for item in data["items"][:per_page]:
            results.append({
                "name": item["name"],
                "path": item["path"],
                "repository": item["repository"]["full_name"],
                "url": item["html_url"],
            })

        return tool_result({
            "total_count": data.get("total_count", 0),
            "results": results,
        })

    except subprocess.TimeoutExpired:
        return tool_error("请求超时")
    except json.JSONDecodeError:
        return tool_error("JSON 解析失败")
    except Exception as e:
        return tool_error(f"搜索失败: {str(e)}")


GITHUB_SEARCH_REPOS_SCHEMA = {
    "name": "github_search_repos",
    "description": "搜索 GitHub 仓库，使用 GitHub API 直接调用",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词，例如 'agent memory management'",
            },
            "sort": {
                "type": "string",
                "description": "排序方式（stars/forks/updated）",
                "default": "stars",
            },
            "order": {
                "type": "string",
                "description": "排序顺序（asc/desc）",
                "default": "desc",
            },
            "per_page": {
                "type": "integer",
                "description": "返回结果数量",
                "default": 10,
            },
        },
        "required": ["query"],
    },
}

GITHUB_GET_REPO_SCHEMA = {
    "name": "github_get_repo",
    "description": "获取 GitHub 仓库详情",
    "parameters": {
        "type": "object",
        "properties": {
            "owner": {
                "type": "string",
                "description": "仓库所有者，例如 'langchain-ai'",
            },
            "repo": {
                "type": "string",
                "description": "仓库名称，例如 'langchain'",
            },
        },
        "required": ["owner", "repo"],
    },
}

GITHUB_SEARCH_CODE_SCHEMA = {
    "name": "github_search_code",
    "description": "搜索 GitHub 代码",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词",
            },
            "per_page": {
                "type": "integer",
                "description": "返回结果数量",
                "default": 10,
            },
        },
        "required": ["query"],
    },
}

registry.register(
    name="github_search_repos",
    toolset="github",
    schema=GITHUB_SEARCH_REPOS_SCHEMA,
    handler=lambda args, **kw: github_search_repos(
        query=args.get("query", ""),
        sort=args.get("sort", "stars"),
        order=args.get("order", "desc"),
        per_page=args.get("per_page", 10),
    ),
    emoji="🔍",
)

registry.register(
    name="github_get_repo",
    toolset="github",
    schema=GITHUB_GET_REPO_SCHEMA,
    handler=lambda args, **kw: github_get_repo(
        owner=args.get("owner", ""),
        repo=args.get("repo", ""),
    ),
    emoji="📦",
)

registry.register(
    name="github_search_code",
    toolset="github",
    schema=GITHUB_SEARCH_CODE_SCHEMA,
    handler=lambda args, **kw: github_search_code(
        query=args.get("query", ""),
        per_page=args.get("per_page", 10),
    ),
    emoji="💻",
)
