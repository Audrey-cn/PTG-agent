"""Cron 调度器 - CronScheduler."""

from __future__ import annotations

import concurrent.futures
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

logger = logging.getLogger("prometheus.cron")

try:
    import fcntl
except ImportError:
    fcntl = None
    try:
        import msvcrt
    except ImportError:
        msvcrt = None

from prometheus._paths import get_paths

if TYPE_CHECKING:
    from pathlib import Path

LOCK_FILE_NAME = ".tick.lock"


@dataclass
class CronJob:
    """Cron 任务定义"""

    id: str
    name: str
    schedule: str
    command: str
    enabled: bool = True
    last_run: datetime | None = None
    next_run: datetime | None = None
    created_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


class CronScheduler:
    """Cron 调度器"""

    def __init__(self, tick_interval: int = 60):
        self.tick_interval = tick_interval
        self._running = False
        self._thread: threading.Thread | None = None
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        self._jobs: dict[str, CronJob] = {}
        self._lock = threading.Lock()
        self._tick_count = 0

    def start(self):
        """启动调度器"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Cron scheduler started")

    def stop(self):
        """停止调度器"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Cron scheduler stopped")

    def _run_loop(self):
        """主调度循环"""
        while self._running:
            try:
                self.tick()
            except Exception as e:
                logger.error(f"Tick error: {e}")
            time.sleep(self.tick_interval)

    def tick(self):
        """执行一次调度检查"""
        self._tick_count += 1

        lock_file = self._get_lock_file()
        if not self._acquire_lock(lock_file):
            logger.debug("Another tick is running, skipping")
            return

        try:
            due_jobs = self._get_due_jobs()
            for job in due_jobs:
                self._run_job(job)
        finally:
            self._release_lock(lock_file)

    def _get_lock_file(self) -> Path:
        """获取锁文件路径"""
        paths = get_paths()
        lock_dir = paths.home / "cron"
        lock_dir.mkdir(parents=True, exist_ok=True)
        return lock_dir / LOCK_FILE_NAME

    def _acquire_lock(self, lock_file: Path) -> bool:
        """获取文件锁"""
        if fcntl is None and msvcrt is None:
            return True

        try:
            lock_file.parent.mkdir(parents=True, exist_ok=True)
            self._lock_fd = open(lock_file, "w")

            if fcntl is not None:
                fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            elif msvcrt is not None:
                msvcrt.locking(self._lock_fd.fileno(), msvcrt.LK_NBLCK, 1)

            return True
        except OSError:
            return False

    def _release_lock(self, lock_file: Path):
        """释放文件锁"""
        if hasattr(self, "_lock_fd") and self._lock_fd:
            try:
                if fcntl is not None:
                    fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_UN)
                elif msvcrt is not None:
                    msvcrt.locking(self._lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
                self._lock_fd.close()
            except Exception:
                pass

    def _get_due_jobs(self) -> list[CronJob]:
        """获取所有到期的任务"""
        now = datetime.now()
        due = []

        with self._lock:
            for job in self._jobs.values():
                if not job.enabled:
                    continue
                if job.next_run and job.next_run <= now:
                    due.append(job)

        return due

    def _run_job(self, job: CronJob):
        """执行单个任务"""
        logger.info(f"Running cron job: {job.name} ({job.id})")

        try:
            job.last_run = datetime.now()
            job.next_run = self._calculate_next_run(job.schedule)

            future = self._executor.submit(self._execute_command, job.command)
            result = future.result(timeout=300)

            logger.info(
                f"Cron job completed: {job.name} - {result[:100] if result else 'no output'}"
            )

        except Exception as e:
            logger.error(f"Cron job failed: {job.name} - {e}")

    def _execute_command(self, command: str) -> str:
        """执行命令"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300,
            )
            return result.stdout + result.stderr
        except Exception as e:
            return f"Error: {str(e)}"

    def _calculate_next_run(self, schedule: str) -> datetime:
        """计算下次运行时间（简单实现）"""
        now = datetime.now()

        schedule = schedule.strip().lower()

        if schedule == "hourly":
            return now + timedelta(hours=1)
        elif schedule == "daily":
            return now + timedelta(days=1)
        elif schedule == "weekly":
            return now + timedelta(weeks=1)
        elif schedule.startswith("@every "):
            duration = schedule.split("@every ")[1].strip()
            if duration.endswith("s"):
                seconds = int(duration[:-1])
                return now + timedelta(seconds=seconds)
            elif duration.endswith("m"):
                minutes = int(duration[:-1])
                return now + timedelta(minutes=minutes)
            elif duration.endswith("h"):
                hours = int(duration[:-1])
                return now + timedelta(hours=hours)
            elif duration.endswith("d"):
                days = int(duration[:-1])
                return now + timedelta(days=days)

        return now + timedelta(hours=1)

    def add_job(self, job: CronJob) -> bool:
        """添加任务"""
        with self._lock:
            job.next_run = self._calculate_next_run(job.schedule)
            self._jobs[job.id] = job
            logger.info(f"Added cron job: {job.name}")
            return True

    def remove_job(self, job_id: str) -> bool:
        """移除任务"""
        with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
                logger.info(f"Removed cron job: {job_id}")
                return True
            return False

    def list_jobs(self) -> list[CronJob]:
        """列出所有任务"""
        with self._lock:
            return list(self._jobs.values())

    def get_job(self, job_id: str) -> CronJob | None:
        """获取任务"""
        with self._lock:
            return self._jobs.get(job_id)

    def enable_job(self, job_id: str) -> bool:
        """启用任务"""
        job = self.get_job(job_id)
        if job:
            job.enabled = True
            return True
        return False

    def disable_job(self, job_id: str) -> bool:
        """禁用任务"""
        job = self.get_job(job_id)
        if job:
            job.enabled = False
            return True
        return False

    @property
    def tick_count(self) -> int:
        """获取调度循环次数"""
        return self._tick_count


_scheduler_instance: CronScheduler | None = None
_scheduler_lock = threading.Lock()


def get_scheduler() -> CronScheduler:
    """获取全局调度器实例"""
    global _scheduler_instance
    with _scheduler_lock:
        if _scheduler_instance is None:
            _scheduler_instance = CronScheduler()
        return _scheduler_instance
