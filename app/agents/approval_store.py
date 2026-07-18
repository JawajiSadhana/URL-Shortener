import uuid
import json
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy import Column, DateTime, String, Text, inspect, text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Base
import app.db as app_db

try:
    import redis
except ImportError:
    redis = None

# Allowed state transitions for the approval lifecycle
_TRANSITIONS = {
    "pending": ["approved", "rejected"],
    "approved": ["executing", "rejected"],
    "executing": ["reviewing", "failed"],
    "reviewing": ["completed", "blocked", "failed"],
    "blocked": [],
    "completed": [],
    "rejected": [],
    "failed": [],
}


class Approval(Base):
    __tablename__ = "approvals"

    id = Column(String, primary_key=True, index=True)
    state = Column(String, nullable=False, default="pending")
    base_path = Column(String, nullable=True)
    assumptions = Column(Text, nullable=True)
    decisions = Column(Text, nullable=True)
    files_touched = Column(Text, nullable=True)
    retry_history = Column(Text, nullable=True)
    planner_tasks = Column(Text)
    executor_tasks = Column(Text)
    history = Column(Text)
    traces = Column(Text, nullable=True)
    approver_id = Column(String, nullable=True)
    approver_comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def _now_history_entry(state: str) -> Dict[str, Any]:
    return {"state": state, "ts": datetime.now(timezone.utc).isoformat()}


def _create_trace_entry(name: str, trace_type: str, parent_id: str | None = None, metadata: Dict[str, Any] | None = None, result: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "type": trace_type,
        "name": name,
        "parent_id": parent_id,
        "ts": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata or {},
        "result": result or {},
    }


