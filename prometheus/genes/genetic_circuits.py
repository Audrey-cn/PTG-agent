#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║   🧬 基因回路工程 · Genetic Circuit Engineering              ║
║                                                              ║
║   合成生物学基因电路 · Synthetic Biology Gene Circuits          ║
║                                                              ║
║   对应碳基生物学：合成生物学基因回路、逻辑门、开关网络    ║
║   可编程的基因网络，类似数字逻辑门，构建复杂行为回路        ║
╚══════════════════════════════════════════════════════════════╝

碳基生物学对照：
- 基因回路：合成生物学中可编程的基因网络
- 逻辑门：AND/OR/NOT门，类似数字电路逻辑门
- 开关网络：基因开关、反馈环路、振荡器等动态电路
- 层级调控：转录级联、转录级联、信号级联
"""
import os
import re
import json
import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum


PROMETHEUS_HOME = os.path.expanduser("~/.hermes/tools/prometheus")
CIRCUITS_DIR = os.path.join(PROMETHEUS_HOME, "genes", "circuits")

os.makedirs(CIRCUITS_DIR, exist_ok=True)


class LogicGateType(Enum):
    """逻辑门类型"""
    AND = "AND"
    OR = "OR"
    NOT = "NOT"
    NAND = "NAND"
    NOR = "NOR"
    XOR = "XOR"
    XNOR = "XNOR"


@dataclass
class GeneticLogicGate:
    """基因逻辑门 - 合成生物学的逻辑门组件"""
    gate_id: str
    gate_type: LogicGateType
    inputs: List[str]
    output: str
    threshold: float = 0.5
    description: str = ""
    strength: float = 1.0

    def evaluate(self, input_values: Dict[str, bool]) -> bool:
        """评估逻辑门输出"""
        if self.gate_type == LogicGateType.AND:
            result = all(input_values.get(i, False) for i in self.inputs)
        elif self.gate_type == LogicGateType.OR:
            result = any(input_values.get(i, False) for i in self.inputs)
        elif self.gate_type == LogicGateType.NOT:
            result = not input_values.get(self.inputs[0], False)
        elif self.gate_type == LogicGateType.NAND:
            result = not all(input_values.get(i, False) for i in self.inputs)
        elif self.gate_type == LogicGateType.NOR:
            result = not any(input_values.get(i, False) for i in self.inputs)
        elif self.gate_type == LogicGateType.XOR:
            vals = [input_values.get(i, False) for i in self.inputs]
            result = sum(1 for v in vals if v) == 1
        elif self.gate_type == LogicGateType.XNOR:
            vals = [input_values.get(i, False) for i in self.inputs]
            result = sum(1 for v in vals if v) != 1
        
        return result
    
    def to_dict(self) -> dict:
        return {
            "gate_id": self.gate_id,
            "gate_type": self.gate_type.value,
            "inputs": self.inputs,
            "output": self.output,
            "threshold": self.threshold,
            "description": self.description,
            "strength": self.strength
        }


@dataclass
class GeneticSwitch:
    """基因开关 - 双稳态开关"""
    switch_id: str
    gene_a: str
    gene_b: str
    state: str = "OFF"
    cooperativity: float = 2.0
    decay_rate: float = 0.1
    description: str = ""

    def toggle(self, input_signal: float) -> str:
        """切换开关状态"""
        if input_signal > 0.5:
            self.state = "ON"
        else:
            self.state = "OFF"
        return self.state
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GeneticOscillator:
    """基因振荡器 - 周期性振荡回路"""
    oscillator_id: str
    genes: List[str]
    period: float = 10.0
    amplitude: float = 1.0
    phase: float = 0.0
    running: bool = False
    description: str = ""

    def get_value(self, time: float) -> float:
        """获取当前振荡器值"""
        import math
        return self.amplitude * math.sin(2 * math.pi * time / self.period + self.phase)
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GeneticCircuit:
    """基因回路 - 完整的合成基因网络"""
    circuit_id: str
    name: str
    description: str = ""
    logic_gates: List[GeneticLogicGate] = field(default_factory=list)
    switches: List[GeneticSwitch] = field(default_factory=list)
    oscillators: List[GeneticOscillator] = field(default_factory=list)
    connections: List[Dict[str, str]] = field(default_factory=list)
    created: str = ""

    def __post_init__(self):
        if not self.created:
            self.created = datetime.datetime.now().isoformat()

    def evaluate(self, inputs: Dict[str, bool]) -> Dict[str, bool]:
        """评估整个回路"""
        results = inputs.copy()
        for gate in self.logic_gates:
            results[gate.output] = gate.evaluate(results)
        
        return results
    
    def to_dict(self) -> dict:
        return {
            "circuit_id": self.circuit_id,
            "name": self.name,
            "description": self.description,
            "logic_gates": [g.to_dict() for g in self.logic_gates],
            "switches": [s.to_dict() for s in self.switches],
            "oscillators": [o.to_dict() for o in self.oscillators],
            "connections": self.connections,
            "created": self.created
        }
    
    def save(self, filepath: str = None):
        """保存回路到文件"""
        if not filepath:
            filepath = os.path.join(CIRCUITS_DIR, f"{self.circuit_id}.json")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        
        return filepath
    
    @classmethod
    def load(cls, filepath: str) -> 'GeneticCircuit':
        """从文件加载回路"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        gates = [GeneticLogicGate(**g) for g in data['logic_gates']]
        switches = [GeneticSwitch(**s) for s in data.get('switches', [])]
        oscillators = [GeneticOscillator(**o) for o in data.get('oscillators', [])]
        
        return cls(
            circuit_id=data['circuit_id'],
            name=data['name'],
            description=data.get('description', ''),
            logic_gates=gates,
            switches=switches,
            oscillators=oscillators,
            connections=data.get('connections', []),
            created=data.get('created', '')
        )


