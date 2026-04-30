"""
Prometheus 定时任务工具
使用 APScheduler 管理定时任务
"""
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
from .registry import tool_result, tool_error

# 尝试导入 APScheduler
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False


class CronManager:
    """定时任务管理器"""
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.jobs_file = Path.home() / ".prometheus" / "cron_jobs.json"
        self.jobs: Dict[str, Dict[str, Any]] = {}
        
        if APSCHEDULER_AVAILABLE:
            self.scheduler.start()
    
    def add_job(
        self,
        job_id: str,
        command: str,
        trigger: str = "interval",
        minutes: Optional[int] = None,
        hours: Optional[int] = None,
        cron: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        添加定时任务
        
        Args:
            job_id: 任务 ID
            command: 要执行的命令
            trigger: 触发器类型（interval/cron）
            minutes: 间隔分钟数
            hours: 间隔小时数
            cron: cron 表达式
        
        Returns:
            包含 success 的字典
        """
        if not APSCHEDULER_AVAILABLE:
            return {"error": "APScheduler 未安装，请运行: pip install apscheduler"}
        
        try:
            # 构建触发器
            if trigger == "interval":
                trigger_obj = IntervalTrigger(
                    minutes=minutes or 0,
                    hours=hours or 0
                )
            elif trigger == "cron" and cron:
                # 解析 cron 表达式
                parts = cron.split()
                if len(parts) >= 5:
                    trigger_obj = CronTrigger(
                        minute=parts[0],
                        hour=parts[1],
                        day=parts[2],
                        month=parts[3],
                        day_of_week=parts[4]
                    )
                else:
                    return {"error": "无效的 cron 表达式"}
            else:
                return {"error": "未指定触发器"}
            
            # 添加任务
            import subprocess
            
            def job_func():
                subprocess.run(command, shell=True)
            
            self.scheduler.add_job(
                job_func,
                trigger_obj,
                id=job_id,
                replace_existing=True
            )
            
            # 保存任务配置
            self.jobs[job_id] = {
                "command": command,
                "trigger": trigger,
                "minutes": minutes,
                "hours": hours,
                "cron": cron,
                "created_at": datetime.now().isoformat()
            }
            self._save_jobs()
            
            return {
                "success": True,
                "job_id": job_id
            }
        
        except Exception as e:
            return {"error": f"添加任务失败: {str(e)}"}
    
    def remove_job(self, job_id: str) -> Dict[str, Any]:
        """
        移除定时任务
        
        Args:
            job_id: 任务 ID
        
        Returns:
            包含 success 的字典
        """
        if not APSCHEDULER_AVAILABLE:
            return {"error": "APScheduler 未安装"}
        
        try:
            self.scheduler.remove_job(job_id)
            self.jobs.pop(job_id, None)
            self._save_jobs()
            
            return {
                "success": True,
                "job_id": job_id
            }
        
        except Exception as e:
            return {"error": f"移除任务失败: {str(e)}"}
    
    def list_jobs(self) -> Dict[str, Any]:
        """
        列出所有任务
        
        Returns:
            包含 jobs 的字典
        """
        try:
            jobs = []
            
            for job in self.scheduler.get_jobs():
                jobs.append({
                    "id": job.id,
                    "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                    "trigger": str(job.trigger)
                })
            
            return {
                "jobs": jobs,
                "count": len(jobs)
            }
        
        except Exception as e:
            return {"error": f"列出任务失败: {str(e)}"}
    
    def _save_jobs(self):
        """保存任务配置"""
        try:
            self.jobs_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.jobs_file, 'w', encoding='utf-8') as f:
                json.dump(self.jobs, f, indent=2)
        except Exception:
            pass
    
    def shutdown(self):
        """关闭调度器"""
        if APSCHEDULER_AVAILABLE:
            self.scheduler.shutdown()


# 全局调度器
_cron_manager = None


def get_cron_manager() -> Optional[CronManager]:
    """获取 Cron 管理器"""
    global _cron_manager
    if _cron_manager is None and APSCHEDULER_AVAILABLE:
        _cron_manager = CronManager()
    return _cron_manager


# Cron 工具 schemas
ADD_JOB_SCHEMA = {
    "name": "add_cron_job",
    "description": "添加定时任务",
    "parameters": {
        "type": "object",
        "properties": {
            "job_id": {"type": "string", "description": "任务 ID"},
            "command": {"type": "string", "description": "要执行的命令"},
            "trigger": {"type": "string", "description": "触发器类型", "enum": ["interval", "cron"]},
            "minutes": {"type": "integer", "description": "间隔分钟数"},
            "hours": {"type": "integer", "description": "间隔小时数"},
            "cron": {"type": "string", "description": "cron 表达式（分 时 日 月 周）"}
        },
        "required": ["job_id", "command"]
    }
}

REMOVE_JOB_SCHEMA = {
    "name": "remove_cron_job",
    "description": "移除定时任务",
    "parameters": {
        "type": "object",
        "properties": {
            "job_id": {"type": "string", "description": "任务 ID"}
        },
        "required": ["job_id"]
    }
}

LIST_JOBS_SCHEMA = {
    "name": "list_cron_jobs",
    "description": "列出所有定时任务",
    "parameters": {
        "type": "object",
        "properties": {}
    }
}


def check_cron_requirements() -> bool:
    """检查 Cron 需求"""
    return APSCHEDULER_AVAILABLE


def handle_add_job(args: Dict[str, Any], **kwargs) -> str:
    job_id = args.get("job_id", "")
    command = args.get("command", "")
    trigger = args.get("trigger", "interval")
    minutes = args.get("minutes")
    hours = args.get("hours")
    cron = args.get("cron")
    
    manager = get_cron_manager()
    
    if not manager:
        return tool_error("APScheduler 未安装")
    
    result = manager.add_job(job_id, command, trigger, minutes, hours, cron)
    
    if "error" in result:
        return tool_error(result["error"])
    
    return tool_result(result)


def handle_remove_job(args: Dict[str, Any], **kwargs) -> str:
    job_id = args.get("job_id", "")
    
    manager = get_cron_manager()
    
    if not manager:
        return tool_error("APScheduler 未安装")
    
    result = manager.remove_job(job_id)
    
    if "error" in result:
        return tool_error(result["error"])
    
    return tool_result(result)


def handle_list_jobs(args: Dict[str, Any], **kwargs) -> str:
    manager = get_cron_manager()
    
    if not manager:
        return tool_error("APScheduler 未安装")
    
    result = manager.list_jobs()
    
    if "error" in result:
        return tool_error(result["error"])
    
    return tool_result(result)


# 注册工具
from .registry import registry

registry.register(
    name="add_cron_job",
    toolset="cron",
    schema=ADD_JOB_SCHEMA,
    handler=handle_add_job,
    description="添加定时任务",
    emoji="⏰",
    check_fn=check_cron_requirements
)

registry.register(
    name="remove_cron_job",
    toolset="cron",
    schema=REMOVE_JOB_SCHEMA,
    handler=handle_remove_job,
    description="移除定时任务",
    emoji="❌",
    check_fn=check_cron_requirements
)

registry.register(
    name="list_cron_jobs",
    toolset="cron",
    schema=LIST_JOBS_SCHEMA,
    handler=handle_list_jobs,
    description="列出定时任务",
    emoji="📋",
    check_fn=check_cron_requirements
)
