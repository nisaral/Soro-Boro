"""Veyra Idempotency Key Semantics & Store Abstraction (Section 7 / Phase 12).

Strong Idempotency Invariant:
The same logical mutation MUST derive the same idempotency key across all retries,
recovery attempts, network drops, and process restarts.

Form:
idempotency_key = sha256(intent_id + tool + canonical_arguments + context_signature)
"""

from __future__ import annotations

import abc
import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


def canonicalize_json(obj: Any) -> str:
    """Return a stable, sorted JSON string for hashing arguments and context."""
    if isinstance(obj, dict):
        return "{" + ",".join(f"{json.dumps(k)}:{canonicalize_json(v)}" for k, v in sorted(obj.items())) + "}"
    elif isinstance(obj, list):
        return "[" + ",".join(canonicalize_json(x) for x in obj) + "]"
    elif isinstance(obj, set):
        return "[" + ",".join(canonicalize_json(x) for x in sorted(obj)) + "]"
    else:
        return json.dumps(obj)


@dataclass
class IdempotencyIdentity:
    """Logical idempotency identity bound to a unique mutation intent."""

    intent_id: str
    tool: str
    arguments: dict[str, Any]
    context_signature: str = ""
    created_at: float = 0.0
    key: str = field(init=False)

    def __post_init__(self):
        self.key = self.compute_key()

    def compute_key(self) -> str:
        payload = (
            f"intent:{self.intent_id}|tool:{self.tool}|args:{canonicalize_json(self.arguments)}|ctx:{self.context_signature}"
        )
        return f"idk_{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:24]}"


class IdempotencyStore(abc.ABC):
    """Abstract Idempotency Store Interface (Phase 12)."""

    @abc.abstractmethod
    def get(self, key: str) -> Optional[Any]:
        pass

    @abc.abstractmethod
    def put(self, key: str, value: Any) -> None:
        pass

    @abc.abstractmethod
    def exists(self, key: str) -> bool:
        pass


class InMemoryIdempotencyStore(IdempotencyStore):
    """Development in-memory idempotency store."""

    def __init__(self):
        self._store: Dict[str, Any] = {}

    def get(self, key: str) -> Optional[Any]:
        return self._store.get(key)

    def put(self, key: str, value: Any) -> None:
        self._store[key] = value

    def exists(self, key: str) -> bool:
        return key in self._store


class FileIdempotencyStore(IdempotencyStore):
    """Development file-backed idempotency store."""

    def __init__(self, filepath: str = "idempotency_store.json"):
        self.filepath = filepath
        self._load()

    def _load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    self._store = json.load(f)
            except Exception:
                self._store = {}
        else:
            self._store = {}

    def _save(self):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self._store, f, indent=2)

    def get(self, key: str) -> Optional[Any]:
        return self._store.get(key)

    def put(self, key: str, value: Any) -> None:
        self._store[key] = value
        self._save()

    def exists(self, key: str) -> bool:
        return key in self._store


class SQLiteIdempotencyStore(IdempotencyStore):
    """Development SQLite-backed idempotency store."""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self._init_db()

    def _init_db(self):
        with self.conn:
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS idempotency (key TEXT PRIMARY KEY, val TEXT)"
            )

    def get(self, key: str) -> Optional[Any]:
        cur = self.conn.cursor()
        cur.execute("SELECT val FROM idempotency WHERE key = ?", (key,))
        row = cur.fetchone()
        if row:
            try:
                return json.loads(row[0])
            except Exception:
                return row[0]
        return None

    def put(self, key: str, value: Any) -> None:
        str_val = json.dumps(value) if not isinstance(value, str) else value
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO idempotency (key, val) VALUES (?, ?)", (key, str_val)
            )

    def exists(self, key: str) -> bool:
        cur = self.conn.cursor()
        cur.execute("SELECT 1 FROM idempotency WHERE key = ?", (key,))
        return cur.fetchone() is not None


class IdempotencyKeyStore:
    """Persistent key store guaranteeing idempotency key stability across retries and restarts."""

    def __init__(self, backend: Optional[IdempotencyStore] = None):
        self.backend = backend or InMemoryIdempotencyStore()
        self._store: dict[str, IdempotencyIdentity] = {}
        self._execution_history: dict[str, dict[str, Any]] = {}

    def get_or_create(
        self,
        intent_id: str,
        tool: str,
        arguments: dict[str, Any],
        context_signature: str = "",
    ) -> IdempotencyIdentity:
        """Retrieve existing idempotency identity for the logical mutation, or create and persist it."""
        lookup_key = f"{intent_id}:{tool}"
        if lookup_key in self._store:
            return self._store[lookup_key]

        identity = IdempotencyIdentity(
            intent_id=intent_id,
            tool=tool,
            arguments=arguments,
            context_signature=context_signature,
        )
        self._store[lookup_key] = identity
        self.backend.put(identity.key, {"intent_id": intent_id, "tool": tool, "args": arguments})
        return identity

    def record_attempt(self, key: str, attempt_number: int, status: str, result: Any = None) -> None:
        if key not in self._execution_history:
            self._execution_history[key] = {"attempts": 0, "status": "PENDING", "result": None, "history": []}

        hist = self._execution_history[key]
        hist["attempts"] = attempt_number
        hist["status"] = status
        if result is not None:
            hist["result"] = result
        hist["history"].append({"attempt": attempt_number, "status": status, "result": result})

    def get_history(self, key: str) -> dict[str, Any] | None:
        return self._execution_history.get(key)

    def clear(self) -> None:
        self._store.clear()
        self._execution_history.clear()
