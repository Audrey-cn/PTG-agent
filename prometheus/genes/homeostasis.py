#!/usr/bin/env python3
"""╔══════════════════════════════════════════════════════════════╗."""

import datetime
import json
import os
from collections.abc import Callable
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

PROMETHEUS_HOME = os.path.expanduser("~/.prometheus/tools/prometheus")
HOMEOSTASIS_DIR = os.path.join(PROMETHEUS_HOME, "homeostasis")

os.makedirs(HOMEOSTASIS_DIR, exist_ok=True)


class RegulationType(Enum):
    """调节类型"""

    NEGATIVE_FEEDBACK = "NEGATIVE"
    POSITIVE_FEEDBACK = "POSITIVE"


@dataclass
class Sensor:
    """传感器 - 监测系统状态"""

    sensor_id: str
    name: str
    metric: str
    min_range: float = 0.0
    max_range: float = 100.0
    set_point: float = 50.0
    tolerance: float = 10.0
    current_value: float = 50.0
    last_read: str = ""

    def __post_init__(self):
        if not self.last_read:
            self.last_read = datetime.datetime.now().isoformat()

    def read(self, value: float) -> "Sensor":
        """读取传感器值"""
        self.current_value = value
        self.last_read = datetime.datetime.now().isoformat()
        return self

    def is_out_of_range(self) -> bool:
        """检查是否超出范围"""
        return (
            self.current_value < self.set_point - self.tolerance
            or self.current_value > self.set_point + self.tolerance
        )

    def deviation(self) -> float:
        """计算偏差"""
        return self.current_value - self.set_point

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Effector:
    """效应器 - 执行调节动作"""

    effector_id: str
    name: str
    target: str
    action: Callable
    sensitivity: float = 0.1
    max_effect: float = 1.0

    def apply(self, deviation: float) -> float:
        """应用效应，返回调整量"""
        effect = -deviation * self.sensitivity
        return max(-self.max_effect, min(self.max_effect, effect))

    def to_dict(self) -> dict:
        return {
            "effector_id": self.effector_id,
            "name": self.name,
            "target": self.target,
            "sensitivity": self.sensitivity,
            "max_effect": self.max_effect,
        }


@dataclass
class FeedbackLoop:
    """反馈回路 - 传感器→控制器→效应器"""

    loop_id: str
    name: str
    sensor: Sensor
    effector: Effector
    regulation_type: RegulationType = RegulationType.NEGATIVE_FEEDBACK
    enabled: bool = True
    description: str = ""

    def regulate(self) -> dict[str, Any]:
        """执行调节"""
        if not self.enabled:
            return {"status": "disabled"}

        deviation = self.sensor.deviation()

        if not self.sensor.is_out_of_range():
            return {"status": "in_range", "deviation": deviation, "message": "Within tolerance"}

        effect = self.effector.apply(deviation)

        if self.regulation_type == RegulationType.POSITIVE_FEEDBACK:
            effect = -effect

        return {
            "status": "regulated",
            "deviation": deviation,
            "effect": effect,
            "sensor": self.sensor.name,
            "effector": self.effector.name,
            "regulation_type": self.regulation_type.value,
        }

    def to_dict(self) -> dict:
        return {
            "loop_id": self.loop_id,
            "name": self.name,
            "sensor": self.sensor.to_dict(),
            "effector": self.effector.to_dict(),
            "regulation_type": self.regulation_type.value,
            "enabled": self.enabled,
            "description": self.description,
        }


