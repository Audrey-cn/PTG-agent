"""Cron job storage and management."""

import copy
import json
import logging
import os
import re
import tempfile
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from prometheus.constants_core import get_prometheus_home

logger = logging.getLogger(__name__)

import contextlib

from prometheus_time import now as _prometheus_now

from prometheus.utils import atomic_replace

try:
    from croniter import croniter

    HAS_CRONITER = True
except ImportError:
    HAS_CRONITER = False

# =============================================================================
# Configuration
# =============================================================================

PROMETHEUS_DIR = get_prometheus_home().resolve()
CRON_DIR = PROMETHEUS_DIR / "cron"
JOBS_FILE = CRON_DIR / "jobs.json"

# In-process lock protecting load_jobs→modify→save_jobs cycles.
# Required when tick() runs jobs in parallel threads — without this,
# concurrent mark_job_run / advance_next_run calls can clobber each other.
_jobs_file_lock = threading.Lock()
OUTPUT_DIR = CRON_DIR / "output"
ONESHOT_GRACE_SECONDS = 120


def _normalize_skill_list(skill: str | None = None, skills: Any | None = None) -> list[str]:
    """Normalize legacy/single-skill and multi-skill inputs into a unique ordered list."""
    if skills is None:
        raw_items = [skill] if skill else []
    elif isinstance(skills, str):
        raw_items = [skills]
    else:
        raw_items = list(skills)

    normalized: list[str] = []
    for item in raw_items:
        text = str(item or "").strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _apply_skill_fields(job: dict[str, Any]) -> dict[str, Any]:
    """Return a job dict with canonical `skills` and legacy `skill` fields aligned."""
    normalized = dict(job)
    skills = _normalize_skill_list(normalized.get("skill"), normalized.get("skills"))
    normalized["skills"] = skills
    normalized["skill"] = skills[0] if skills else None
    return normalized


def _secure_dir(path: Path):
    """Set directory to owner-only access (0700). No-op on Windows."""
    with contextlib.suppress(OSError, NotImplementedError):
        os.chmod(path, 0o700)


def _secure_file(path: Path):
    """Set file to owner-only read/write (0600). No-op on Windows."""
    try:
        if path.exists():
            os.chmod(path, 0o600)
    except (OSError, NotImplementedError):
        pass


def ensure_dirs():
    """Ensure cron directories exist with secure permissions."""
    CRON_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _secure_dir(CRON_DIR)
    _secure_dir(OUTPUT_DIR)


# =============================================================================
# Schedule Parsing
# =============================================================================


def parse_duration(s: str) -> int:
    """
    Parse duration string into minutes.

    Examples:
        "30m" → 30
        "2h" → 120
        "1d" → 1440
    """
    s = s.strip().lower()
    match = re.match(r"^(\d+)\s*(m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)$", s)
    if not match:
        raise ValueError(f"Invalid duration: '{s}'. Use format like '30m', '2h', or '1d'")

    value = int(match.group(1))
    unit = match.group(2)[0]

    multipliers = {"m": 1, "h": 60, "d": 1440}
    return value * multipliers[unit]


