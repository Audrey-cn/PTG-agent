
"""
Prometheus snapshot and session management system
- Lightweight snapshot saving
- Resume from breakpoint
- Session logging
"""
import os
import hashlib
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


def get_checkpoints_dir():
    """Get snapshot directory"""
    from prometheus.config import get_prometheus_home
    return get_prometheus_home() / "checkpoints"


def get_sessions_dir():
    """Get session log directory"""
    from prometheus.config import get_prometheus_home
    return get_prometheus_home() / "sessions"


def _compute_file_hash(file_path):
    """Compute file hash"""
    if not file_path.exists():
        return ""
    try:
        content = file_path.read_bytes()
        return hashlib.md5(content).hexdigest()[:12]
    except Exception:
        return ""


def _ensure_dirs():
    """Ensure directories exist"""
    get_checkpoints_dir().mkdir(parents=True, exist_ok=True)
    get_sessions_dir().mkdir(parents=True, exist_ok=True)


class Checkpoint:
    """Snapshot data structure"""
    
    def __init__(self, name=None):
        self.timestamp = datetime.now().isoformat()
        self.name = name or f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.state = {}
        self.checksums = {}
        self.files_data = {}  # Save actual file content
    
    def to_dict(self):
        return {
            "timestamp": self.timestamp,
            "name": self.name,
            "state": self.state,
            "checksums": self.checksums,
            "files_data": self.files_data
        }
    
    @classmethod
    def from_dict(cls, data):
        cp = cls(data.get("name"))
        cp.timestamp = data.get("timestamp", cp.timestamp)
        cp.state = data.get("state", {})
        cp.checksums = data.get("checksums", {})
        cp.files_data = data.get("files_data", {})
        return cp


