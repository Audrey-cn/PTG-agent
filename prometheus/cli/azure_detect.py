from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Any, Optional


IMDS_URL = "http://169.254.169.254/metadata/instance"
IMDS_API_VERSION = "2021-02-01"


def is_azure_environment() -> bool:
    try:
        url = f"{IMDS_URL}?api-version={IMDS_API_VERSION}"
        req = urllib.request.Request(url)
        req.add_header("Metadata", "true")
        
        with urllib.request.urlopen(req, timeout=2) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                return "compute" in data
    except Exception:
        pass
    
    return False


def get_azure_metadata() -> dict[str, Any]:
    try:
        url = f"{IMDS_URL}?api-version={IMDS_API_VERSION}"
        req = urllib.request.Request(url)
        req.add_header("Metadata", "true")
        
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                return json.loads(response.read().decode("utf-8"))
    except Exception:
        pass
    
    return {}


def get_azure_identity() -> Optional[dict[str, Any]]:
    try:
        url = f"{IMDS_URL}/identity?api-version={IMDS_API_VERSION}"
        req = urllib.request.Request(url)
        req.add_header("Metadata", "true")
        
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                return json.loads(response.read().decode("utf-8"))
    except Exception:
        pass
    
    return None


def detect_azure_resources() -> list[dict[str, Any]]:
    resources = []
    
    metadata = get_azure_metadata()
    if not metadata:
        return resources
    
    compute = metadata.get("compute", {})
    
    if compute:
        resources.append({
            "type": "virtual_machine",
            "name": compute.get("name"),
            "location": compute.get("location"),
            "resource_group": compute.get("resourceGroupName"),
            "subscription_id": compute.get("subscriptionId"),
            "vm_id": compute.get("vmId"),
            "vm_size": compute.get("vmSize"),
            "os_type": compute.get("osProfile", {}).get("systemType"),
            "tags": compute.get("tags", {}),
        })
    
    network = metadata.get("network", {})
    if network:
        interfaces = network.get("interface", [])
        for iface in interfaces:
            resources.append({
                "type": "network_interface",
                "name": iface.get("name"),
                "mac_address": iface.get("macAddress"),
                "ipv4": [ip.get("privateIpAddress") for ip in iface.get("ipv4", {}).get("ipAddress", [])],
                "ipv6": [ip.get("privateIpAddress") for ip in iface.get("ipv6", {}).get("ipAddress", [])],
            })
    
    return resources


def get_azure_attested_metadata() -> Optional[dict[str, Any]]:
    try:
        url = f"{IMDS_URL}/attested/document?api-version={IMDS_API_VERSION}"
        req = urllib.request.Request(url)
        req.add_header("Metadata", "true")
        
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                return json.loads(response.read().decode("utf-8"))
    except Exception:
        pass
    
    return None