class HomeostasisSystem:
    """内稳态系统 - 动态平衡调节系统"""

    def __init__(self):
        self.sensors: dict[str, Sensor] = {}
        self.effectors: dict[str, Effector] = {}
        self.loops: dict[str, FeedbackLoop] = {}
        self.history: list[dict[str, Any]] = []
        self._init_standard_sensors()

    def _init_standard_sensors(self):
        """初始化标准传感器"""
        energy_sensor = Sensor(
            sensor_id="energy",
            name="能量传感器",
            metric="energy_level",
            min_range=0,
            max_range=100,
            set_point=70,
            tolerance=20,
        )
        self.add_sensor(energy_sensor)

        focus_sensor = Sensor(
            sensor_id="focus",
            name="注意力传感器",
            metric="focus_level",
            min_range=0,
            max_range=100,
            set_point=80,
            tolerance=15,
        )
        self.add_sensor(focus_sensor)

        stress_sensor = Sensor(
            sensor_id="stress",
            name="压力传感器",
            metric="stress_level",
            min_range=0,
            max_range=100,
            set_point=30,
            tolerance=20,
        )
        self.add_sensor(stress_sensor)

    def add_sensor(self, sensor: Sensor):
        """添加传感器"""
        self.sensors[sensor.sensor_id] = sensor

    def add_effector(self, effector: Effector):
        """添加效应器"""
        self.effectors[effector.effector_id] = effector

    def create_loop(
        self,
        loop_id: str,
        name: str,
        sensor_id: str,
        effector_id: str,
        regulation_type: RegulationType = RegulationType.NEGATIVE_FEEDBACK,
        description: str = "",
    ) -> FeedbackLoop | None:
        """创建反馈回路"""
        if sensor_id not in self.sensors:
            return None
        if effector_id not in self.effectors:
            return None

        loop = FeedbackLoop(
            loop_id=loop_id,
            name=name,
            sensor=self.sensors[sensor_id],
            effector=self.effectors[effector_id],
            regulation_type=regulation_type,
            description=description,
        )

        self.loops[loop_id] = loop
        return loop

    def update_sensor(self, sensor_id: str, value: float) -> Sensor | None:
        """更新传感器值"""
        if sensor_id not in self.sensors:
            return None

        sensor = self.sensors[sensor_id]
        sensor.read(value)
        return sensor

    def regulate_all(self) -> list[dict[str, Any]]:
        """执行所有回路调节"""
        results = []

        for loop in self.loops.values():
            result = loop.regulate()
            results.append(
                {
                    "loop_id": loop.loop_id,
                    "loop_name": loop.name,
                    "result": result,
                    "timestamp": datetime.datetime.now().isoformat(),
                }
            )

            if result["status"] == "regulated":
                self.history.append(results[-1])

        return results

    def read_all_sensors(self) -> dict[str, float]:
        """读取所有传感器值"""
        return {sensor_id: sensor.current_value for sensor_id, sensor in self.sensors.items()}

    def get_system_state(self) -> dict[str, Any]:
        """获取系统状态"""
        sensors_data = {sensor_id: sensor.to_dict() for sensor_id, sensor in self.sensors.items()}

        in_homeostasis = all(not sensor.is_out_of_range() for sensor in self.sensors.values())

        return {
            "timestamp": datetime.datetime.now().isoformat(),
            "in_homeostasis": in_homeostasis,
            "sensors": sensors_data,
            "active_loops": [loop_id for loop_id, loop in self.loops.items() if loop.enabled],
            "history_length": len(self.history),
        }

    def enable_loop(self, loop_id: str) -> bool:
        """启用回路"""
        if loop_id in self.loops:
            self.loops[loop_id].enabled = True
            return True
        return False

    def disable_loop(self, loop_id: str) -> bool:
        """禁用回路"""
        if loop_id in self.loops:
            self.loops[loop_id].enabled = False
            return True
        return False

    def get_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """获取历史记录"""
        return self.history[-limit:]

    def save_state(self, filepath: str = None):
        """保存状态"""
        if not filepath:
            filepath = os.path.join(HOMEOSTASIS_DIR, "state.json")

        state = {
            "sensors": {k: v.to_dict() for k, v in self.sensors.items()},
            "loops": {k: v.to_dict() for k, v in self.loops.items()},
            "history": self.history[-100:],
            "last_updated": datetime.datetime.now().isoformat(),
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def load_state(self, filepath: str = None):
        """加载状态"""
        if not filepath:
            filepath = os.path.join(HOMEOSTASIS_DIR, "state.json")

        if os.path.exists(filepath):
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)

            if "history" in data:
                self.history = data["history"]


