
"""
Prometheus 进化提案引擎
改进版：更完善的提案机制

改进点：
1. 冷却期从上次成功应用开始计算
2. 冷却期内提案仍然累积
3. 提案去重
4. 提案过期机制
5. 审核历史记录
6. 回滚机制
7. 提案优先级
8. 用户通知
9. 智能压缩
10. 来源追踪
"""
import os
import fcntl
import contextlib
import logging
import hashlib
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


def get_prometheus_home():
    home = os.environ.get("PROMETHEUS_HOME")
    if home:
        return Path(home)
    return Path.home() / ".prometheus"


def get_evolution_log_path():
    return get_prometheus_home() / "evolution-log.json"


def get_evolution_backup_path():
    return get_prometheus_home() / "evolution-backups"


@contextlib.contextmanager
def _file_lock(path: Path):
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    
    if fcntl is None:
        yield
        return
    
    fd = open(lock_path, "w")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()


class ProposalStatus(Enum):
    PENDING = "pending"
    ACCUMULATING = "accumulating"
    READY_FOR_REVIEW = "ready_for_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    EXPIRED = "expired"
    ROLLED_BACK = "rolled_back"


class ProposalPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Proposal:
    id: str
    section: str
    content: str
    target_file: str
    source: str
    priority: ProposalPriority
    status: ProposalStatus
    created_at: datetime
    expires_at: datetime
    content_hash: str
    reason: str = ""
    reviewed_at: Optional[datetime] = None
    applied_at: Optional[datetime] = None
    rolled_back_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "section": self.section,
            "content": self.content,
            "target_file": self.target_file,
            "source": self.source,
            "priority": self.priority.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "content_hash": self.content_hash,
            "reason": self.reason,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "rolled_back_at": self.rolled_back_at.isoformat() if self.rolled_back_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Proposal":
        return cls(
            id=data["id"],
            section=data["section"],
            content=data["content"],
            target_file=data["target_file"],
            source=data.get("source", "unknown"),
            priority=ProposalPriority(data.get("priority", 2)),
            status=ProposalStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            content_hash=data["content_hash"],
            reason=data.get("reason", ""),
            reviewed_at=datetime.fromisoformat(data["reviewed_at"]) if data.get("reviewed_at") else None,
            applied_at=datetime.fromisoformat(data["applied_at"]) if data.get("applied_at") else None,
            rolled_back_at=datetime.fromisoformat(data["rolled_back_at"]) if data.get("rolled_back_at") else None,
        )