class SQLiteApprovalStore:
    def __init__(self):
        self.engine = app_db.engine
        self._ensure_schema()

    def _ensure_schema(self):
        with self.engine.begin() as conn:
            inspector = inspect(conn)
            if not inspector.has_table("approvals"):
                Base.metadata.create_all(bind=self.engine)
                return

            cols = {c["name"] for c in inspector.get_columns("approvals")}
            needed = {
                "assumptions": "TEXT",
                "decisions": "TEXT",
                "files_touched": "TEXT",
                "retry_history": "TEXT",
                "traces": "TEXT",
                "approver_id": "VARCHAR(255)",
                "approver_comment": "TEXT",
            }
            for name, typ in needed.items():
                if name not in cols:
                    try:
                        conn.execute(text(f"ALTER TABLE approvals ADD COLUMN {name} {typ}"))
                    except Exception:
                        pass

    def _session(self) -> Session:
        return app_db.SessionLocal()

    def create_approval(self, executor_tasks, planner_tasks, base_path=None, assumptions=None, decisions=None, files_touched=None, retry_history=None, traces=None) -> str:
        approval_id = str(uuid.uuid4())
        planner_json = json.dumps(planner_tasks)
        executor_json = json.dumps(executor_tasks)
        history = json.dumps([_now_history_entry("pending")])
        assumptions_json = json.dumps(assumptions or [])
        decisions_json = json.dumps(decisions or [])
        files_json = json.dumps(files_touched or [])
        retry_json = json.dumps(retry_history or [])
        traces_json = json.dumps(traces or [])
        db: Session = self._session()
        try:
            rec = Approval(
                id=approval_id,
                state="pending",
                base_path=base_path,
                planner_tasks=planner_json,
                executor_tasks=executor_json,
                history=history,
                traces=traces_json,
                assumptions=assumptions_json,
                decisions=decisions_json,
                files_touched=files_json,
                retry_history=retry_json,
            )
            db.add(rec)
            db.commit()
            return approval_id
        finally:
            db.close()

    def get_approval(self, approval_id: str) -> Dict[str, Any] | None:
        db: Session = self._session()
        try:
            rec = db.get(Approval, approval_id)
            if not rec:
                return None
            return {
                "id": rec.id,
                "state": rec.state,
                "base_path": rec.base_path,
                "planner_tasks": json.loads(rec.planner_tasks) if rec.planner_tasks else [],
                "executor_tasks": json.loads(rec.executor_tasks) if rec.executor_tasks else [],
                "assumptions": json.loads(rec.assumptions) if rec.assumptions else [],
                "decisions": json.loads(rec.decisions) if rec.decisions else [],
                "files_touched": json.loads(rec.files_touched) if rec.files_touched else [],
                "retry_history": json.loads(rec.retry_history) if rec.retry_history else [],
                "history": json.loads(rec.history) if rec.history else [],
                "traces": json.loads(rec.traces) if rec.traces else [],
                "approver_id": rec.approver_id,
                "approver_comment": rec.approver_comment,
                "created_at": rec.created_at.isoformat() if rec.created_at else None,
                "updated_at": rec.updated_at.isoformat() if rec.updated_at else None,
            }
        finally:
            db.close()

    def _save_history_and_state(self, db: Session, rec: Approval, new_state: str) -> None:
        h = json.loads(rec.history) if rec.history else []
        h.append(_now_history_entry(new_state))
        rec.history = json.dumps(h)
        rec.state = new_state
        rec.updated_at = datetime.now(timezone.utc)
        db.add(rec)
        db.commit()

    def transition_approval(self, approval_id: str, new_state: str) -> bool:
        db: Session = self._session()
        try:
            rec = db.get(Approval, approval_id)
            if not rec:
                return False
            cur = rec.state
            allowed = _TRANSITIONS.get(cur, [])
            if new_state not in allowed:
                return False
            self._save_history_and_state(db, rec, new_state)
            return True
        finally:
            db.close()

    def set_approval_state_force(self, approval_id: str, new_state: str) -> bool:
        db: Session = self._session()
        try:
            rec = db.get(Approval, approval_id)
            if not rec:
                return False
            self._save_history_and_state(db, rec, new_state)
            return True
        finally:
            db.close()

    def set_approver_metadata(self, approval_id: str, approver_id: str | None, approver_comment: str | None) -> bool:
        db: Session = self._session()
        try:
            rec = db.get(Approval, approval_id)
            if not rec:
                return False
            rec.approver_id = approver_id
            rec.approver_comment = approver_comment
            rec.updated_at = datetime.now(timezone.utc)
            db.add(rec)
            db.commit()
            return True
        finally:
            db.close()

    def update_execution_metadata(self, approval_id: str, files_touched: List[str], retry_history: List[Dict[str, Any]]) -> bool:
        db: Session = self._session()
        try:
            rec = db.get(Approval, approval_id)
            if not rec:
                return False
            existing_files = json.loads(rec.files_touched) if rec.files_touched else []
            existing_retries = json.loads(rec.retry_history) if rec.retry_history else []
            rec.files_touched = json.dumps(existing_files + (files_touched or []))
            rec.retry_history = json.dumps(existing_retries + (retry_history or []))
            rec.updated_at = datetime.now(timezone.utc)
            db.add(rec)
            db.commit()
            return True
        finally:
            db.close()

    def append_trace(self, approval_id: str, trace: Dict[str, Any]) -> bool:
        db: Session = self._session()
        try:
            rec = db.get(Approval, approval_id)
            if not rec:
                return False
            existing_traces = json.loads(rec.traces) if rec.traces else []
            existing_traces.append(trace)
            rec.traces = json.dumps(existing_traces)
            rec.updated_at = datetime.now(timezone.utc)
            db.add(rec)
            db.commit()
            return True
        finally:
            db.close()

    def append_decision(self, approval_id: str, decision: Any) -> bool:
        db: Session = self._session()
        try:
            rec = db.get(Approval, approval_id)
            if not rec:
                return False
            existing_decisions = json.loads(rec.decisions) if rec.decisions else []
            existing_decisions.append(decision)
            rec.decisions = json.dumps(existing_decisions)
            rec.updated_at = datetime.now(timezone.utc)
            db.add(rec)
            db.commit()
            return True
        finally:
            db.close()

    def delete_approval(self, approval_id: str):
        db: Session = self._session()
        try:
            rec = db.get(Approval, approval_id)
            if not rec:
                return None
            db.delete(rec)
            db.commit()
            return True
        finally:
            db.close()

    def list_approvals(self) -> List[str]:
        db: Session = self._session()
        try:
            rows = db.query(Approval.id).all()
            return [r[0] for r in rows]
        finally:
            db.close()