def print_homeostasis_dashboard(system: HomeostasisSystem):
    """打印内稳态仪表盘"""
    state = system.get_system_state()

    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║   🧬 内稳态系统 · Homeostasis Dashboard                     ║")
    print("╠══════════════════════════════════════════════════════════════╣")

    status_icon = "✅" if state["in_homeostasis"] else "⚠️"
    print(f"║   {status_icon} 整体状态: {'在稳态中' if state['in_homeostasis'] else '需要调节'}")
    print(f"║   更新时间: {state['timestamp'][:19]}")
    print("║                                                              ║")
    print("║   📡 传感器状态:")

    for _sensor_id, sensor in system.sensors.items():
        value = sensor.current_value
        set_point = sensor.set_point
        low = set_point - sensor.tolerance
        high = set_point + sensor.tolerance

        status = "✅" if low <= value <= high else "⚠️"
        bar = generate_visual_bar(value, low, high, set_point, 25)

        print(f"║     {status} {sensor.name:20}")
        print(f"║        {bar} {value:3.1f}/{set_point}")

    print("║                                                              ║")
    print(f"║   🔄 反馈回路 ({len(system.loops)} 个):")
    for loop in system.loops.values():
        status_icon = "✅" if loop.enabled else "❌"
        print(f"║     {status_icon} {loop.name}")

    print("╚══════════════════════════════════════════════════════════════╝\n")


def generate_visual_bar(value: float, low: float, high: float, set_point: float, width: int) -> str:
    """生成可视化条"""
    import math

    min_val = 0
    max_val = 100

    normalized = (value - min_val) / (max_val - min_val)
    pos = math.floor(normalized * width)

    bar = []
    for i in range(width):
        if i < pos:
            bar.append("█")
        elif i == pos:
            bar.append("●")
        else:
            bar.append("░")

    return "".join(bar)


def main():
    import sys

    if len(sys.argv) < 2:
        print("""
🧬 内稳态系统 · Homeostasis System

用法:
    python homeostasis.py dashboard     # 显示仪表盘
    python homeostasis.py regulate       # 执行自动调节
    python homeostasis.py update <传感器> <值>  # 更新传感器
    python homeostasis.py loop <ID>      # 管理反馈回路
""")
        return

    system = HomeostasisSystem()

    def dummy_effector(action_value):
        return action_value

    system.add_effector(
        Effector(
            effector_id="energy_regulator",
            name="能量调节器",
            target="energy_level",
            action=dummy_effector,
        )
    )

    system.add_effector(
        Effector(
            effector_id="stress_reliever",
            name="压力缓解器",
            target="stress_level",
            action=dummy_effector,
        )
    )

    system.create_loop(
        loop_id="energy_balance",
        name="能量平衡回路",
        sensor_id="energy",
        effector_id="energy_regulator",
    )

    system.create_loop(
        loop_id="stress_balance",
        name="压力平衡回路",
        sensor_id="stress",
        effector_id="stress_reliever",
    )

    action = sys.argv[1]

    if action == "dashboard":
        system.update_sensor("energy", 65)
        system.update_sensor("focus", 78)
        system.update_sensor("stress", 25)
        print_homeostasis_dashboard(system)

    elif action == "regulate":
        results = system.regulate_all()
        print(f"\n🔄 执行了 {len(results)} 个调节")
        for r in results:
            print(f"  {r['loop_name']}: {r['result']['status']}")

    elif action == "update" and len(sys.argv) > 3:
        sensor_id = sys.argv[2]
        try:
            value = float(sys.argv[3])
            sensor = system.update_sensor(sensor_id, value)
            if sensor:
                print(f"\n✅ {sensor.name} 更新到 {value}")
            else:
                print(f"\n❌ 传感器 {sensor_id} 不存在")
        except ValueError:
            print("\n❌ 无效的值")

    elif action == "loop" and len(sys.argv) > 2:
        loop_id = sys.argv[2]
        if len(sys.argv) > 3:
            if sys.argv[3] == "enable":
                system.enable_loop(loop_id)
                print(f"✅ 回路 {loop_id} 已启用")
            elif sys.argv[3] == "disable":
                system.disable_loop(loop_id)
                print(f"✅ 回路 {loop_id} 已禁用")


if __name__ == "__main__":
    main()
