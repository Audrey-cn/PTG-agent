from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from prometheus.plugins import PluginManager, get_plugin_manager

logger = logging.getLogger("prometheus.plugins_cmd")


def _get_manager() -> PluginManager:
    return get_plugin_manager()


def cmd_plugins_list() -> None:
    manager = _get_manager()
    manifests = manager.discover()
    loaded = manager.list_plugins()

    if not manifests:
        print("\n🔌 无已安装插件\n")
        return

    loaded_names = {p["name"] for p in loaded}
    print(f"\n🔌 插件列表 ({len(manifests)} 个)\n")

    for m in manifests:
        is_loaded = m.name in loaded_names
        status = "✅ 已加载" if is_loaded else ("⏸ 禁用" if not m.enabled else "⏳ 未加载")
        print(f"  · {m.name} v{m.version} — {status}")
        if m.description:
            print(f"    {m.description[:60]}")
        if m.provides_tools:
            print(f"    工具: {', '.join(m.provides_tools)}")
        print()


def cmd_plugins_install(source: str) -> None:
    source_path = Path(source).expanduser().resolve()
    if not source_path.exists():
        print(f"❌ 源路径不存在: {source}")
        return

    manager = _get_manager()
    target_dir = manager.plugins_dir / source_path.name

    if target_dir.exists():
        print(f"❌ 插件已存在: {source_path.name}")
        return

    manager.plugins_dir.mkdir(parents=True, exist_ok=True)

    if source_path.is_dir():
        shutil.copytree(str(source_path), str(target_dir))
    else:
        print("❌ 插件源必须是一个目录")
        return

    manifest_path = target_dir / "plugin.yaml"
    if not manifest_path.exists():
        manifest_path = target_dir / "plugin.json"

    if not manifest_path.exists():
        print("⚠️  已复制但未找到 manifest (plugin.yaml/plugin.json)")

    if manager.load_plugin(source_path.name):
        print(f"✅ 插件已安装并加载: {source_path.name}")
    else:
        print(f"⚠️  插件已复制但加载失败: {source_path.name}")


def cmd_plugins_uninstall(name: str) -> None:
    manager = _get_manager()

    if name in manager._plugins:
        manager.unload_plugin(name)

    plugin_dir = manager.plugins_dir / name
    if not plugin_dir.exists():
        print(f"❌ 插件未找到: {name}")
        return

    shutil.rmtree(str(plugin_dir))
    print(f"✅ 插件已卸载: {name}")


def cmd_plugins_enable(name: str) -> None:
    manager = _get_manager()
    plugin_dir = manager.plugins_dir / name

    if not plugin_dir.exists():
        print(f"❌ 插件未找到: {name}")
        return

    for manifest_name in ("plugin.yaml", "plugin.json"):
        manifest_path = plugin_dir / manifest_name
        if manifest_path.exists():
            try:
                if manifest_name.endswith(".json"):
                    data = json.loads(manifest_path.read_text(encoding="utf-8"))
                else:
                    import yaml

                    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
                data["enabled"] = True
                if manifest_name.endswith(".json"):
                    manifest_path.write_text(
                        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
                    )
                else:
                    manifest_path.write_text(
                        yaml.dump(data, default_flow_style=False, allow_unicode=True),
                        encoding="utf-8",
                    )
            except Exception as e:
                print(f"❌ 更新 manifest 失败: {e}")
                return
            break

    if manager.load_plugin(name):
        print(f"✅ 插件已启用: {name}")
    else:
        print(f"⚠️  插件启用失败: {name}")


def cmd_plugins_disable(name: str) -> None:
    manager = _get_manager()

    if name in manager._plugins:
        manager.unload_plugin(name)

    plugin_dir = manager.plugins_dir / name
    if not plugin_dir.exists():
        print(f"❌ 插件未找到: {name}")
        return

    for manifest_name in ("plugin.yaml", "plugin.json"):
        manifest_path = plugin_dir / manifest_name
        if manifest_path.exists():
            try:
                if manifest_name.endswith(".json"):
                    data = json.loads(manifest_path.read_text(encoding="utf-8"))
                else:
                    import yaml

                    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
                data["enabled"] = False
                if manifest_name.endswith(".json"):
                    manifest_path.write_text(
                        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
                    )
                else:
                    manifest_path.write_text(
                        yaml.dump(data, default_flow_style=False, allow_unicode=True),
                        encoding="utf-8",
                    )
            except Exception as e:
                print(f"❌ 更新 manifest 失败: {e}")
                return
            break

    print(f"✅ 插件已禁用: {name}")


def cmd_plugins_info(name: str) -> None:
    manager = _get_manager()
    plugin = manager.get_plugin(name)

    if plugin:
        m = plugin.manifest
        print(f"\n🔌 插件详情: {m.name}\n")
        print(f"  版本: {m.version}")
        print(f"  描述: {m.description}")
        print(f"  作者: {m.author}")
        print(f"  启用: {'是' if m.enabled else '否'}")
        print(f"  已加载: {'是' if plugin.loaded else '否'}")
        print(f"  目录: {plugin.plugin_dir}")
        if m.dependencies:
            print(f"  依赖: {', '.join(m.dependencies)}")
        if m.provides_tools:
            print(f"  提供工具: {', '.join(m.provides_tools)}")
        if m.provides_commands:
            print(
                f"  提供命令: {', '.join(c.get('name', '?') if isinstance(c, dict) else str(c) for c in m.provides_commands)}"
            )
        if plugin.context:
            if plugin.context._registered_tools:
                print(f"  已注册工具: {', '.join(plugin.context._registered_tools)}")
            if plugin.context._registered_commands:
                print(
                    f"  已注册命令: {', '.join(c.get('name', '?') for c in plugin.context._registered_commands)}"
                )
        print()
        return

    manifests = manager.discover()
    for mf in manifests:
        if mf.name == name:
            print(f"\n🔌 插件详情: {mf.name} (未加载)\n")
            print(f"  版本: {mf.version}")
            print(f"  描述: {mf.description}")
            print(f"  作者: {mf.author}")
            print(f"  启用: {'是' if mf.enabled else '否'}")
            if mf.dependencies:
                print(f"  依赖: {', '.join(mf.dependencies)}")
            if mf.provides_tools:
                print(f"  提供工具: {', '.join(mf.provides_tools)}")
            print()
            return

    print(f"❌ 插件未找到: {name}")