class RedisApprovalStore:
    def __init__(self, redis_url: str, ttl: int):
        if redis is None:
            raise ImportError("redis package is required for Redis approval store")
        self.client = redis.from_url(redis_url, decode_responses=True)
        self.ttl = ttl
        self.index_key = "approvals:index"

    def _key(self, approval_id: str) -> str:
        return f"approval:{approval_id}"

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _restore_record(self, data: Dict[str, str]) -> Dict[str, Any]:
        if not data:
            return None
        return {
            "id": data.get("id"),
            "state": data.get("state"),
            "base_path": data.get("base_path"),
            "planner_tasks": json.loads(data.get("planner_tasks") or "[]"),
            "executor_tasks": json.loads(data.get("executor_tasks") or "[]"),
            "assumptions": json.loads(data.get("assumptions") or "[]"),
            "decisions": json.loads(data.get("decisions") or "[]"),
            "files_touched": json.loads(data.get("files_touched") or "[]"),
            "retry_history": json.loads(data.get("retry_history") or "[]"),
            "traces": json.loads(data.get("traces") or "[]"),
            "history": json.loads(data.get("history") or "[]"),
            "approver_id": data.get("approver_id"),
            "approver_comment": data.get("approver_comment"),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
        }

    def create_approval(self, executor_tasks, planner_tasks, base_path=None, assumptions=None, decisions=None, files_touched=None, retry_history=None, traces=None) -> str:
        approval_id = str(uuid.uuid4())
        now = self._now()
        key = self._key(approval_id)
        record = {
            "id": approval_id,
            "state": "pending",
            "base_path": base_path or "",
            "planner_tasks": json.dumps(planner_tasks),
            "executor_tasks": json.dumps(executor_tasks),
            "history": json.dumps([_now_history_entry("pending")]),
            "traces": json.dumps(traces or []),
            "assumptions": json.dumps(assumptions or []),
            "decisions": json.dumps(decisions or []),
            "files_touched": json.dumps(files_touched or []),
            "retry_history": json.dumps(retry_history or []),
            "approver_id": "",
            "approver_comment": "",
            "created_at": now,
            "updated_at": now,
        }
        pipeline = self.client.pipeline()
        pipeline.hset(key, mapping=record)
        pipeline.sadd(self.index_key, approval_id)
        pipeline.expire(key, self.ttl)
        pipeline.execute()
        return approval_id

    def get_approval(self, approval_id: str) -> Dict[str, Any] | None:
        key = self._key(approval_id)
        data = self.client.hgetall(key)
        if not data:
            return None
        return self._restore_record(data)

    def append_trace(self, approval_id: str, trace: Dict[str, Any]) -> bool:
        record = self.get_approval(approval_id)
        if not record:
            return False
        updates = {
            "traces": json.dumps((record.get("traces") or []) + [trace]),
            "updated_at": self._now(),
        }
        self._set_fields(self._key(approval_id), updates)
        return True

    def append_decision(self, approval_id: str, decision: Any) -> bool:
        record = self.get_approval(approval_id)
        if not record:
            return False
        updates = {
            "decisions": json.dumps((record.get("decisions") or []) + [decision]),
            "updated_at": self._now(),
        }
        self._set_fields(self._key(approval_id), updates)
        return True

    def _set_fields(self, key: str, updates: Dict[str, Any]) -> None:
        self.client.hset(key, mapping={k: v for k, v in updates.items() if v is not None})
        self.client.expire(key, self.ttl)

    def _save_history_and_state(self, approval_id: str, new_state: str) -> bool:
        record = self.get_approval(approval_id)
        if not record:
            return False
        record["history"].append(_now_history_entry(new_state))
        record["state"] = new_state
        record["updated_at"] = self._now()
        self._set_fields(self._key(approval_id), {
            "state": record["state"],
            "history": json.dumps(record["history"]),
            "updated_at": record["updated_at"],
        })
        return True

    def transition_approval(self, approval_id: str, new_state: str) -> bool:
        record = self.get_approval(approval_id)
        if not record:
            return False
        allowed = _TRANSITIONS.get(record["state"], [])
        if new_state not in allowed:
            return False
        return self._save_history_and_state(approval_id, new_state)

    def set_approval_state_force(self, approval_id: str, new_state: str) -> bool:
        record = self.get_approval(approval_id)
        if not record:
            return False
        return self._save_history_and_state(approval_id, new_state)

    def set_approver_metadata(self, approval_id: str, approver_id: str | None, approver_comment: str | None) -> bool:
        record = self.get_approval(approval_id)
        if not record:
            return False
        updates = {
            "approver_id": approver_id or "",
            "approver_comment": approver_comment or "",
            "updated_at": self._now(),
        }
        self._set_fields(self._key(approval_id), updates)
        return True

    def update_execution_metadata(self, approval_id: str, files_touched: List[str], retry_history: List[Dict[str, Any]]) -> bool:
        record = self.get_approval(approval_id)
        if not record:
            return False
        updates = {
            "files_touched": json.dumps((record.get("files_touched") or []) + (files_touched or [])),
            "retry_history": json.dumps((record.get("retry_history") or []) + (retry_history or [])),
            "updated_at": self._now(),
        }
        self._set_fields(self._key(approval_id), updates)
        return True

    def delete_approval(self, approval_id: str):
        key = self._key(approval_id)
        self.client.delete(key)
        self.client.srem(self.index_key, approval_id)
        return True

    def list_approvals(self) -> List[str]:
        return list(self.client.smembers(self.index_key))


