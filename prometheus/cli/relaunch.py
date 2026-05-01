from __future__ import annotations

import os
import sys
import time
import subprocess
from pathlib import Path
from typing import Optional

from prometheus.config import get_prometheus_home
from prometheus.cli.dump import save_dump


def relaunch(args: list[str] | None = None) -> None:
    dump_path = get_prometheus_home() / "pre_relaunch_state.json"
    save_dump(dump_path)
    
    executable = sys.executable
    main_module = "prometheus.cli.main"
    
    cmd = [executable, "-m", main_module]
    if args:
        cmd.extend(args)
    
    os.execv(executable, cmd)


def schedule_relaunch(delay_seconds: int, args: list[str] | None = None) -> None:
    dump_path = get_prometheus_home() / "scheduled_relaunch_state.json"
    save_dump(dump_path)
    
    executable = sys.executable
    main_module = "prometheus.cli.main"
    
    cmd = [executable, "-m", main_module]
    if args:
        cmd.extend(args)
    
    def do_relaunch():
        time.sleep(delay_seconds)
        subprocess.Popen(cmd, start_new_session=True)
    
    import threading
    thread = threading.Thread(target=do_relaunch, daemon=True)
    thread.start()


def check_relaunch_state() -> Optional[dict]:
    dump_path = get_prometheus_home() / "pre_relaunch_state.json"
    if dump_path.exists():
        import json
        try:
            with open(dump_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            dump_path.unlink()
            return state
        except Exception:
            return None
    return None
