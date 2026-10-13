"""Soro Framework Typed Models & Schemas (v0.3.0).

Stable, versioned request/response schemas carrying full decision traces.
Supported across Python, Node, Java, and MCP gateway clients.
"""

from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ToolDecisionType(str, Enum):
    EXECUTE = "EXECUTE"
    ASK_CONFIRMATION = "ASK"
    ABSTAIN = "ABSTAIN"
    DENY = "DENY"


class DecisionTrace(BaseModel):
    trace_id: str = Field(default_factory=lambda: f"tr_{uuid.uuid4().hex[:12]}")
    timestamp: float = Field(default_factory=time.time)
    decision: ToolDecisionType
    reason: str
    conformal_quantile: Optional[float] = None
    prediction_set_size: int = 1
    action_id: Optional[str] = None
    latency_ms: float = 0.0
    shadow_mode: bool = False


class ToolCandidate(BaseModel):
    name: str
    description: str = ""
    parameters: Dict[str, Any] = Field(default_factory=dict)
    score: float = 1.0
    inferred_class: str = "read_only"  # read_only, idempotent_write, non_idempotent_mutation
    verified_idempotent: bool = False


class RouteRequest(BaseModel):
    query: str
    candidate_tools: List[ToolCandidate]
    alpha: float = 0.05
    tenant_id: str = "default"
    shadow_mode: bool = False


class RouteResponse(BaseModel):
    decision: ToolDecisionType
    shortlist: List[ToolCandidate]
    singleton_tool: Optional[ToolCandidate] = None
    trace: DecisionTrace


class ExecuteRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    action_id: str = Field(default_factory=lambda: f"act_{uuid.uuid4().hex[:12]}")
    idempotency_key: Optional[str] = None
    shadow_mode: bool = False
    simulate_fault: Optional[str] = None  # None, pre_commit, post_commit, probe_crash


class ExecuteResponse(BaseModel):
    status: str  # "COMMITTED", "REPLAYED", "DEFERRED", "DROPPED"
    result: Optional[Any] = None
    error: Optional[str] = None
    was_replayed: bool = False
    was_deferred: bool = False
    trace: DecisionTrace


class CalibrateRequest(BaseModel):
    queries: List[str]
    gold_tool_names: List[str]
    alpha_write: float = 0.05
    alpha_read: float = 0.10


class CalibrateResponse(BaseModel):
    q_write: float
    q_read: float
    n_queries: int
    temperature: float


class FeedbackRequest(BaseModel):
    trace_id: str
    user_confirmed: bool
    actual_outcome: str  # "success", "duplicate", "cancelled"
