#!/usr/bin/env python3
"""Toolset Distributions Module."""

import random

from toolsets import validate_toolset

# Distribution definitions
# Each key is a distribution name, value is dict of toolset: probability (%)
DISTRIBUTIONS = {
    # Default: All tools available 100% of the time
    "default": {
        "description": "All available tools, all the time",
        "toolsets": {
            "web": 100,
            "vision": 100,
            "image_gen": 100,
            "terminal": 100,
            "file": 100,
            "moa": 100,
            "browser": 100,
            "prometheus": 100,
        },
    },
    # Image generation focused
    "image_gen": {
        "description": "Heavy focus on image generation with vision and web support",
        "toolsets": {"image_gen": 90, "vision": 90, "web": 55, "terminal": 45, "moa": 10},
    },
    # Research-focused
    "research": {
        "description": "Web research with vision analysis and reasoning",
        "toolsets": {"web": 90, "browser": 70, "vision": 50, "moa": 40, "terminal": 10},
    },
    # Scientific problem solving focused
    "science": {
        "description": "Scientific research with web, terminal, file, and browser",
        "toolsets": {
            "web": 94,
            "terminal": 94,
            "file": 94,
            "vision": 65,
            "browser": 50,
            "image_gen": 15,
            "moa": 10,
        },
    },
    # Development-focused
    "development": {
        "description": "Terminal, file tools, and reasoning with web lookup",
        "toolsets": {
            "terminal": 80,
            "file": 80,
            "moa": 60,
            "web": 30,
            "vision": 10,
            "prometheus": 70,
        },
    },
    # Safe mode (no terminal)
    "safe": {
        "description": "All tools except terminal for safety",
        "toolsets": {
            "web": 80,
            "browser": 70,
            "vision": 60,
            "image_gen": 60,
            "moa": 50,
            "prometheus": 80,
        },
    },
    # Balanced distribution
    "balanced": {
        "description": "Equal probability of all toolsets",
        "toolsets": {
            "web": 50,
            "vision": 50,
            "image_gen": 50,
            "terminal": 50,
            "file": 50,
            "moa": 50,
            "browser": 50,
            "prometheus": 50,
        },
    },
    # Minimal (web only)
    "minimal": {"description": "Only web tools for basic research", "toolsets": {"web": 100}},
    # Terminal only
    "terminal_only": {
        "description": "Terminal and file tools for code execution tasks",
        "toolsets": {"terminal": 100, "file": 100},
    },
    # Terminal + web (for coding tasks needing docs)
    "terminal_web": {
        "description": "Terminal and file tools with web search for docs",
        "toolsets": {"terminal": 100, "file": 100, "web": 100, "prometheus": 80},
    },
    # Creative (vision + image generation)
    "creative": {
        "description": "Image generation and vision analysis focus",
        "toolsets": {"image_gen": 90, "vision": 90, "web": 30},
    },
    # Reasoning heavy
    "reasoning": {
        "description": "Heavy mixture of agents with minimal other tools",
        "toolsets": {"moa": 90, "web": 30, "terminal": 20, "prometheus": 50},
    },
    # Browser-based web interaction
    "browser_use": {
        "description": "Full browser automation with search and vision",
        "toolsets": {"browser": 100, "web": 80, "vision": 70},
    },
    # Prometheus-focused (Prometheus development)
    "prometheus_development": {
        "description": "Prometheus-focused development with all Prometheus-specific tools",
        "toolsets": {
            "prometheus": 100,
            "file": 100,
            "terminal": 100,
            "web": 80,
            "browser": 60,
            "moa": 40,
        },
    },
}


def get_distribution(name: str) -> dict[str, any] | None:
    """
    Get a toolset distribution by name.

    Args:
        name (str): Name of the distribution

    Returns:
        Dict: Distribution definition with description and toolsets
        None: If distribution not found
    """
    return DISTRIBUTIONS.get(name)


def list_distributions() -> dict[str, dict]:
    """
    List all available distributions.

    Returns:
        Dict: All distribution definitions
    """
    return DISTRIBUTIONS.copy()


def sample_toolsets_from_distribution(distribution_name: str) -> list[str]:
    """
    Sample toolsets based on distribution probabilities.

    Each toolset in the distribution has a % chance of being included.
    This allows multiple toolsets to be active simultaneously.

    Args:
        distribution_name (str): Name of distribution to sample from

    Returns:
        List[str]: List of sampled toolset names

    Raises:
        ValueError: If distribution name not found
    """
    dist = get_distribution(distribution_name)
    if not dist:
        raise ValueError(f"Unknown distribution: {distribution_name}")

    selected_toolsets = []

    for toolset_name, probability in dist["toolsets"].items():
        if not validate_toolset(toolset_name):
            print(f"Warning: Toolset '{toolset_name}' in distribution not valid")
            continue

        if random.random() * 100 < probability:
            selected_toolsets.append(toolset_name)

    if not selected_toolsets and dist["toolsets"]:
        highest_prob_toolset = max(dist["toolsets"].items(), key=lambda x: x[1])[0]
        if validate_toolset(highest_prob_toolset):
            selected_toolsets.append(highest_prob_toolset)

    return selected_toolsets


def validate_distribution(distribution_name: str) -> bool:
    """
    Check if a distribution name is valid.

    Args:
        distribution_name (str): Distribution name to validate

    Returns:
        bool: True if valid, False otherwise
    """
    return distribution_name in DISTRIBUTIONS


def print_distribution_info(distribution_name: str) -> None:
    """
    Print detailed information about a distribution.

    Args:
        distribution_name (str): Distribution name
    """
    dist = get_distribution(distribution_name)
    if not dist:
        print(f"Unknown distribution: {distribution_name}")
        return

    print(f"\nDistribution: {distribution_name}")
    print(f"Description: {dist['description']}")
    print("Toolsets:")
    for toolset, prob in sorted(dist["toolsets"].items(), key=lambda x: x[1], reverse=True):
        print(f"  {toolset:20} : {prob:3}% chance")


if __name__ == "__main__":
    print("Prometheus Toolset Distributions Demo")
    print("=" * 60)

    print("\nAvailable Distributions:")
    print("-" * 40)
    for name, dist in list_distributions().items():
        print(f"\n{name}:")
        print(f"  {dist['description']}")
        toolset_list = ", ".join([f"{ts}({p}%)" for ts, p in dist["toolsets"].items()])
        print(f"  Toolsets: {toolset_list}")

    print("\nSampling Examples:")
    print("-" * 40)

    test_distributions = ["image_gen", "research", "balanced", "prometheus_development"]

    for dist_name in test_distributions:
        print(f"\n{dist_name}:")
        samples = []
        for _ in range(5):
            sampled = sample_toolsets_from_distribution(dist_name)
            samples.append(sorted(sampled))

        for i, sample in enumerate(samples):
            print(f"  Sample {i + 1}: {sample}")

    print("\nDetailed Distribution Info:")
    print("-" * 40)
    print_distribution_info("prometheus_development")
    print_distribution_info("research")