class CircuitFactory:
    """回路工厂 - 预定义标准回路"""
    
    @staticmethod
    def create_task_decider() -> GeneticCircuit:
        """任务决策回路"""
        circuit = GeneticCircuit(
            circuit_id="task_decider",
            name="任务决策回路",
            description="根据输入条件选择执行任务"
        )
        
        circuit.logic_gates.append(
            GeneticLogicGate(
                gate_id="urgent_task",
                gate_type=LogicGateType.AND,
                inputs=["has_deadline", "has_high_priority"],
                output="urgent_mode",
                description="紧急任务模式触发"
            )
        )
        
        circuit.logic_gates.append(
            GeneticLogicGate(
                gate_id="creative_task",
                gate_type=LogicGateType.OR,
                inputs=["is_creative", "needs_innovation"],
                output="creative_mode",
                description="创意任务模式触发"
            )
        )
        
        circuit.logic_gates.append(
            GeneticLogicGate(
                gate_id="analytical_task",
                gate_type=LogicGateType.NAND,
                inputs=["urgent_mode", "creative_mode"],
                output="analytical_mode",
                description="分析任务模式触发"
            )
        )
        
        return circuit
    
    @staticmethod
    def create_feedback_loop() -> GeneticCircuit:
        """反馈调节回路"""
        circuit = GeneticCircuit(
            circuit_id="feedback_loop",
            name="反馈调节回路",
            description="负反馈调节回路"
        )
        
        circuit.logic_gates.append(
            GeneticLogicGate(
                gate_id="positive_feedback",
                gate_type=LogicGateType.OR,
                inputs=["success", "goal_reached"],
                output="amplify",
                description="正反馈放大"
            )
        )
        
        circuit.switches.append(
            GeneticSwitch(
                switch_id="task_switch",
                gene_a="mode_a",
                gene_b="mode_b",
                description="任务切换开关"
            )
        )
        
        return circuit
    
    @staticmethod
    def create_circadian_oscillator() -> GeneticCircuit:
        """生物钟振荡器"""
        circuit = GeneticCircuit(
            circuit_id="circadian_oscillator",
            name="生物钟振荡器",
            description="模拟生物钟的基因振荡器"
        )
        
        circuit.oscillators.append(
            GeneticOscillator(
                oscillator_id="clock",
                genes=["morning_gene", "noon_gene", "night_gene"],
                period=24.0,
                description="24小时生物钟"
            )
        )
        
        return circuit


