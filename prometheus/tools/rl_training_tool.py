#!/usr/bin/env python3
"""RL Training Tools Module."""

import ast
import asyncio
import contextlib
import importlib.util
import json
import logging
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from prometheus.constants_core import get_prometheus_home

logger = logging.getLogger(__name__)

# ============================================================================
# Path Configuration
# ============================================================================

PROMETHEUS_ROOT = Path(__file__).parent.parent
TINKER_ATROPOS_ROOT = PROMETHEUS_ROOT / "tinker-atropos"
ENVIRONMENTS_DIR = TINKER_ATROPOS_ROOT / "tinker_atropos" / "environments"
CONFIGS_DIR = TINKER_ATROPOS_ROOT / "configs"
LOGS_DIR = get_prometheus_home() / "logs" / "rl_training"


def _ensure_logs_dir():
    """Lazily create logs directory on first use (avoid side effects at import time)."""
    if TINKER_ATROPOS_ROOT.exists():
        LOGS_DIR.mkdir(exist_ok=True)


# ============================================================================
# Locked Configuration (Infrastructure Settings)
# ============================================================================

LOCKED_FIELDS = {
    "env": {
        "tokenizer_name": "Qwen/Qwen3-8B",
        "rollout_server_url": "http://localhost:8000",
        "use_wandb": True,
        "max_token_length": 8192,
        "max_num_workers": 2048,
        "worker_timeout": 3600,
        "total_steps": 2500,
        "steps_per_eval": 25,
        "max_batches_offpolicy": 3,
        "inference_weight": 1.0,
        "eval_limit_ratio": 0.1,
    },
    "openai": [
        {
            "model_name": "Qwen/Qwen3-8B",
            "base_url": "http://localhost:8001/v1",
            "api_key": "x",
            "weight": 1.0,
            "num_requests_for_eval": 256,
            "timeout": 3600,
            "server_type": "sglang",
        }
    ],
    "tinker": {
        "lora_rank": 32,
        "learning_rate": 0.00004,
        "max_token_trainer_length": 9000,
        "checkpoint_dir": "./temp/",
        "save_checkpoint_interval": 25,
    },
    "slurm": False,
    "testing": False,
}

LOCKED_FIELD_NAMES = set(LOCKED_FIELDS.get("env", {}).keys())


# ============================================================================
# State Management
# ============================================================================


@dataclass
class EnvironmentInfo:
    """Information about a discovered environment."""

    name: str
    class_name: str
    file_path: str
    description: str = ""
    config_class: str = "BaseEnvConfig"


@dataclass
class RunState:
    """State for a training run."""

    run_id: str
    environment: str
    config: dict[str, Any]
    status: str = "pending"
    error_message: str = ""
    wandb_project: str = ""
    wandb_run_name: str = ""
    start_time: float = 0.0
    api_process: subprocess.Popen | None = None
    trainer_process: subprocess.Popen | None = None
    env_process: subprocess.Popen | None = None


_environments: list[EnvironmentInfo] = []
_current_env: str | None = None
_current_config: dict[str, Any] = {}
_env_config_cache: dict[str, dict[str, dict[str, Any]]] = {}
_active_runs: dict[str, RunState] = {}
_last_status_check: dict[str, float] = {}

MIN_STATUS_CHECK_INTERVAL = 30 * 60


# ============================================================================
# Environment Discovery
# ============================================================================


def _scan_environments() -> list[EnvironmentInfo]:
    """
    Scan the environments directory for BaseEnv subclasses using AST.
    """
    environments = []

    if not ENVIRONMENTS_DIR.exists():
        return environments

    for py_file in ENVIRONMENTS_DIR.glob("*.py"):
        if py_file.name.startswith("_"):
            continue

        try:
            with open(py_file) as f:
                tree = ast.parse(f.read())

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for base in node.bases:
                        base_name = ""
                        if isinstance(base, ast.Name):
                            base_name = base.id
                        elif isinstance(base, ast.Attribute):
                            base_name = base.attr

                        if base_name == "BaseEnv":
                            env_name = py_file.stem
                            description = ""
                            config_class = "BaseEnvConfig"

                            for item in node.body:
                                if isinstance(item, ast.Assign):
                                    for target in item.targets:
                                        if isinstance(target, ast.Name):
                                            if target.id == "name" and isinstance(
                                                item.value, ast.Constant
                                            ):
                                                env_name = item.value.value
                                            elif target.id == "env_config_cls" and isinstance(
                                                item.value, ast.Name
                                            ):
                                                config_class = item.value.id

                                if isinstance(item, ast.Expr) and isinstance(
                                    item.value, ast.Constant
                                ):
                                    if isinstance(item.value.value, str) and not description:
                                        description = item.value.value.split("\n")[0].strip()

                            environments.append(
                                EnvironmentInfo(
                                    name=env_name,
                                    class_name=node.name,
                                    file_path=str(py_file),
                                    description=description or f"Environment from {py_file.name}",
                                    config_class=config_class,
                                )
                            )
                            break
        except Exception as e:
            logger.warning("Could not parse %s: %s", py_file, e)

    return environments