class CheckpointSystem:
    """Snapshot manager"""
    
    def __init__(self):
        _ensure_dirs()
        from prometheus.config import PrometheusConfig
        self.config = PrometheusConfig.load()
        self.max_snapshots = self.config.get("checkpoints.max_snapshots", 50)
    
    def _get_critical_files(self):
        """Get list of critical files"""
        from prometheus.config import get_config_path
        from prometheus.memory_system import (
            get_user_profile_path,
            get_memory_path,
            get_soul_path
        )
        return [
            get_config_path(),
            get_user_profile_path(),
            get_memory_path(),
            get_soul_path()
        ]
    
    def create_snapshot(self, name=None, additional_state=None, save_files=True):
        """
        Create snapshot
        
        Args:
            name: Snapshot name (optional)
            additional_state: Additional state (optional)
            save_files: Whether to save actual file content (default True)
        
        Returns:
            Checkpoint object
        """
        cp = Checkpoint(name)
        
        # Record critical state
        cp.state["timestamp"] = datetime.now().isoformat()
        cp.state["working_dir"] = str(Path.cwd())
        
        if additional_state:
            cp.state.update(additional_state)
        
        # Compute critical file hashes and save content
        for file_path in self._get_critical_files():
            cp.checksums[str(file_path)] = _compute_file_hash(file_path)
            
            if save_files and file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        cp.files_data[str(file_path)] = f.read()
                except Exception as e:
                    logger.warning(f"Failed to save file {file_path}: {e}")
        
        self._save_snapshot(cp)
        self._cleanup_old_snapshots()
        
        logger.info("Snapshot created: %s", cp.name)
        return cp
    
    def _save_snapshot(self, checkpoint):
        """Save snapshot to file"""
        snapshot_file = get_checkpoints_dir() / f"{checkpoint.name}.json"
        try:
            with open(snapshot_file, "w", encoding="utf-8") as f:
                json.dump(checkpoint.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("Failed to save snapshot: %s", e)
        
        # Also save as latest
        latest_file = get_checkpoints_dir() / "latest.json"
        try:
            with open(latest_file, "w", encoding="utf-8") as f:
                json.dump(checkpoint.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("Failed to update latest snapshot: %s", e)
    
    def list_snapshots(self):
        """List all snapshots"""
        snapshots = []
        checkpoints_dir = get_checkpoints_dir()
        
        for f in checkpoints_dir.glob("*.json"):
            if f.name == "latest.json":
                continue
            try:
                with open(f, "r", encoding="utf-8") as fobj:
                    data = json.load(fobj)
                    snapshots.append(data)
            except Exception as e:
                logger.warning("Failed to read snapshot: %s: %s", f, e)
        
        snapshots.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return snapshots
    
    def get_snapshot(self, name):
        """Get specific snapshot"""
        if name == "latest":
            snapshot_file = get_checkpoints_dir() / "latest.json"
        else:
            snapshot_file = get_checkpoints_dir() / f"{name}.json"
        
        if not snapshot_file.exists():
            return None
        
        try:
            with open(snapshot_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return Checkpoint.from_dict(data)
        except Exception as e:
            logger.error("Failed to read snapshot: %s", e)
            return None
    
    def restore_snapshot(self, name, confirm=False):
        """
        Restore snapshot
        
        Args:
            name: Snapshot name
            confirm: Whether to confirm restore (default False, only check differences)
        
        Returns:
            Restore result
        """
        cp = self.get_snapshot(name)
        if not cp:
            return {"success": False, "error": "Snapshot not found"}
        
        result = {
            "success": True,
            "name": cp.name,
            "timestamp": cp.timestamp,
            "state": cp.state,
            "changed_files": [],
            "restored": []
        }
        
        for file_path_str, old_hash in cp.checksums.items():
            file_path = Path(file_path_str)
            current_hash = _compute_file_hash(file_path)
            changed = old_hash != current_hash
            file_info = {
                "file": str(file_path),
                "old_hash": old_hash,
                "current_hash": current_hash,
                "changed": changed
            }
            result["changed_files"].append(file_info)
        
        if confirm:
            for file_path_str, content in cp.files_data.items():
                file_path = Path(file_path_str)
                try:
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    result["restored"].append(file_path_str)
                    logger.info(f"Restored file: {file_path_str}")
                except Exception as e:
                    logger.error(f"Failed to restore file {file_path_str}: {e}")
                    result["success"] = False
                    result.setdefault("errors", []).append(str(e))
        
        return result
    
    def _cleanup_old_snapshots(self):
        """Clean up old snapshots"""
        snapshots = self.list_snapshots()
        if len(snapshots) <= self.max_snapshots:
            return
        
        for i, s in enumerate(snapshots):
            if i >= self.max_snapshots:
                name = s.get("name", "")
                snapshot_file = get_checkpoints_dir() / f"{name}.json"
                if snapshot_file.exists():
                    try:
                        snapshot_file.unlink()
                        logger.info("Cleaned up old snapshot: %s", name)
                    except Exception as e:
                        logger.warning("Failed to delete snapshot: %s", e)


class SessionLogger:
    """Session logger"""
    
    def __init__(self):
        _ensure_dirs()
    
    def _get_log_file(self):
        """Get current log file (per day)"""
        date_str = datetime.now().strftime("%Y%m%d")
        return get_sessions_dir() / f"{date_str}.jsonl"
    
    def log_event(self, event_type, **kwargs):
        """Log event"""
        log_file = self._get_log_file()
        
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type
        }
        event.update(kwargs)
        
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning("Failed to log event: %s", e)
    
    def log_command(self, command, args=None):
        """Log command execution"""
        self.log_event("command", command=command, args=args)
    
    def log_snapshot(self, snapshot_name):
        """Log snapshot creation"""
        self.log_event("snapshot", snapshot_name=snapshot_name)
    
    def log_error(self, error, traceback=None):
        """Log error"""
        self.log_event("error", error=error, traceback=traceback)
    
    def get_recent_events(self, limit=100):
        """Get recent events"""
        log_file = self._get_log_file()
        if not log_file.exists():
            return []
        
        events = []
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        events.append(json.loads(line))
        except Exception as e:
            logger.warning("Failed to read log: %s", e)
        
        return events[-limit:]


_checkpoint_system = None
_session_logger = None


def get_checkpoint_system():
    """Get checkpoint system singleton"""
    global _checkpoint_system
    if _checkpoint_system is None:
        _checkpoint_system = CheckpointSystem()
    return _checkpoint_system


def get_session_logger():
    """Get session logger singleton"""
    global _session_logger
    if _session_logger is None:
        _session_logger = SessionLogger()
    return _session_logger