class CircuitEngine:
    """基因回路引擎 - 管理和运行基因回路"""
    
    def __init__(self):
        self.circuits: Dict[str, GeneticCircuit] = {}
        self.active_circuits: List[str] = []
    
    def register_circuit(self, circuit: GeneticCircuit) -> str:
        """注册回路"""
        self.circuits[circuit.circuit_id] = circuit
        return circuit.circuit_id
    
    def activate_circuit(self, circuit_id: str):
        """激活回路"""
        if circuit_id in self.circuits and circuit_id not in self.active_circuits:
            self.active_circuits.append(circuit_id)
    
    def deactivate_circuit(self, circuit_id: str):
        """禁用回路"""
        if circuit_id in self.active_circuits:
            self.active_circuits.remove(circuit_id)
    
    def run_circuit(self, circuit_id: str, inputs: Dict[str, bool]) -> Dict[str, Any]:
        """运行指定回路"""
        if circuit_id not in self.circuits:
            return {"error": f"Circuit {circuit_id} not found"}
        
        circuit = self.circuits[circuit_id]
        
        results = circuit.evaluate(inputs)
        
        return {
            "circuit_id": circuit_id,
            "inputs": inputs,
            "outputs": results,
            "timestamp": datetime.datetime.now().isoformat()
        }
    
    def run_all_active(self, inputs: Dict[str, bool]) -> Dict[str, Any]:
        """运行所有激活的回路"""
        all_results = {}
        
        for circuit_id in self.active_circuits:
            result = self.run_circuit(circuit_id, inputs)
            all_results[circuit_id] = result
        
        return all_results
    
    def list_circuits(self) -> List[Dict[str, str]]:
        """列出所有可用回路"""
        return [
            {
                "circuit_id": c.circuit_id,
                "name": c.name,
                "description": c.description
            }
            for c in self.circuits.values()
        ]


def print_circuit_visualization(circuit: GeneticCircuit):
    """打印回路可视化"""
    print(f"\n╔══════════════════════════════════════════════════════════════╗")
    print(f"║   🧬 基因回路: {circuit.name:40}║")
    print(f"╠══════════════════════════════════════════════════════════════╣")
    
    if circuit.logic_gates:
        print(f"║   🚪 逻辑门 ({len(circuit.logic_gates)} 个:")
        for gate in circuit.logic_gates:
            input_str = ", ".join(gate.inputs)
            print(f"║       [{gate.gate_type.value}] {gate.gate_id}: {input_str} → {gate.output}")
            if gate.description:
                print(f"║         {gate.description}")
    
    if circuit.switches:
        print(f"║   ⚡ 开关 ({len(circuit.switches)} 个):")
        for switch in circuit.switches:
            print(f"║       {switch.switch_id}: {switch.gene_a} ⇄ {switch.gene_b} ({switch.state})")
    
    if circuit.oscillators:
        print(f"║   🔄 振荡器 ({len(circuit.oscillators)} 个):")
        for osc in circuit.oscillators:
            print(f"║       {osc.oscillator_id}: 周期={osc.period}, 基因={', '.join(osc.genes)}")
    
    print(f"╚══════════════════════════════════════════════════════════════╝\n")


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("""
🧬 基因回路工程 · Genetic Circuit Engineering

用法:
    python genetic_circuits.py create <回路ID>    # 创建预定义回路
    python genetic_circuits.py list              # 列出可用回路
    python genetic_circuits.py run <回路ID>       # 运行回路示例
""")
        return
    
    action = sys.argv[1]
    
    engine = CircuitEngine()
    factory = CircuitFactory()
    
    task_decider = factory.create_task_decider()
    feedback_loop = factory.create_feedback_loop()
    circadian = factory.create_circadian_oscillator()
    
    engine.register_circuit(task_decider)
    engine.register_circuit(feedback_loop)
    engine.register_circuit(circadian)
    
    if action == "list":
        circuits = engine.list_circuits()
        print(f"\n🧬 可用基因回路 ({len(circuits)} 个:\n")
        for c in circuits:
            print(f"  {c['circuit_id']:20} {c['name']}")
            if c['description']:
                print(f"      {c['description'][:60]}")
    
    elif action == "create" and len(sys.argv) > 2:
        print(f"\n✨ 创建回路: {sys.argv[2]} 成功!")
        print_circuit_visualization(task_decider)
    
    elif action == "run" and len(sys.argv) > 2:
        circuit_id = sys.argv[2]
        test_inputs = {
            "has_deadline": True,
            "has_high_priority": True,
            "is_creative": False,
            "needs_innovation": False
        }
        result = engine.run_circuit(circuit_id, test_inputs)
        print(f"\n🚀 运行回路结果: {result}")


if __name__ == "__main__":
    main()