def parse_schedule(schedule: str) -> dict[str, Any]:
    """
    Parse schedule string into structured format.

    Returns dict with:
        - kind: "once" | "interval" | "cron"
        - For "once": "run_at" (ISO timestamp)
        - For "interval": "minutes" (int)
        - For "cron": "expr" (cron expression)

    Examples:
        "30m"              → once in 30 minutes
        "2h"               → once in 2 hours
        "every 30m"        → recurring every 30 minutes
        "every 2h"         → recurring every 2 hours
        "0 9 * * *"        → cron expression
        "2026-02-03T14:00" → once at timestamp
    """
    schedule = schedule.strip()
    original = schedule
    schedule_lower = schedule.lower()

    if schedule_lower.startswith("every "):
        duration_str = schedule[6:].strip()
        minutes = parse_duration(duration_str)
        return {"kind": "interval", "minutes": minutes, "display": f"every {minutes}m"}

    parts = schedule.split()
    if len(parts) >= 5 and all(re.match(r"^[\d\*\-,/]+$", p) for p in parts[:5]):
        if not HAS_CRONITER:
            raise ValueError(
                "Cron expressions require 'croniter' package. Install with: pip install croniter"
            )
        try:
            croniter(schedule)
        except Exception as e:
            raise ValueError(f"Invalid cron expression '{schedule}': {e}")
        return {"kind": "cron", "expr": schedule, "display": schedule}

    if "T" in schedule or re.match(r"^\d{4}-\d{2}-\d{2}", schedule):
        try:
            dt = datetime.fromisoformat(schedule.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.astimezone()
            return {
                "kind": "once",
                "run_at": dt.isoformat(),
                "display": f"once at {dt.strftime('%Y-%m-%d %H:%M')}",
            }
        except ValueError as e:
            raise ValueError(f"Invalid timestamp '{schedule}': {e}")

    try:
        minutes = parse_duration(schedule)
        run_at = _prometheus_now() + timedelta(minutes=minutes)
        return {"kind": "once", "run_at": run_at.isoformat(), "display": f"once in {original}"}
    except ValueError:
        pass

    raise ValueError(
        f"Invalid schedule '{original}'. Use:\n"
        f"  - Duration: '30m', '2h', '1d' (one-shot)\n"
        f"  - Interval: 'every 30m', 'every 2h' (recurring)\n"
        f"  - Cron: '0 9 * * *' (cron expression)\n"
        f"  - Timestamp: '2026-02-03T14:00:00' (one-shot at time)"
    )


def _ensure_aware(dt: datetime) -> datetime:
    """Return a timezone-aware datetime in Prometheus configured timezone.

    Backward compatibility:
    - Older stored timestamps may be naive.
    - Naive values are interpreted as *system-local wall time* (the timezone
      `datetime.now()` used when they were created), then converted to the
      configured Prometheus timezone.

    This preserves relative ordering for legacy naive timestamps across
    timezone changes and avoids false not-due results.
    """
    target_tz = _prometheus_now().tzinfo
    if dt.tzinfo is None:
        local_tz = datetime.now().astimezone().tzinfo
        return dt.replace(tzinfo=local_tz).astimezone(target_tz)
    return dt.astimezone(target_tz)


def _recoverable_oneshot_run_at(
    schedule: dict[str, Any],
    now: datetime,
    *,
    last_run_at: str | None = None,
) -> str | None:
    """Return a one-shot run time if it is still eligible to fire.

    One-shot jobs get a small grace window so jobs created a few seconds after
    their requested minute still run on the next tick. Once a one-shot has
    already run, it is never eligible again.
    """
    if schedule.get("kind") != "once":
        return None
    if last_run_at:
        return None

    run_at = schedule.get("run_at")
    if not run_at:
        return None

    run_at_dt = _ensure_aware(datetime.fromisoformat(run_at))
    if run_at_dt >= now - timedelta(seconds=ONESHOT_GRACE_SECONDS):
        return run_at
    return None


def _compute_grace_seconds(schedule: dict) -> int:
    """Compute how late a job can be and still catch up instead of fast-forwarding.

    Uses half the schedule period, clamped between 120 seconds and 2 hours.
    This ensures daily jobs can catch up if missed by up to 2 hours,
    while frequent jobs (every 5-10 min) still fast-forward quickly.
    """
    MIN_GRACE = 120
    MAX_GRACE = 7200

    kind = schedule.get("kind")

    if kind == "interval":
        period_seconds = schedule.get("minutes", 1) * 60
        grace = period_seconds // 2
        return max(MIN_GRACE, min(grace, MAX_GRACE))

    if kind == "cron" and HAS_CRONITER:
        try:
            now = _prometheus_now()
            cron = croniter(schedule["expr"], now)
            first = cron.get_next(datetime)
            second = cron.get_next(datetime)
            period_seconds = int((second - first).total_seconds())
            grace = period_seconds // 2
            return max(MIN_GRACE, min(grace, MAX_GRACE))
        except Exception:
            pass

    return MIN_GRACE


def compute_next_run(schedule: dict[str, Any], last_run_at: str | None = None) -> str | None:
    """
    Compute the next run time for a schedule.

    Returns ISO timestamp string, or None if no more runs.
    """
    now = _prometheus_now()

    if schedule["kind"] == "once":
        return _recoverable_oneshot_run_at(schedule, now, last_run_at=last_run_at)

    elif schedule["kind"] == "interval":
        minutes = schedule["minutes"]
        if last_run_at:
            last = _ensure_aware(datetime.fromisoformat(last_run_at))
            next_run = last + timedelta(minutes=minutes)
        else:
            next_run = now + timedelta(minutes=minutes)
        return next_run.isoformat()

    elif schedule["kind"] == "cron":
        if not HAS_CRONITER:
            logger.warning(
                "Cannot compute next run for cron schedule %r: 'croniter' is "
                "not installed. croniter is a core dependency as of v0.9.x; "
                "reinstall prometheus-agent or run 'pip install croniter' in your "
                "runtime env.",
                schedule.get("expr"),
            )
            return None
        base_time = now
        if last_run_at:
            base_time = _ensure_aware(datetime.fromisoformat(last_run_at))
        cron = croniter(schedule["expr"], base_time)
        next_run = cron.get_next(datetime)
        return next_run.isoformat()

    return None


# =============================================================================
# Job CRUD Operations
# =============================================================================


def load_jobs() -> list[dict[str, Any]]:
    """Load all jobs from storage."""
    ensure_dirs()
    if not JOBS_FILE.exists():
        return []

    try:
        with open(JOBS_FILE, encoding="utf-8") as f:
            data = json.load(f)
            return data.get("jobs", [])
    except json.JSONDecodeError:
        try:
            with open(JOBS_FILE, encoding="utf-8") as f:
                data = json.loads(f.read(), strict=False)
                jobs = data.get("jobs", [])
                if jobs:
                    save_jobs(jobs)
                    logger.warning("Auto-repaired jobs.json (had invalid control characters)")
                return jobs
        except Exception as e:
            logger.error("Failed to auto-repair jobs.json: %s", e)
            raise RuntimeError(f"Cron database corrupted and unrepairable: {e}") from e
    except OSError as e:
        logger.error("IOError reading jobs.json: %s", e)
        raise RuntimeError(f"Failed to read cron database: {e}") from e


def save_jobs(jobs: list[dict[str, Any]]):
    """Save all jobs to storage."""
    ensure_dirs()
    fd, tmp_path = tempfile.mkstemp(dir=str(JOBS_FILE.parent), suffix=".tmp", prefix=".jobs_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"jobs": jobs, "updated_at": _prometheus_now().isoformat()}, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        atomic_replace(tmp_path, JOBS_FILE)
        _secure_file(JOBS_FILE)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


def _normalize_workdir(workdir: str | None) -> str | None:
    """Normalize and validate a cron job workdir.

    Rules:
      - Empty / None → None (feature off, preserves old behaviour).
      - ``~`` is expanded.  Relative paths are rejected — cron jobs run detached
        from any shell cwd, so relative paths have no stable meaning.
      - The path must exist and be a directory at create/update time.

    Returns the absolute path string, or None when disabled.
    Raises ValueError on invalid input.
    """
    if workdir is None:
        return None
    raw = str(workdir).strip()
    if not raw:
        return None
    expanded = Path(raw).expanduser()
    if not expanded.is_absolute():
        raise ValueError(
            f"Cron workdir must be an absolute path (got {raw!r}). "
            f"Cron jobs run detached from any shell cwd, so relative paths are ambiguous."
        )
    resolved = expanded.resolve()
    if not resolved.exists():
        raise ValueError(f"Cron workdir does not exist: {resolved}")
    if not resolved.is_dir():
        raise ValueError(f"Cron workdir is not a directory: {resolved}")
    return str(resolved)


def create_job(
    prompt: str,
    schedule: str,
    name: str | None = None,
    repeat: int | None = None,
    deliver: str | None = None,
    origin: dict[str, Any] | None = None,
    skill: str | None = None,
    skills: list[str] | None = None,
    model: str | None = None,
    provider: str | None = None,
    base_url: str | None = None,
    script: str | None = None,
    context_from: str | list[str] | None = None,
    enabled_toolsets: list[str] | None = None,
    workdir: str | None = None,
) -> dict[str, Any]:
    """
    Create a new cron job.

    Args:
        prompt: The prompt to run (must be self-contained, or a task instruction when skill is set)
        schedule: Schedule string (see parse_schedule)
        name: Optional friendly name
        repeat: How many times to run (None = forever, 1 = once)
        deliver: Where to deliver output ("origin", "local", "telegram", etc.)
        origin: Source info where job was created (for "origin" delivery)
        skill: Optional legacy single skill name to load before running the prompt
        skills: Optional ordered list of skills to load before running the prompt
        model: Optional per-job model override
        provider: Optional per-job provider override
        base_url: Optional per-job base URL override
        script: Optional path to a Python script whose stdout is injected into the
                prompt each run.
        context_from: Optional job ID (or list of job IDs) whose most recent output
                      is injected into the prompt as context before each run.
        enabled_toolsets: Optional list of toolset names to restrict the agent to.
        workdir: Optional absolute path.

    Returns:
        The created job dict
    """
    parsed_schedule = parse_schedule(schedule)

    if repeat is not None and repeat <= 0:
        repeat = None

    if parsed_schedule["kind"] == "once" and repeat is None:
        repeat = 1

    if deliver is None:
        deliver = "origin" if origin else "local"

    job_id = uuid.uuid4().hex[:12]
    now = _prometheus_now().isoformat()

    normalized_skills = _normalize_skill_list(skill, skills)
    normalized_model = str(model).strip() if isinstance(model, str) else None
    normalized_provider = str(provider).strip() if isinstance(provider, str) else None
    normalized_base_url = str(base_url).strip().rstrip("/") if isinstance(base_url, str) else None
    normalized_model = normalized_model or None
    normalized_provider = normalized_provider or None
    normalized_base_url = normalized_base_url or None
    normalized_script = str(script).strip() if isinstance(script, str) else None
    normalized_script = normalized_script or None
    normalized_toolsets = (
        [str(t).strip() for t in enabled_toolsets if str(t).strip()] if enabled_toolsets else None
    )
    normalized_toolsets = normalized_toolsets or None
    normalized_workdir = _normalize_workdir(workdir)

    if isinstance(context_from, str):
        context_from = [context_from.strip()] if context_from.strip() else None
    elif isinstance(context_from, list):
        context_from = [str(j).strip() for j in context_from if str(j).strip()] or None
    else:
        context_from = None

    label_source = (prompt or (normalized_skills[0] if normalized_skills else None)) or "cron job"
    job = {
        "id": job_id,
        "name": name or label_source[:50].strip(),
        "prompt": prompt,
        "skills": normalized_skills,
        "skill": normalized_skills[0] if normalized_skills else None,
        "model": normalized_model,
        "provider": normalized_provider,
        "base_url": normalized_base_url,
        "script": normalized_script,
        "context_from": context_from,
        "schedule": parsed_schedule,
        "schedule_display": parsed_schedule.get("display", schedule),
        "repeat": {"times": repeat, "completed": 0},
        "enabled": True,
        "state": "scheduled",
        "paused_at": None,
        "paused_reason": None,
        "created_at": now,
        "next_run_at": compute_next_run(parsed_schedule),
        "last_run_at": None,
        "last_status": None,
        "last_error": None,
        "last_delivery_error": None,
        "deliver": deliver,
        "origin": origin,
        "enabled_toolsets": normalized_toolsets,
        "workdir": normalized_workdir,
    }

    jobs = load_jobs()
    jobs.append(job)
    save_jobs(jobs)

    return job


def get_job(job_id: str) -> dict[str, Any] | None:
    """Get a job by ID."""
    jobs = load_jobs()
    for job in jobs:
        if job["id"] == job_id:
            return _apply_skill_fields(job)
    return None


def list_jobs(include_disabled: bool = False) -> list[dict[str, Any]]:
    """List all jobs, optionally including disabled ones."""
    jobs = [_apply_skill_fields(j) for j in load_jobs()]
    if not include_disabled:
        jobs = [j for j in jobs if j.get("enabled", True)]
    return jobs


def update_job(job_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    """Update a job by ID, refreshing derived schedule fields when needed."""
    jobs = load_jobs()
    for i, job in enumerate(jobs):
        if job["id"] != job_id:
            continue

        if "workdir" in updates:
            _wd = updates["workdir"]
            if _wd in (None, "", False):
                updates["workdir"] = None
            else:
                updates["workdir"] = _normalize_workdir(_wd)

        updated = _apply_skill_fields({**job, **updates})
        schedule_changed = "schedule" in updates

        if "skills" in updates or "skill" in updates:
            normalized_skills = _normalize_skill_list(updated.get("skill"), updated.get("skills"))
            updated["skills"] = normalized_skills
            updated["skill"] = normalized_skills[0] if normalized_skills else None

        if schedule_changed:
            updated_schedule = updated["schedule"]
            if isinstance(updated_schedule, str):
                updated_schedule = parse_schedule(updated_schedule)
                updated["schedule"] = updated_schedule
            updated["schedule_display"] = updates.get(
                "schedule_display",
                updated_schedule.get("display", updated.get("schedule_display")),
            )
            if updated.get("state") != "paused":
                updated["next_run_at"] = compute_next_run(updated_schedule)

        if (
            updated.get("enabled", True)
            and updated.get("state") != "paused"
            and not updated.get("next_run_at")
        ):
            updated["next_run_at"] = compute_next_run(updated["schedule"])

        jobs[i] = updated
        save_jobs(jobs)
        return _apply_skill_fields(jobs[i])
    return None


def pause_job(job_id: str, reason: str | None = None) -> dict[str, Any] | None:
    """Pause a job without deleting it."""
    return update_job(
        job_id,
        {
            "enabled": False,
            "state": "paused",
            "paused_at": _prometheus_now().isoformat(),
            "paused_reason": reason,
        },
    )


def resume_job(job_id: str) -> dict[str, Any] | None:
    """Resume a paused job and compute the next future run from now."""
    job = get_job(job_id)
    if not job:
        return None

    next_run_at = compute_next_run(job["schedule"])
    return update_job(
        job_id,
        {
            "enabled": True,
            "state": "scheduled",
            "paused_at": None,
            "paused_reason": None,
            "next_run_at": next_run_at,
        },
    )


def trigger_job(job_id: str) -> dict[str, Any] | None:
    """Schedule a job to run on the next scheduler tick."""
    job = get_job(job_id)
    if not job:
        return None
    return update_job(
        job_id,
        {
            "enabled": True,
            "state": "scheduled",
            "paused_at": None,
            "paused_reason": None,
            "next_run_at": _prometheus_now().isoformat(),
        },
    )


def remove_job(job_id: str) -> bool:
    """Remove a job by ID."""
    jobs = load_jobs()
    original_len = len(jobs)
    jobs = [j for j in jobs if j["id"] != job_id]
    if len(jobs) < original_len:
        save_jobs(jobs)
        return True
    return False


def mark_job_run(
    job_id: str, success: bool, error: str | None = None, delivery_error: str | None = None
):
    """
    Mark a job as having been run.

    Updates last_run_at, last_status, increments completed count,
    computes next_run_at, and auto-deletes if repeat limit reached.
    """
    with _jobs_file_lock:
        jobs = load_jobs()
        for i, job in enumerate(jobs):
            if job["id"] == job_id:
                now = _prometheus_now().isoformat()
                job["last_run_at"] = now
                job["last_status"] = "ok" if success else "error"
                job["last_error"] = error if not success else None
                job["last_delivery_error"] = delivery_error

                if job.get("repeat"):
                    job["repeat"]["completed"] = job["repeat"].get("completed", 0) + 1

                    times = job["repeat"].get("times")
                    completed = job["repeat"]["completed"]
                    if times is not None and times > 0 and completed >= times:
                        jobs.pop(i)
                        save_jobs(jobs)
                        return

                job["next_run_at"] = compute_next_run(job["schedule"], now)

                if job["next_run_at"] is None:
                    kind = job.get("schedule", {}).get("kind")
                    if kind in ("cron", "interval"):
                        job["state"] = "error"
                        if not job.get("last_error"):
                            job["last_error"] = (
                                "Failed to compute next run for recurring "
                                "schedule (is the 'croniter' package "
                                "installed in the gateway's Python env?)"
                            )
                        logger.error(
                            "Job '%s' (%s) could not compute next_run_at; "
                            "leaving enabled and marking state=error so the "
                            "job is not silently disabled.",
                            job.get("name", job["id"]),
                            kind,
                        )
                    else:
                        job["enabled"] = False
                        job["state"] = "completed"
                elif job.get("state") != "paused":
                    job["state"] = "scheduled"

                save_jobs(jobs)
                return

        logger.warning("mark_job_run: job_id %s not found, skipping save", job_id)


def advance_next_run(job_id: str) -> bool:
    """Preemptively advance next_run_at for a recurring job before execution."""
    with _jobs_file_lock:
        jobs = load_jobs()
        for job in jobs:
            if job["id"] == job_id:
                kind = job.get("schedule", {}).get("kind")
                if kind not in ("cron", "interval"):
                    return False
                now = _prometheus_now().isoformat()
                new_next = compute_next_run(job["schedule"], now)
                if new_next and new_next != job.get("next_run_at"):
                    job["next_run_at"] = new_next
                    save_jobs(jobs)
                    return True
                return False
        return False


def get_due_jobs() -> list[dict[str, Any]]:
    """Get all jobs that are due to run now."""
    now = _prometheus_now()
    raw_jobs = load_jobs()
    jobs = [_apply_skill_fields(j) for j in copy.deepcopy(raw_jobs)]
    due = []
    needs_save = False

    for job in jobs:
        if not job.get("enabled", True):
            continue

        next_run = job.get("next_run_at")
        if not next_run:
            recovered_next = _recoverable_oneshot_run_at(
                job.get("schedule", {}),
                now,
                last_run_at=job.get("last_run_at"),
            )
            if not recovered_next:
                continue

            job["next_run_at"] = recovered_next
            next_run = recovered_next
            logger.info(
                "Job '%s' had no next_run_at; recovering one-shot run at %s",
                job.get("name", job["id"]),
                recovered_next,
            )
            for rj in raw_jobs:
                if rj["id"] == job["id"]:
                    rj["next_run_at"] = recovered_next
                    needs_save = True
                    break

        next_run_dt = _ensure_aware(datetime.fromisoformat(next_run))
        if next_run_dt <= now:
            schedule = job.get("schedule", {})
            kind = schedule.get("kind")

            grace = _compute_grace_seconds(schedule)
            if kind in ("cron", "interval") and (now - next_run_dt).total_seconds() > grace:
                new_next = compute_next_run(schedule, now.isoformat())
                if new_next:
                    logger.info(
                        "Job '%s' missed its scheduled time (%s, grace=%ds). "
                        "Fast-forwarding to next run: %s",
                        job.get("name", job["id"]),
                        next_run,
                        grace,
                        new_next,
                    )
                    for rj in raw_jobs:
                        if rj["id"] == job["id"]:
                            rj["next_run_at"] = new_next
                            needs_save = True
                            break
                    continue

            due.append(job)

    if needs_save:
        save_jobs(raw_jobs)

    return due


def save_job_output(job_id: str, output: str):
    """Save job output to file."""
    ensure_dirs()
    job_output_dir = OUTPUT_DIR / job_id
    job_output_dir.mkdir(parents=True, exist_ok=True)
    _secure_dir(job_output_dir)

    timestamp = _prometheus_now().strftime("%Y-%m-%d_%H-%M-%S")
    output_file = job_output_dir / f"{timestamp}.md"

    fd, tmp_path = tempfile.mkstemp(dir=str(job_output_dir), suffix=".tmp", prefix=".output_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(output)
            f.flush()
            os.fsync(f.fileno())
        atomic_replace(tmp_path, output_file)
        _secure_file(output_file)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise

    return output_file