def _build_store():
    backend = settings.approval_store_backend.lower().strip()
    if backend == "redis":
        return RedisApprovalStore(settings.redis_url, settings.approval_ttl_seconds)
    return SQLiteApprovalStore()


_store = None


def _get_store():
    global _store
    if _store is None:
        _store = _build_store()
    return _store


def reset_store():
    global _store
    _store = None


def create_approval(executor_tasks, planner_tasks, base_path=None, assumptions=None, decisions=None, files_touched=None, retry_history=None, traces=None) -> str:
    return _get_store().create_approval(
        executor_tasks=executor_tasks,
        planner_tasks=planner_tasks,
        base_path=base_path,
        assumptions=assumptions,
        decisions=decisions,
        files_touched=files_touched,
        retry_history=retry_history,
        traces=traces,
    )


def get_approval(approval_id: str) -> Dict[str, Any] | None:
    return _get_store().get_approval(approval_id)


def transition_approval(approval_id: str, new_state: str) -> bool:
    return _get_store().transition_approval(approval_id, new_state)


def set_approval_state_force(approval_id: str, new_state: str) -> bool:
    return _get_store().set_approval_state_force(approval_id, new_state)


def set_approver_metadata(approval_id: str, approver_id: str | None, approver_comment: str | None) -> bool:
    return _get_store().set_approver_metadata(approval_id, approver_id, approver_comment)


def update_execution_metadata(approval_id: str, files_touched: List[str], retry_history: List[Dict[str, Any]]) -> bool:
    return _get_store().update_execution_metadata(approval_id, files_touched, retry_history)


def append_trace(approval_id: str, trace: Dict[str, Any]) -> bool:
    return _get_store().append_trace(approval_id, trace)


def append_decision(approval_id: str, decision: Any) -> bool:
    return _get_store().append_decision(approval_id, decision)


def delete_approval(approval_id: str):
    return _get_store().delete_approval(approval_id)


def list_approvals() -> List[str]:
    return _get_store().list_approvals()