class EvolutionEngine:
    """进化提案引擎"""
    
    CONFIG = {
        "cooldown_hours": 24,
        "max_entries": 50,
        "compression_threshold": 5000,
        "sensitive_keywords": [
            "密码", "password", "secret", "key", "token",
            "私钥", "private", "credential", "api_key"
        ],
        "proposal_threshold": 3,
        "proposal_expire_days": 7,
        "max_pending_proposals": 20,
        "auto_expire_hours": 168,
    }
    
    def __init__(self):
        self._ensure_directories()
        self._load_state()
    
    def _ensure_directories(self):
        get_prometheus_home().mkdir(parents=True, exist_ok=True)
        get_evolution_backup_path().mkdir(parents=True, exist_ok=True)
    
    def _load_state(self):
        log_path = get_evolution_log_path()
        if log_path.exists():
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    self._state = json.load(f)
            except Exception:
                self._state = self._default_state()
        else:
            self._state = self._default_state()
    
    def _default_state(self) -> Dict[str, Any]:
        return {
            "proposals": [],
            "history": [],
            "last_applied": None,
            "notifications": [],
            "stats": {
                "total_proposals": 0,
                "approved": 0,
                "rejected": 0,
                "expired": 0,
                "rolled_back": 0,
            }
        }
    
    def _save_state(self):
        log_path = get_evolution_log_path()
        with _file_lock(log_path):
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(self._state, f, ensure_ascii=False, indent=2)
    
    def _hash_content(self, content: str) -> str:
        return hashlib.md5(content.encode()).hexdigest()[:8]
    
    def _contains_sensitive_info(self, text: str) -> bool:
        text_lower = text.lower()
        for keyword in self.CONFIG["sensitive_keywords"]:
            if keyword.lower() in text_lower:
                return True
        return False
    
    def _check_cooldown(self) -> bool:
        if not self._state.get("last_applied"):
            return True
        
        last_applied = datetime.fromisoformat(self._state["last_applied"])
        cooldown = timedelta(hours=self.CONFIG["cooldown_hours"])
        
        return datetime.now() > last_applied + cooldown
    
    def _is_duplicate(self, content_hash: str, target_file: str) -> bool:
        for p in self._state.get("proposals", []):
            if (p.get("content_hash") == content_hash and 
                p.get("target_file") == target_file and
                p.get("status") in ["pending", "accumulating", "ready_for_review"]):
                return True
        return False
    
    def _is_expired(self, proposal: Proposal) -> bool:
        return datetime.now() > proposal.expires_at
    
    def _generate_id(self) -> str:
        return datetime.now().strftime("%Y%m%d_%H%M%S_") + self._hash_content(str(datetime.now().timestamp()))
    
    def propose(self, section: str, content: str, target_file: str = "MEMORY.md",
                source: str = "ai", priority: ProposalPriority = ProposalPriority.NORMAL) -> Dict[str, Any]:
        """
        提出进化提案
        
        改进：
        1. 冷却期内提案仍然累积
        2. 自动去重
        3. 自动设置过期时间
        4. 追踪来源
        """
        content_hash = self._hash_content(section + content)
        
        proposal = Proposal(
            id=self._generate_id(),
            section=section,
            content=content[:500],
            target_file=target_file,
            source=source,
            priority=priority,
            status=ProposalStatus.PENDING,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(days=self.CONFIG["proposal_expire_days"]),
            content_hash=content_hash,
        )
        
        if self._contains_sensitive_info(content):
            proposal.status = ProposalStatus.REJECTED
            proposal.reason = "包含敏感信息"
            return proposal.to_dict()
        
        if self._is_duplicate(content_hash, target_file):
            proposal.status = ProposalStatus.REJECTED
            proposal.reason = "重复提案"
            return proposal.to_dict()
        
        pending_count = len([p for p in self._state.get("proposals", []) 
                           if p.get("status") in ["pending", "accumulating", "ready_for_review"]])
        
        if pending_count >= self.CONFIG["max_pending_proposals"]:
            proposal.status = ProposalStatus.REJECTED
            proposal.reason = f"待处理提案已达上限 ({self.CONFIG['max_pending_proposals']})"
            return proposal.to_dict()
        
        self._state["proposals"].append(proposal.to_dict())
        if "stats" not in self._state:
            self._state["stats"] = {}
        self._state["stats"]["total_proposals"] = self._state["stats"].get("total_proposals", 0) + 1
        
        pending_proposals = [p for p in self._state["proposals"] 
                           if p.get("status") in ["pending", "accumulating", "ready_for_review"]]
        
        if len(pending_proposals) >= self.CONFIG["proposal_threshold"]:
            proposal.status = ProposalStatus.READY_FOR_REVIEW
            proposal.reason = f"已累积 {len(pending_proposals)} 个提案，等待审核"
            
            self._add_notification(
                level="info",
                message=f"进化提案已准备好审核：{len(pending_proposals)} 个提案等待处理",
                proposal_ids=[p.get("id", "unknown") for p in pending_proposals]
            )
        else:
            proposal.status = ProposalStatus.ACCUMULATING
            proposal.reason = f"已累积 {len(pending_proposals)}/{self.CONFIG['proposal_threshold']}"
        
        self._save_state()
        return proposal.to_dict()
    
    def get_pending_proposals(self) -> List[Dict[str, Any]]:
        """获取待审核的提案"""
        self._expire_old_proposals()
        
        pending = [p for p in self._state.get("proposals", []) 
                  if p.get("status") in ["pending", "accumulating", "ready_for_review"]]
        
        pending.sort(key=lambda x: ProposalPriority(x.get("priority", 2)).value, reverse=True)
        
        return pending
    
    def review_proposal(self, proposal_id: str, approved: bool, reason: str = "") -> Dict[str, Any]:
        """审核提案"""
        proposal = None
        for p in self._state.get("proposals", []):
            if p.get("id") == proposal_id:
                proposal = Proposal.from_dict(p)
                break
        
        if not proposal:
            return {"success": False, "error": "提案不存在"}
        
        if self._is_expired(proposal):
            proposal.status = ProposalStatus.EXPIRED
            proposal.reason = "提案已过期"
            self._save_state()
            return proposal.to_dict()
        
        proposal.reviewed_at = datetime.now()
        
        if approved:
            proposal.status = ProposalStatus.APPROVED
            proposal.reason = reason or "用户批准"
            
            result = self._apply_proposal(proposal)
            if result["success"]:
                proposal.status = ProposalStatus.APPLIED
                proposal.applied_at = datetime.now()
                self._state["last_applied"] = datetime.now().isoformat()
                self._state["stats"]["approved"] = self._state["stats"].get("approved", 0) + 1
                
                self._state["history"].append({
                    "proposal": proposal.to_dict(),
                    "applied_at": datetime.now().isoformat(),
                    "backup_path": result.get("backup_path"),
                })
            else:
                proposal.status = ProposalStatus.REJECTED
                proposal.reason = f"应用失败: {result.get('error', '未知错误')}"
        else:
            proposal.status = ProposalStatus.REJECTED
            proposal.reason = reason or "用户拒绝"
            self._state["stats"]["rejected"] = self._state["stats"].get("rejected", 0) + 1
        
        for i, p in enumerate(self._state["proposals"]):
            if p.get("id") == proposal_id:
                self._state["proposals"][i] = proposal.to_dict()
                break
        
        self._save_state()
        return proposal.to_dict()
    
    def _apply_proposal(self, proposal: Proposal) -> Dict[str, Any]:
        """应用提案"""
        try:
            from prometheus.memory_system import (
                get_user_profile_path, get_memory_path, get_soul_path
            )
            
            if proposal.target_file == "USER.md":
                path = get_user_profile_path()
            elif proposal.target_file == "SOUL.md":
                path = get_soul_path()
            else:
                path = get_memory_path()
            
            if not path.exists():
                return {"success": False, "error": "目标文件不存在"}
            
            backup_path = get_evolution_backup_path() / f"{proposal.id}.md"
            backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            
            current = path.read_text(encoding="utf-8")
            new_content = current + f"\n\n§\n{proposal.content}"
            
            if len(new_content) > self.CONFIG["compression_threshold"]:
                new_content = self._smart_compress(new_content)
            
            with _file_lock(path):
                path.write_text(new_content, encoding="utf-8")
            
            return {"success": True, "backup_path": str(backup_path)}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def rollback(self, proposal_id: str) -> Dict[str, Any]:
        """回滚提案"""
        for entry in self._state.get("history", []):
            if entry.get("proposal", {}).get("id") == proposal_id:
                backup_path = Path(entry.get("backup_path", ""))
                
                if not backup_path.exists():
                    return {"success": False, "error": "备份文件不存在"}
                
                proposal = Proposal.from_dict(entry["proposal"])
                
                from prometheus.memory_system import (
                    get_user_profile_path, get_memory_path, get_soul_path
                )
                
                if proposal.target_file == "USER.md":
                    path = get_user_profile_path()
                elif proposal.target_file == "SOUL.md":
                    path = get_soul_path()
                else:
                    path = get_memory_path()
                
                with _file_lock(path):
                    path.write_text(backup_path.read_text(encoding="utf-8"), encoding="utf-8")
                
                proposal.status = ProposalStatus.ROLLED_BACK
                proposal.rolled_back_at = datetime.now()
                
                for i, p in enumerate(self._state["proposals"]):
                    if p.get("id") == proposal_id:
                        self._state["proposals"][i] = proposal.to_dict()
                        break
                
                self._state["stats"]["rolled_back"] = self._state["stats"].get("rolled_back", 0) + 1
                self._save_state()
                
                return {"success": True, "proposal": proposal.to_dict()}
        
        return {"success": False, "error": "提案不存在或无法回滚"}
    
    def _smart_compress(self, content: str) -> str:
        """智能压缩"""
        sections = content.split("§")
        
        if len(sections) > 10:
            sections = sections[-10:]
        
        compressed = []
        for section in sections:
            lines = section.strip().split("\n")
            if lines:
                compressed.append(lines[0] if len(lines[0]) < 100 else lines[0][:100] + "...")
        
        return "§\n".join(compressed)
    
    def _expire_old_proposals(self):
        """过期旧提案"""
        expired_count = 0
        for p in self._state.get("proposals", []):
            proposal = Proposal.from_dict(p)
            if proposal.status in [ProposalStatus.PENDING, ProposalStatus.ACCUMULATING]:
                if self._is_expired(proposal):
                    proposal.status = ProposalStatus.EXPIRED
                    proposal.reason = "提案已过期"
                    expired_count += 1
        
        if expired_count > 0:
            self._state["stats"]["expired"] = self._state["stats"].get("expired", 0) + expired_count
            self._save_state()
    
    def _add_notification(self, level: str, message: str, proposal_ids: List[str] = None):
        """添加通知"""
        if "notifications" not in self._state:
            self._state["notifications"] = []
        
        notification = {
            "id": self._hash_content(message + str(datetime.now().timestamp())),
            "level": level,
            "message": message,
            "proposal_ids": proposal_ids or [],
            "created_at": datetime.now().isoformat(),
            "read": False,
        }
        
        self._state["notifications"].append(notification)
        
        if len(self._state["notifications"]) > 20:
            self._state["notifications"] = self._state["notifications"][-20:]
    
    def get_notifications(self, unread_only: bool = True) -> List[Dict[str, Any]]:
        """获取通知"""
        notifications = self._state.get("notifications", [])
        
        if unread_only:
            notifications = [n for n in notifications if not n.get("read")]
        
        return notifications
    
    def mark_notification_read(self, notification_id: str):
        """标记通知已读"""
        for n in self._state.get("notifications", []):
            if n.get("id") == notification_id:
                n["read"] = True
                break
        self._save_state()
    
    def get_status(self) -> Dict[str, Any]:
        """获取进化状态"""
        self._expire_old_proposals()
        
        pending = self.get_pending_proposals()
        
        return {
            "pending_count": len(pending),
            "threshold": self.CONFIG["proposal_threshold"],
            "cooldown_active": not self._check_cooldown(),
            "last_applied": self._state.get("last_applied"),
            "stats": self._state.get("stats", {}),
            "notifications": len(self.get_notifications(unread_only=True)),
        }
    
    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取审核历史"""
        history = self._state.get("history", [])
        return history[-limit:]