def _get_env_config_fields(env_file_path: str) -> dict[str, dict[str, Any]]:
    """
    Dynamically import an environment and extract its config fields.
    """
    try:
        spec = importlib.util.spec_from_file_location("env_module", env_file_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["env_module"] = module
        spec.loader.exec_module(module)

        env_class = None
        for name, obj in vars(module).items():
            if isinstance(obj, type) and name != "BaseEnv":
                if hasattr(obj, "config_init") and callable(obj.config_init):
                    env_class = obj
                    break

        if not env_class:
            return {}

        config_class = None
        try:
            env_config, server_configs = env_class.config_init()
            config_class = type(env_config)
        except Exception as config_error:
            logger.info("config_init failed (%s), using BaseEnvConfig defaults", config_error)
            try:
                from atroposlib.envs.base import BaseEnvConfig

                config_class = BaseEnvConfig
            except ImportError:
                return {}

        if not config_class:
            return {}

        def make_serializable(val):
            if val is None:
                return None
            if hasattr(val, "value"):
                return val.value
            if hasattr(val, "name") and hasattr(val, "__class__") and "Enum" in str(type(val)):
                return val.name
            return val

        fields = {}
        for field_name, field_info in config_class.model_fields.items():
            field_type = field_info.annotation
            default = make_serializable(field_info.default)
            description = field_info.description or ""

            is_locked = field_name in LOCKED_FIELD_NAMES

            type_name = getattr(field_type, "__name__", str(field_type))
            if hasattr(field_type, "__origin__"):
                type_name = str(field_type)

            locked_value = LOCKED_FIELDS.get("env", {}).get(field_name, default)
            current_value = make_serializable(locked_value) if is_locked else default

            fields[field_name] = {
                "type": type_name,
                "default": default,
                "description": description,
                "locked": is_locked,
                "current_value": current_value,
            }

        return fields

    except Exception as e:
        logger.warning("Could not introspect environment config: %s", e)
        return {}


def _initialize_environments():
    """Initialize environment list on first use."""
    global _environments
    if not _environments:
        _environments = _scan_environments()


# ============================================================================
# Subprocess Management
# ============================================================================


async def _spawn_training_run(run_state: RunState, config_path: Path):
    """
    Spawn the three processes needed for training:
    1. run-api (Atropos API server)
    2. launch_training.py (Tinker trainer + inference server)
    3. environment.py serve (the Atropos environment)
    """
    run_id = run_state.run_id

    _ensure_logs_dir()

    api_log = LOGS_DIR / f"api_{run_id}.log"
    trainer_log = LOGS_DIR / f"trainer_{run_id}.log"
    env_log = LOGS_DIR / f"env_{run_id}.log"

    try:
        logger.info("[%s] Starting Atropos API server (run-api)...", run_id)

        api_log_file = open(api_log, "w")
        run_state.api_log_file = api_log_file
        run_state.api_process = subprocess.Popen(
            ["run-api"],
            stdout=api_log_file,
            stderr=subprocess.STDOUT,
            cwd=str(TINKER_ATROPOS_ROOT),
        )

        await asyncio.sleep(5)

        if run_state.api_process.poll() is not None:
            run_state.status = "failed"
            run_state.error_message = (
                f"API server exited with code {run_state.api_process.returncode}. Check {api_log}"
            )
            _stop_training_run(run_state)
            return

        logger.info("[%s] Atropos API server started", run_id)

        logger.info(
            "[%s] Starting Tinker trainer: launch_training.py --config %s", run_id, config_path
        )

        trainer_log_file = open(trainer_log, "w")
        run_state.trainer_log_file = trainer_log_file
        run_state.trainer_process = subprocess.Popen(
            [sys.executable, "launch_training.py", "--config", str(config_path)],
            stdout=trainer_log_file,
            stderr=subprocess.STDOUT,
            cwd=str(TINKER_ATROPOS_ROOT),
            env={**os.environ, "TINKER_API_KEY": os.getenv("TINKER_API_KEY", "")},
        )

        logger.info("[%s] Waiting 30 seconds for trainer to initialize...", run_id)
        await asyncio.sleep(30)

        if run_state.trainer_process.poll() is not None:
            run_state.status = "failed"
            run_state.error_message = f"Trainer exited with code {run_state.trainer_process.returncode}. Check {trainer_log}"
            _stop_training_run(run_state)
            return

        logger.info("[%s] Trainer started, inference server on port 8001", run_id)

        logger.info("[%s] Waiting 90 more seconds before starting environment...", run_id)
        await asyncio.sleep(90)

        env_info = None
        for env in _environments:
            if env.name == run_state.environment:
                env_info = env
                break

        if not env_info:
            run_state.status = "failed"
            run_state.error_message = f"Environment '{run_state.environment}' not found"
            _stop_training_run(run_state)
            return

        logger.info("[%s] Starting environment: %s serve", run_id, env_info.file_path)

        env_log_file = open(env_log, "w")
        run_state.env_log_file = env_log_file
        run_state.env_process = subprocess.Popen(
            [sys.executable, str(env_info.file_path), "serve", "--config", str(config_path)],
            stdout=env_log_file,
            stderr=subprocess.STDOUT,
            cwd=str(TINKER_ATROPOS_ROOT),
        )

        await asyncio.sleep(10)

        if run_state.env_process.poll() is not None:
            run_state.status = "failed"
            run_state.error_message = (
                f"Environment exited with code {run_state.env_process.returncode}. Check {env_log}"
            )
            _stop_training_run(run_state)
            return

        run_state.status = "running"
        run_state.start_time = time.time()
        logger.info("[%s] Training run started successfully!", run_id)

        asyncio.create_task(_monitor_training_run(run_state))

    except Exception as e:
        run_state.status = "failed"
        run_state.error_message = str(e)
        _stop_training_run(run_state)


async def _monitor_training_run(run_state: RunState):
    """Background task to monitor a training run."""
    while run_state.status == "running":
        await asyncio.sleep(30)

        if run_state.env_process and run_state.env_process.poll() is not None:
            exit_code = run_state.env_process.returncode
            if exit_code == 0:
                run_state.status = "completed"
            else:
                run_state.status = "failed"
                run_state.error_message = f"Environment process exited with code {exit_code}"
            _stop_training_run(run_state)
            break

        if run_state.trainer_process and run_state.trainer_process.poll() is not None:
            exit_code = run_state.trainer_process.returncode
            if exit_code == 0:
                run_state.status = "completed"
            else:
                run_state.status = "failed"
                run_state.error_message = f"Trainer process exited with code {exit_code}"
            _stop_training_run(run_state)
            break

        if run_state.api_process and run_state.api_process.poll() is not None:
            run_state.status = "failed"
            run_state.error_message = "API server exited unexpectedly"
            _stop_training_run(run_state)
            break


def _stop_training_run(run_state: RunState):
    """Stop all processes for a training run."""
    if run_state.env_process and run_state.env_process.poll() is None:
        logger.info("[%s] Stopping environment process...", run_state.run_id)
        run_state.env_process.terminate()
        try:
            run_state.env_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            run_state.env_process.kill()

    if run_state.trainer_process and run_state.trainer_process.poll() is None:
        logger.info("[%s] Stopping trainer process...", run_state.run_id)
        run_state.trainer_process.terminate()
        try:
            run_state.trainer_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            run_state.trainer_process.kill()

    if run_state.api_process and run_state.api_process.poll() is None:
        logger.info("[%s] Stopping API server...", run_state.run_id)
        run_state.api_process.terminate()
        try:
            run_state.api_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            run_state.api_process.kill()

    if run_state.status == "running":
        run_state.status = "stopped"

    for attr in ("env_log_file", "trainer_log_file", "api_log_file"):
        fh = getattr(run_state, attr, None)
        if fh is not None:
            with contextlib.suppress(Exception):
                fh.close()
            setattr(run_state, attr, None)


# ============================================================================
# Environment Discovery Tools
# ============================================================================


async def rl_list_environments() -> str:
    """
    List all available RL environments.
    """
    _initialize_environments()

    response = {
        "environments": [
            {
                "name": env.name,
                "class_name": env.class_name,
                "file_path": env.file_path,
                "description": env.description,
            }
            for env in _environments
        ],
        "count": len(_environments),
        "tips": [
            "Use rl_select_environment(name) to select an environment",
            "Read the file_path with file tools to understand how each environment works",
            "Look for load_dataset(), score_answer(), get_next_item() methods",
        ],
    }

    return json.dumps(response, indent=2)


async def rl_select_environment(name: str) -> str:
    """
    Select an RL environment for training.
    """
    global _current_env, _current_config

    _initialize_environments()

    env_info = None
    for env in _environments:
        if env.name == name:
            env_info = env
            break

    if not env_info:
        return json.dumps(
            {
                "error": f"Environment '{name}' not found",
                "available": [e.name for e in _environments],
            },
            indent=2,
        )

    _current_env = name

    config_fields = _get_env_config_fields(env_info.file_path)
    _env_config_cache[name] = config_fields

    _current_config = {}
    for field_name, field_info in config_fields.items():
        if not field_info.get("locked", False):
            _current_config[field_name] = field_info.get("default")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    _current_config["wandb_name"] = f"{name}-{timestamp}"

    return json.dumps(
        {
            "message": f"Selected environment: {name}",
            "environment": name,
            "file_path": env_info.file_path,
        },
        indent=2,
    )


# ============================================================================
# Configuration Tools
# ============================================================================


async def rl_get_current_config() -> str:
    """
    Get the current environment configuration.
    """
    if not _current_env:
        return json.dumps(
            {
                "error": "No environment selected. Use rl_select_environment(name) first.",
            },
            indent=2,
        )

    config_fields = _env_config_cache.get(_current_env, {})

    configurable = []
    locked = []

    for field_name, field_info in config_fields.items():
        field_data = {
            "name": field_name,
            "type": field_info.get("type", "unknown"),
            "default": field_info.get("default"),
            "description": field_info.get("description", ""),
            "current_value": _current_config.get(field_name, field_info.get("default")),
        }

        if field_info.get("locked", False):
            field_data["locked_value"] = LOCKED_FIELDS.get("env", {}).get(field_name)
            locked.append(field_data)
        else:
            configurable.append(field_data)

    return json.dumps(
        {
            "environment": _current_env,
            "configurable_fields": configurable,
            "locked_fields": locked,
            "tip": "Use rl_edit_config(field, value) to change any configurable field.",
        },
        indent=2,
    )


async def rl_edit_config(field: str, value: Any) -> str:
    """
    Update a configuration field.
    """
    if not _current_env:
        return json.dumps(
            {
                "error": "No environment selected. Use rl_select_environment(name) first.",
            },
            indent=2,
        )

    config_fields = _env_config_cache.get(_current_env, {})

    if field not in config_fields:
        return json.dumps(
            {
                "error": f"Unknown field '{field}'",
                "available_fields": list(config_fields.keys()),
            },
            indent=2,
        )

    field_info = config_fields[field]
    if field_info.get("locked", False):
        return json.dumps(
            {
                "error": f"Field '{field}' is locked and cannot be changed",
                "locked_value": LOCKED_FIELDS.get("env", {}).get(field),
            },
            indent=2,
        )

    _current_config[field] = value

    return json.dumps(
        {
            "message": f"Updated {field} = {value}",
            "field": field,
            "value": value,
            "config": _current_config,
        },
        indent=2,
    )


# ============================================================================
# Training Management Tools
# ============================================================================


async def rl_start_training() -> str:
    """
    Start a new RL training run with the current environment and config.
    """
    if not _current_env:
        return json.dumps(
            {
                "error": "No environment selected. Use rl_select_environment(name) first.",
            },
            indent=2,
        )

    if not os.getenv("TINKER_API_KEY"):
        return json.dumps(
            {
                "error": "TINKER_API_KEY not set. Add it to ~/.prometheus/.env",
            },
            indent=2,
        )

    env_info = None
    for env in _environments:
        if env.name == _current_env:
            env_info = env
            break

    if not env_info or not Path(env_info.file_path).exists():
        return json.dumps(
            {
                "error": f"Environment file not found for '{_current_env}'",
            },
            indent=2,
        )

    run_id = str(uuid.uuid4())[:8]

    CONFIGS_DIR.mkdir(exist_ok=True)
    config_path = CONFIGS_DIR / f"run_{run_id}.yaml"

    import copy

    run_config = copy.deepcopy(LOCKED_FIELDS)

    if "env" not in run_config:
        run_config["env"] = {}

    for field_name, value in _current_config.items():
        if value is not None and value != "":
            run_config["env"][field_name] = value

    wandb_project = _current_config.get("wandb_project", "atropos-tinker")
    if "tinker" not in run_config:
        run_config["tinker"] = {}
    run_config["tinker"]["wandb_project"] = wandb_project
    run_config["tinker"]["wandb_run_name"] = f"{_current_env}-{run_id}"

    if "wandb_name" in _current_config and _current_config["wandb_name"]:
        run_config["env"]["wandb_name"] = _current_config["wandb_name"]

    with open(config_path, "w") as f:
        yaml.dump(run_config, f, default_flow_style=False)

    run_state = RunState(
        run_id=run_id,
        environment=_current_env,
        config=_current_config.copy(),
        status="starting",
        wandb_project=wandb_project,
        wandb_run_name=f"{_current_env}-{run_id}",
    )

    _active_runs[run_id] = run_state

    asyncio.create_task(_spawn_training_run(run_state, config_path))

    return json.dumps(
        {
            "run_id": run_id,
            "status": "starting",
            "environment": _current_env,
            "config": _current_config,
            "wandb_project": wandb_project,
            "wandb_run_name": f"{_current_env}-{run_id}",
            "config_path": str(config_path),
            "logs": {
                "api": str(LOGS_DIR / f"api_{run_id}.log"),
                "trainer": str(LOGS_DIR / f"trainer_{run_id}.log"),
                "env": str(LOGS_DIR / f"env_{run_id}.log"),
            },
            "message": "Training starting. Use rl_check_status(run_id) to monitor (recommended: every 30 minutes).",
        },
        indent=2,
    )


async def rl_check_status(run_id: str) -> str:
    """
    Get status and metrics for a training run.
    """
    now = time.time()
    if run_id in _last_status_check:
        elapsed = now - _last_status_check[run_id]
        if elapsed < MIN_STATUS_CHECK_INTERVAL:
            remaining = MIN_STATUS_CHECK_INTERVAL - elapsed
            return json.dumps(
                {
                    "rate_limited": True,
                    "run_id": run_id,
                    "message": f"Rate limited. Next check available in {remaining / 60:.0f} minutes.",
                    "next_check_in_seconds": remaining,
                },
                indent=2,
            )

    _last_status_check[run_id] = now

    if run_id not in _active_runs:
        return json.dumps(
            {
                "error": f"Run '{run_id}' not found",
                "active_runs": list(_active_runs.keys()),
            },
            indent=2,
        )

    run_state = _active_runs[run_id]

    processes = {
        "api": run_state.api_process.poll() if run_state.api_process else None,
        "trainer": run_state.trainer_process.poll() if run_state.trainer_process else None,
        "env": run_state.env_process.poll() if run_state.env_process else None,
    }

    running_time = time.time() - run_state.start_time if run_state.start_time else 0

    result = {
        "run_id": run_id,
        "status": run_state.status,
        "environment": run_state.environment,
        "running_time_minutes": running_time / 60,
        "processes": {
            name: "running" if code is None else f"exited ({code})"
            for name, code in processes.items()
        },
        "wandb_project": run_state.wandb_project,
        "wandb_run_name": run_state.wandb_run_name,
        "logs": {
            "api": str(LOGS_DIR / f"api_{run_id}.log"),
            "trainer": str(LOGS_DIR / f"trainer_{run_id}.log"),
            "env": str(LOGS_DIR / f"env_{run_id}.log"),
        },
    }

    if run_state.error_message:
        result["error"] = run_state.error_message

    try:
        import wandb

        api = wandb.Api()
        runs = api.runs(
            f"{os.getenv('WANDB_ENTITY', 'nousresearch')}/{run_state.wandb_project}",
            filters={"display_name": run_state.wandb_run_name},
        )
        if runs:
            wandb_run = runs[0]
            result["wandb_url"] = wandb_run.url
            result["metrics"] = {
                "step": wandb_run.summary.get("_step", 0),
                "reward_mean": wandb_run.summary.get("train/reward_mean"),
                "percent_correct": wandb_run.summary.get("train/percent_correct"),
                "eval_percent_correct": wandb_run.summary.get("eval/percent_correct"),
            }
    except Exception as e:
        result["wandb_error"] = str(e)

    return json.dumps(result, indent=2)


async def rl_stop_training(run_id: str) -> str:
    """
    Stop a running training job.
    """
    if run_id not in _active_runs:
        return json.dumps(
            {
                "error": f"Run '{run_id}' not found",
                "active_runs": list(_active_runs.keys()),
            },
            indent=2,
        )

    run_state = _active_runs[run_id]

    if run_state.status not in ("running", "starting"):
        return json.dumps(
            {
                "message": f"Run '{run_id}' is not running (status: {run_state.status})",
            },
            indent=2,
        )

    _stop_training_run(run_state)

    return json.dumps(
        {
            "message": f"Stopped training run '{run_id}'",
            "run_id": run_id,
            "status": run_state.status,
        },
        indent=2,
    )


async def rl_get_results(run_id: str) -> str:
    """
    Get final results and metrics for a training run.
    """
    if run_id not in _active_runs:
        return json.dumps(
            {
                "error": f"Run '{run_id}' not found",
            },
            indent=2,
        )

    run_state = _active_runs[run_id]

    result = {
        "run_id": run_id,
        "status": run_state.status,
        "environment": run_state.environment,
        "wandb_project": run_state.wandb_project,
        "wandb_run_name": run_state.wandb_run_name,
    }

    try:
        import wandb

        api = wandb.Api()
        runs = api.runs(
            f"{os.getenv('WANDB_ENTITY', 'nousresearch')}/{run_state.wandb_project}",
            filters={"display_name": run_state.wandb_run_name},
        )
        if runs:
            wandb_run = runs[0]
            result["wandb_url"] = wandb_run.url
            result["final_metrics"] = dict(wandb_run.summary)
            result["history"] = [dict(row) for row in wandb_run.history(samples=10)]
    except Exception as e:
        result["wandb_error"] = str(e)

    return json.dumps(result, indent=2)


async def rl_list_runs() -> str:
    """
    List all training runs (active and completed).
    """
    runs = []
    for run_id, run_state in _active_runs.items():
        runs.append(
            {
                "run_id": run_id,
                "environment": run_state.environment,
                "status": run_state.status,
                "wandb_run_name": run_state.wandb_run_name,
            }
        )

    return json.dumps(
        {
            "runs": runs,
            "count": len(runs),
        },
        indent=2,
    )


# ============================================================================
# Inference Testing (via Atropos `process` mode with OpenRouter)
# ============================================================================

TEST_MODELS = [
    {"id": "qwen/qwen3-8b", "name": "Qwen3 8B", "scale": "small"},
    {"id": "z-ai/glm-4.7-flash", "name": "GLM-4.7 Flash", "scale": "medium"},
    {"id": "minimax/minimax-m2.7", "name": "MiniMax M2.7", "scale": "large"},
]

DEFAULT_NUM_STEPS = 3
DEFAULT_GROUP_SIZE = 16


async def rl_test_inference(
    num_steps: int = DEFAULT_NUM_STEPS,
    group_size: int = DEFAULT_GROUP_SIZE,
    models: list[str] | None = None,
) -> str:
    """
    Quick inference test for any environment using Atropos's `process` mode.
    """
    if not _current_env:
        return json.dumps(
            {
                "error": "No environment selected. Use rl_select_environment(name) first.",
            },
            indent=2,
        )

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return json.dumps(
            {
                "error": "OPENROUTER_API_KEY not set. Required for inference testing.",
            },
            indent=2,
        )

    env_info = None
    for env in _environments:
        if env.name == _current_env:
            env_info = env
            break

    if not env_info:
        return json.dumps(
            {
                "error": f"Environment '{_current_env}' not found",
            },
            indent=2,
        )

    if models:
        test_models = [m for m in TEST_MODELS if m["id"] in models]
        if not test_models:
            test_models = [{"id": m, "name": m, "scale": "custom"} for m in models]
    else:
        test_models = TEST_MODELS

    total_rollouts_per_model = num_steps * group_size
    total_rollouts = total_rollouts_per_model * len(test_models)

    results = {
        "environment": _current_env,
        "environment_file": env_info.file_path,
        "test_config": {
            "num_steps": num_steps,
            "group_size": group_size,
            "rollouts_per_model": total_rollouts_per_model,
            "total_rollouts": total_rollouts,
        },
        "models_tested": [],
    }

    _ensure_logs_dir()
    test_output_dir = LOGS_DIR / "inference_tests"
    test_output_dir.mkdir(exist_ok=True)

    for model_info in test_models:
        model_id = model_info["id"]
        model_safe_name = model_id.replace("/", "_")

        print(f"\n{'=' * 60}")
        print(f"Testing with {model_info['name']} ({model_id})")
        print(f"{'=' * 60}")

        output_file = test_output_dir / f"test_{_current_env}_{model_safe_name}.jsonl"

        test_run_id = str(uuid.uuid4())[:8]
        wandb_run_name = f"test_inference_RSIAgent_{_current_env}_{test_run_id}"

        cmd = [
            sys.executable,
            env_info.file_path,
            "process",
            "--env.total_steps",
            str(num_steps),
            "--env.group_size",
            str(group_size),
            "--env.use_wandb",
            "true",
            "--env.wandb_name",
            wandb_run_name,
            "--env.data_path_to_save_groups",
            str(output_file),
            "--env.tokenizer_name",
            LOCKED_FIELDS["env"]["tokenizer_name"],
            "--env.max_token_length",
            str(LOCKED_FIELDS["env"]["max_token_length"]),
            "--env.max_num_workers",
            str(LOCKED_FIELDS["env"]["max_num_workers"]),
            "--env.max_batches_offpolicy",
            str(LOCKED_FIELDS["env"]["max_batches_offpolicy"]),
            "--openai.base_url",
            "https://openrouter.ai/api/v1",
            "--openai.api_key",
            api_key,
            "--openai.model_name",
            model_id,
            "--openai.server_type",
            "openai",
            "--openai.health_check",
            "false",
        ]

        cmd_str = " ".join(str(c) for c in cmd)
        cmd_display = cmd_str.replace(api_key, "***API_KEY***")
        print(f"Command: {cmd_display}")
        print(f"Working dir: {TINKER_ATROPOS_ROOT}")
        print(f"WandB run: {wandb_run_name}")
        print(
            f"  {num_steps} steps × {group_size} completions = {total_rollouts_per_model} rollouts"
        )

        model_results = {
            "model": model_id,
            "name": model_info["name"],
            "scale": model_info["scale"],
            "wandb_run": wandb_run_name,
            "output_file": str(output_file),
            "steps": [],
            "steps_tested": 0,
            "total_completions": 0,
            "correct_completions": 0,
        }

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(TINKER_ATROPOS_ROOT),
            )

            stdout_lines = []
            stderr_lines = []
            log_file = test_output_dir / f"test_{_current_env}_{model_safe_name}.log"

            async def read_stream(stream, lines_list, prefix=""):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    decoded = line.decode().rstrip()
                    lines_list.append(decoded)
                    if any(
                        kw in decoded.lower()
                        for kw in ["processing", "group", "step", "progress", "%", "completed"]
                    ):
                        print(f"  {prefix}{decoded}")

            try:
                await asyncio.wait_for(
                    asyncio.gather(
                        read_stream(process.stdout, stdout_lines, "📊 "),
                        read_stream(process.stderr, stderr_lines, "⚠️ "),
                    ),
                    timeout=600,
                )
            except TimeoutError:
                process.kill()
                raise

            await process.wait()

            stdout_text = "\n".join(stdout_lines)
            stderr_text = "\n".join(stderr_lines)

            with open(log_file, "w") as f:
                f.write(f"Command: {cmd_display}\n")
                f.write(f"Working dir: {TINKER_ATROPOS_ROOT}\n")
                f.write(f"Return code: {process.returncode}\n")
                f.write(f"\n{'=' * 60}\n")
                f.write(f"STDOUT:\n{'=' * 60}\n")
                f.write(stdout_text or "(empty)\n")
                f.write(f"\n{'=' * 60}\n")
                f.write(f"STDERR:\n{'=' * 60}\n")
                f.write(stderr_text or "(empty)\n")

            print(f"  Log file: {log_file}")

            if process.returncode != 0:
                model_results["error"] = f"Process exited with code {process.returncode}"
                model_results["stderr"] = stderr_text[-1000:]
                model_results["stdout"] = stdout_text[-1000:]
                model_results["log_file"] = str(log_file)
                print(f"\n  ❌ Error: {model_results['error']}")
                if stderr_lines:
                    print("  Last errors:")
                    for line in stderr_lines[-5:]:
                        print(f"    {line}")
            else:
                print("\n  ✅ Process completed successfully")
                print(f"  Output file: {output_file}")
                print(f"  File exists: {output_file.exists()}")

                if output_file.exists():
                    with open(output_file) as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                item = json.loads(line)
                                scores = item.get("scores", [])
                                model_results["steps_tested"] += 1
                                model_results["total_completions"] += len(scores)
                                correct = sum(1 for s in scores if s > 0)
                                model_results["correct_completions"] += correct

                                model_results["steps"].append(
                                    {
                                        "step": model_results["steps_tested"],
                                        "completions": len(scores),
                                        "correct": correct,
                                        "scores": scores,
                                    }
                                )
                            except json.JSONDecodeError:
                                continue

                    print(f"  Completed {model_results['steps_tested']} steps")
                else:
                    model_results["error"] = f"Output file not created: {output_file}"

        except TimeoutError:
            model_results["error"] = "Process timed out after 10 minutes"
            print("  Timeout!")
        except Exception as e:
            model_results["error"] = str(e)
            print(f"  Error: {e}")

        if model_results["total_completions"] > 0:
            model_results["accuracy"] = round(
                model_results["correct_completions"] / model_results["total_completions"], 3
            )
        else:
            model_results["accuracy"] = 0

        if model_results["steps_tested"] > 0:
            steps_with_correct = sum(1 for s in model_results["steps"] if s.get("correct", 0) > 0)
            model_results["steps_with_correct"] = steps_with_correct
            model_results["step_success_rate"] = round(
                steps_with_correct / model_results["steps_tested"], 3
            )
        else:
            model_results["steps_with_correct"] = 0
            model_results["step_success_rate"] = 0

        print(
            f"  Results: {model_results['correct_completions']}/{model_results['total_completions']} correct"
        )
        print(f"  Accuracy: {model_results['accuracy']:.1%}")

        results["models_tested"].append(model_results)

    working_models = [m for m in results["models_tested"] if m.get("steps_tested", 0) > 0]

    results["summary"] = {
        "steps_requested": num_steps,
        "models_tested": len(test_models),
        "models_succeeded": len(working_models),
        "best_model": max(working_models, key=lambda x: x.get("accuracy", 0))["model"]
        if working_models
        else None,
        "avg_accuracy": round(
            sum(m.get("accuracy", 0) for m in working_models) / len(working_models), 3
        )
        if working_models
        else 0,
        "environment_working": bool(working_models),
        "output_directory": str(test_output_dir),
    }

    return json.dumps(results, indent=2)


# ============================================================================
# Requirements Check
# ============================================================================


def check_rl_python_version() -> bool:
    """
    Check if Python version meets the minimum for RL tools.
    """
    return sys.version_info >= (3, 11)


def check_rl_api_keys() -> bool:
    """
    Check if required API keys and Python version are available.
    """
    if not check_rl_python_version():
        return False
    tinker_key = os.getenv("TINKER_API_KEY")
    wandb_key = os.getenv("WANDB_API_KEY")
    return bool(tinker_key) and bool(wandb_key)


def get_missing_keys() -> list[str]:
    """
    Get list of missing requirements for RL tools (API keys and Python version).
    """
    missing = []
    if not check_rl_python_version():
        missing.append(
            f"Python >= 3.11 (current: {sys.version_info.major}.{sys.version_info.minor})"
        )
    if not os.getenv("TINKER_API_KEY"):
        missing.append("TINKER_API_KEY")
    if not os.getenv("WANDB_API_KEY"):
        missing.append("WANDB_API_KEY")
    return missing


# ---------------------------------------------------------------------------
# Schemas + Registry
# ---------------------------------------------------------------------------
from prometheus.tools.registry import registry

RL_LIST_ENVIRONMENTS_SCHEMA = {
    "name": "rl_list_environments",
    "description": "List all available RL environments. Returns environment names, paths, and descriptions. TIP: Read the file_path with file tools to understand how each environment works (verifiers, data loading, rewards).",
    "parameters": {"type": "object", "properties": {}, "required": []},
}
RL_SELECT_ENVIRONMENT_SCHEMA = {
    "name": "rl_select_environment",
    "description": "Select an RL environment for training. Loads the environment's default configuration. After selecting, use rl_get_current_config() to see settings and rl_edit_config() to modify them.",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Name of the environment to select (from rl_list_environments)",
            }
        },
        "required": ["name"],
    },
}
RL_GET_CURRENT_CONFIG_SCHEMA = {
    "name": "rl_get_current_config",
    "description": "Get the current environment configuration. Returns only fields that can be modified: group_size, max_token_length, total_steps, steps_per_eval, use_wandb, wandb_name, max_num_workers.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}
RL_EDIT_CONFIG_SCHEMA = {
    "name": "rl_edit_config",
    "description": "Update a configuration field. Use rl_get_current_config() first to see all available fields for the selected environment. Each environment has different configurable options. Infrastructure settings (tokenizer, URLs, lora_rank, learning_rate) are locked.",
    "parameters": {
        "type": "object",
        "properties": {
            "field": {
                "type": "string",
                "description": "Name of the field to update (get available fields from rl_get_current_config)",
            },
            "value": {"description": "New value for the field"},
        },
        "required": ["field", "value"],
    },
}
RL_START_TRAINING_SCHEMA = {
    "name": "rl_start_training",
    "description": "Start a new RL training run with the current environment and config. Most training parameters (lora_rank, learning_rate, etc.) are fixed. Use rl_edit_config() to set group_size, batch_size, wandb_project before starting. WARNING: Training takes hours.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}
RL_CHECK_STATUS_SCHEMA = {
    "name": "rl_check_status",
    "description": "Get status and metrics for a training run. RATE LIMITED: enforces 30-minute minimum between checks for the same run. Returns WandB metrics: step, state, reward_mean, loss, percent_correct.",
    "parameters": {
        "type": "object",
        "properties": {
            "run_id": {"type": "string", "description": "The run ID from rl_start_training()"}
        },
        "required": ["run_id"],
    },
}
RL_STOP_TRAINING_SCHEMA = {
    "name": "rl_stop_training",
    "description": "Stop a running training job. Use if metrics look bad, training is stagnant, or you want to try different settings.",
    "parameters": {
        "type": "object",
        "properties": {"run_id": {"type": "string", "description": "The run ID to stop"}},
        "required": ["run_id"],
    },
}
RL_GET_RESULTS_SCHEMA = {
    "name": "rl_get_results",
    "description": "Get final results and metrics for a completed training run. Returns final metrics and path to trained weights.",
    "parameters": {
        "type": "object",
        "properties": {
            "run_id": {"type": "string", "description": "The run ID to get results for"}
        },
        "required": ["run_id"],
    },
}
RL_LIST_RUNS_SCHEMA = {
    "name": "rl_list_runs",
    "description": "List all training runs (active and completed) with their status.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}
RL_TEST_INFERENCE_SCHEMA = {
    "name": "rl_test_inference",
    "description": "Quick inference test for any environment. Runs a few steps of inference + scoring using OpenRouter. Default: 3 steps x 16 completions = 48 rollouts per model, testing 3 models = 144 total. Tests environment loading, prompt construction, inference parsing, and verifier logic. Use BEFORE training to catch issues.",
    "parameters": {
        "type": "object",
        "properties": {
            "num_steps": {
                "type": "integer",
                "description": "Number of steps to run (default: 3, recommended max for testing)",
                "default": 3,
            },
            "group_size": {
                "type": "integer",
                "description": "Completions per step (default: 16, like training)",
                "default": 16,
            },
            "models": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of OpenRouter model IDs. Default: qwen/qwen3-8b, z-ai/glm-4.7-flash, minimax/minimax-m2.7",
            },
        },
        "required": [],
    },
}

_rl_env = ["TINKER_API_KEY", "WANDB_API_KEY"]

registry.register(
    name="rl_list_environments",
    emoji="🧪",
    toolset="rl",
    schema=RL_LIST_ENVIRONMENTS_SCHEMA,
    handler=lambda args, **kw: rl_list_environments(),
    check_fn=check_rl_api_keys,
    requires_env=_rl_env,
    is_async=True,
)
registry.register(
    name="rl_select_environment",
    emoji="🧪",
    toolset="rl",
    schema=RL_SELECT_ENVIRONMENT_SCHEMA,
    handler=lambda args, **kw: rl_select_environment(name=args.get("name", "")),
    check_fn=check_rl_api_keys,
    requires_env=_rl_env,
    is_async=True,
)
registry.register(
    name="rl_get_current_config",
    emoji="🧪",
    toolset="rl",
    schema=RL_GET_CURRENT_CONFIG_SCHEMA,
    handler=lambda args, **kw: rl_get_current_config(),
    check_fn=check_rl_api_keys,
    requires_env=_rl_env,
    is_async=True,
)
registry.register(
    name="rl_edit_config",
    emoji="🧪",
    toolset="rl",
    schema=RL_EDIT_CONFIG_SCHEMA,
    handler=lambda args, **kw: rl_edit_config(field=args.get("field", ""), value=args.get("value")),
    check_fn=check_rl_api_keys,
    requires_env=_rl_env,
    is_async=True,
)
registry.register(
    name="rl_start_training",
    emoji="🧪",
    toolset="rl",
    schema=RL_START_TRAINING_SCHEMA,
    handler=lambda args, **kw: rl_start_training(),
    check_fn=check_rl_api_keys,
    requires_env=_rl_env,
    is_async=True,
)
registry.register(
    name="rl_check_status",
    emoji="🧪",
    toolset="rl",
    schema=RL_CHECK_STATUS_SCHEMA,
    handler=lambda args, **kw: rl_check_status(run_id=args.get("run_id", "")),
    check_fn=check_rl_api_keys,
    requires_env=_rl_env,
    is_async=True,
)
registry.register(
    name="rl_stop_training",
    emoji="🧪",
    toolset="rl",
    schema=RL_STOP_TRAINING_SCHEMA,
    handler=lambda args, **kw: rl_stop_training(run_id=args.get("run_id", "")),
    check_fn=check_rl_api_keys,
    requires_env=_rl_env,
    is_async=True,
)
registry.register(
    name="rl_get_results",
    emoji="🧪",
    toolset="rl",
    schema=RL_GET_RESULTS_SCHEMA,
    handler=lambda args, **kw: rl_get_results(run_id=args.get("run_id", "")),
    check_fn=check_rl_api_keys,
    requires_env=_rl_env,
    is_async=True,
)
registry.register(
    name="rl_list_runs",
    emoji="🧪",
    toolset="rl",
    schema=RL_LIST_RUNS_SCHEMA,
    handler=lambda args, **kw: rl_list_runs(),
    check_fn=check_rl_api_keys,
    requires_env=_rl_env,
    is_async=True,
)
registry.register(
    name="rl_test_inference",
    emoji="🧪",
    toolset="rl",
    schema=RL_TEST_INFERENCE_SCHEMA,
    handler=lambda args, **kw: rl_test_inference(
        num_steps=args.get("num_steps", 3),
        group_size=args.get("group_size", 16),
        models=args.get("models"),
    ),
    check_fn=check_rl_api_keys,
    requires_env=_rl_env,
    is_async=True,
)
