from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ActionType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ACTION_TYPE_UNSPECIFIED: _ClassVar[ActionType]
    MODEL_CALL: _ClassVar[ActionType]
    TOOL_CALL: _ClassVar[ActionType]
    VERIFY: _ClassVar[ActionType]
    RETRY: _ClassVar[ActionType]
    SWITCH_HARNESS: _ClassVar[ActionType]
    TERMINATE: _ClassVar[ActionType]

class ControlOp(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CONTROL_OP_UNSPECIFIED: _ClassVar[ControlOp]
    PAUSE: _ClassVar[ControlOp]
    RESUME: _ClassVar[ControlOp]
    INTERRUPT: _ClassVar[ControlOp]
    TERMINATE_RUN: _ClassVar[ControlOp]

class RunStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    RUN_STATUS_UNSPECIFIED: _ClassVar[RunStatus]
    PENDING: _ClassVar[RunStatus]
    RUNNING: _ClassVar[RunStatus]
    PAUSED: _ClassVar[RunStatus]
    SUCCEEDED: _ClassVar[RunStatus]
    FAILED: _ClassVar[RunStatus]
    CANCELLED: _ClassVar[RunStatus]
    BUDGET_EXCEEDED: _ClassVar[RunStatus]
    SWITCHED: _ClassVar[RunStatus]
ACTION_TYPE_UNSPECIFIED: ActionType
MODEL_CALL: ActionType
TOOL_CALL: ActionType
VERIFY: ActionType
RETRY: ActionType
SWITCH_HARNESS: ActionType
TERMINATE: ActionType
CONTROL_OP_UNSPECIFIED: ControlOp
PAUSE: ControlOp
RESUME: ControlOp
INTERRUPT: ControlOp
TERMINATE_RUN: ControlOp
RUN_STATUS_UNSPECIFIED: RunStatus
PENDING: RunStatus
RUNNING: RunStatus
PAUSED: RunStatus
SUCCEEDED: RunStatus
FAILED: RunStatus
CANCELLED: RunStatus
BUDGET_EXCEEDED: RunStatus
SWITCHED: RunStatus

class Budget(_message.Message):
    __slots__ = ("max_actions", "max_usd", "max_wall_ms", "max_tokens")
    MAX_ACTIONS_FIELD_NUMBER: _ClassVar[int]
    MAX_USD_FIELD_NUMBER: _ClassVar[int]
    MAX_WALL_MS_FIELD_NUMBER: _ClassVar[int]
    MAX_TOKENS_FIELD_NUMBER: _ClassVar[int]
    max_actions: int
    max_usd: float
    max_wall_ms: int
    max_tokens: int
    def __init__(self, max_actions: _Optional[int] = ..., max_usd: _Optional[float] = ..., max_wall_ms: _Optional[int] = ..., max_tokens: _Optional[int] = ...) -> None: ...

class BudgetUsage(_message.Message):
    __slots__ = ("actions", "usd", "wall_ms", "tokens")
    ACTIONS_FIELD_NUMBER: _ClassVar[int]
    USD_FIELD_NUMBER: _ClassVar[int]
    WALL_MS_FIELD_NUMBER: _ClassVar[int]
    TOKENS_FIELD_NUMBER: _ClassVar[int]
    actions: int
    usd: float
    wall_ms: int
    tokens: int
    def __init__(self, actions: _Optional[int] = ..., usd: _Optional[float] = ..., wall_ms: _Optional[int] = ..., tokens: _Optional[int] = ...) -> None: ...

class Message(_message.Message):
    __slots__ = ("role", "content")
    ROLE_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    role: str
    content: str
    def __init__(self, role: _Optional[str] = ..., content: _Optional[str] = ...) -> None: ...

class Artifact(_message.Message):
    __slots__ = ("path", "kind", "sha256", "bytes")
    PATH_FIELD_NUMBER: _ClassVar[int]
    KIND_FIELD_NUMBER: _ClassVar[int]
    SHA256_FIELD_NUMBER: _ClassVar[int]
    BYTES_FIELD_NUMBER: _ClassVar[int]
    path: str
    kind: str
    sha256: str
    bytes: int
    def __init__(self, path: _Optional[str] = ..., kind: _Optional[str] = ..., sha256: _Optional[str] = ..., bytes: _Optional[int] = ...) -> None: ...

class ToolResult(_message.Message):
    __slots__ = ("tool", "ok", "output", "usd")
    TOOL_FIELD_NUMBER: _ClassVar[int]
    OK_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_FIELD_NUMBER: _ClassVar[int]
    USD_FIELD_NUMBER: _ClassVar[int]
    tool: str
    ok: bool
    output: str
    usd: float
    def __init__(self, tool: _Optional[str] = ..., ok: bool = ..., output: _Optional[str] = ..., usd: _Optional[float] = ...) -> None: ...

class CommonExecutionState(_message.Message):
    __slots__ = ("task_id", "instruction", "messages", "artifacts", "variables", "tool_results", "workspace", "usage", "step", "harness_id", "checkpoint_id", "observations", "done", "failed", "failure_kind")
    class VariablesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    INSTRUCTION_FIELD_NUMBER: _ClassVar[int]
    MESSAGES_FIELD_NUMBER: _ClassVar[int]
    ARTIFACTS_FIELD_NUMBER: _ClassVar[int]
    VARIABLES_FIELD_NUMBER: _ClassVar[int]
    TOOL_RESULTS_FIELD_NUMBER: _ClassVar[int]
    WORKSPACE_FIELD_NUMBER: _ClassVar[int]
    USAGE_FIELD_NUMBER: _ClassVar[int]
    STEP_FIELD_NUMBER: _ClassVar[int]
    HARNESS_ID_FIELD_NUMBER: _ClassVar[int]
    CHECKPOINT_ID_FIELD_NUMBER: _ClassVar[int]
    OBSERVATIONS_FIELD_NUMBER: _ClassVar[int]
    DONE_FIELD_NUMBER: _ClassVar[int]
    FAILED_FIELD_NUMBER: _ClassVar[int]
    FAILURE_KIND_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    instruction: str
    messages: _containers.RepeatedCompositeFieldContainer[Message]
    artifacts: _containers.RepeatedCompositeFieldContainer[Artifact]
    variables: _containers.ScalarMap[str, str]
    tool_results: _containers.RepeatedCompositeFieldContainer[ToolResult]
    workspace: str
    usage: BudgetUsage
    step: int
    harness_id: str
    checkpoint_id: str
    observations: _containers.RepeatedScalarFieldContainer[str]
    done: bool
    failed: bool
    failure_kind: str
    def __init__(self, task_id: _Optional[str] = ..., instruction: _Optional[str] = ..., messages: _Optional[_Iterable[_Union[Message, _Mapping]]] = ..., artifacts: _Optional[_Iterable[_Union[Artifact, _Mapping]]] = ..., variables: _Optional[_Mapping[str, str]] = ..., tool_results: _Optional[_Iterable[_Union[ToolResult, _Mapping]]] = ..., workspace: _Optional[str] = ..., usage: _Optional[_Union[BudgetUsage, _Mapping]] = ..., step: _Optional[int] = ..., harness_id: _Optional[str] = ..., checkpoint_id: _Optional[str] = ..., observations: _Optional[_Iterable[str]] = ..., done: bool = ..., failed: bool = ..., failure_kind: _Optional[str] = ...) -> None: ...

class TaskSpec(_message.Message):
    __slots__ = ("id", "instruction", "workspace", "metadata", "budget", "required_capabilities", "category")
    class MetadataEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    ID_FIELD_NUMBER: _ClassVar[int]
    INSTRUCTION_FIELD_NUMBER: _ClassVar[int]
    WORKSPACE_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    BUDGET_FIELD_NUMBER: _ClassVar[int]
    REQUIRED_CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    id: str
    instruction: str
    workspace: str
    metadata: _containers.ScalarMap[str, str]
    budget: Budget
    required_capabilities: _containers.RepeatedScalarFieldContainer[str]
    category: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, id: _Optional[str] = ..., instruction: _Optional[str] = ..., workspace: _Optional[str] = ..., metadata: _Optional[_Mapping[str, str]] = ..., budget: _Optional[_Union[Budget, _Mapping]] = ..., required_capabilities: _Optional[_Iterable[str]] = ..., category: _Optional[_Iterable[str]] = ...) -> None: ...

class ActionCandidate(_message.Message):
    __slots__ = ("id", "type", "provider", "capabilities", "est_cost_usd", "est_latency_ms", "expected_success", "risk", "required_permissions", "payload_json", "rationale")
    ID_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    PROVIDER_FIELD_NUMBER: _ClassVar[int]
    CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
    EST_COST_USD_FIELD_NUMBER: _ClassVar[int]
    EST_LATENCY_MS_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_SUCCESS_FIELD_NUMBER: _ClassVar[int]
    RISK_FIELD_NUMBER: _ClassVar[int]
    REQUIRED_PERMISSIONS_FIELD_NUMBER: _ClassVar[int]
    PAYLOAD_JSON_FIELD_NUMBER: _ClassVar[int]
    RATIONALE_FIELD_NUMBER: _ClassVar[int]
    id: str
    type: ActionType
    provider: str
    capabilities: _containers.RepeatedScalarFieldContainer[str]
    est_cost_usd: float
    est_latency_ms: int
    expected_success: float
    risk: float
    required_permissions: _containers.RepeatedScalarFieldContainer[str]
    payload_json: str
    rationale: str
    def __init__(self, id: _Optional[str] = ..., type: _Optional[_Union[ActionType, str]] = ..., provider: _Optional[str] = ..., capabilities: _Optional[_Iterable[str]] = ..., est_cost_usd: _Optional[float] = ..., est_latency_ms: _Optional[int] = ..., expected_success: _Optional[float] = ..., risk: _Optional[float] = ..., required_permissions: _Optional[_Iterable[str]] = ..., payload_json: _Optional[str] = ..., rationale: _Optional[str] = ...) -> None: ...

class DecisionRequest(_message.Message):
    __slots__ = ("state", "candidates", "question", "budget", "usage", "backend")
    STATE_FIELD_NUMBER: _ClassVar[int]
    CANDIDATES_FIELD_NUMBER: _ClassVar[int]
    QUESTION_FIELD_NUMBER: _ClassVar[int]
    BUDGET_FIELD_NUMBER: _ClassVar[int]
    USAGE_FIELD_NUMBER: _ClassVar[int]
    BACKEND_FIELD_NUMBER: _ClassVar[int]
    state: CommonExecutionState
    candidates: _containers.RepeatedCompositeFieldContainer[ActionCandidate]
    question: str
    budget: Budget
    usage: BudgetUsage
    backend: str
    def __init__(self, state: _Optional[_Union[CommonExecutionState, _Mapping]] = ..., candidates: _Optional[_Iterable[_Union[ActionCandidate, _Mapping]]] = ..., question: _Optional[str] = ..., budget: _Optional[_Union[Budget, _Mapping]] = ..., usage: _Optional[_Union[BudgetUsage, _Mapping]] = ..., backend: _Optional[str] = ...) -> None: ...

class Decision(_message.Message):
    __slots__ = ("candidate_ids", "probabilities", "chosen_id", "confidence", "policy_id", "backend", "latency_ms", "rationale")
    CANDIDATE_IDS_FIELD_NUMBER: _ClassVar[int]
    PROBABILITIES_FIELD_NUMBER: _ClassVar[int]
    CHOSEN_ID_FIELD_NUMBER: _ClassVar[int]
    CONFIDENCE_FIELD_NUMBER: _ClassVar[int]
    POLICY_ID_FIELD_NUMBER: _ClassVar[int]
    BACKEND_FIELD_NUMBER: _ClassVar[int]
    LATENCY_MS_FIELD_NUMBER: _ClassVar[int]
    RATIONALE_FIELD_NUMBER: _ClassVar[int]
    candidate_ids: _containers.RepeatedScalarFieldContainer[str]
    probabilities: _containers.RepeatedScalarFieldContainer[float]
    chosen_id: str
    confidence: float
    policy_id: str
    backend: str
    latency_ms: float
    rationale: str
    def __init__(self, candidate_ids: _Optional[_Iterable[str]] = ..., probabilities: _Optional[_Iterable[float]] = ..., chosen_id: _Optional[str] = ..., confidence: _Optional[float] = ..., policy_id: _Optional[str] = ..., backend: _Optional[str] = ..., latency_ms: _Optional[float] = ..., rationale: _Optional[str] = ...) -> None: ...

class StartRequest(_message.Message):
    __slots__ = ("harness_id", "task", "state", "options_json", "run_id")
    HARNESS_ID_FIELD_NUMBER: _ClassVar[int]
    TASK_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    OPTIONS_JSON_FIELD_NUMBER: _ClassVar[int]
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    harness_id: str
    task: TaskSpec
    state: CommonExecutionState
    options_json: str
    run_id: str
    def __init__(self, harness_id: _Optional[str] = ..., task: _Optional[_Union[TaskSpec, _Mapping]] = ..., state: _Optional[_Union[CommonExecutionState, _Mapping]] = ..., options_json: _Optional[str] = ..., run_id: _Optional[str] = ...) -> None: ...

class StartResponse(_message.Message):
    __slots__ = ("run_id", "state")
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    run_id: str
    state: CommonExecutionState
    def __init__(self, run_id: _Optional[str] = ..., state: _Optional[_Union[CommonExecutionState, _Mapping]] = ...) -> None: ...

class StepRequest(_message.Message):
    __slots__ = ("run_id", "state", "decision")
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    DECISION_FIELD_NUMBER: _ClassVar[int]
    run_id: str
    state: CommonExecutionState
    decision: Decision
    def __init__(self, run_id: _Optional[str] = ..., state: _Optional[_Union[CommonExecutionState, _Mapping]] = ..., decision: _Optional[_Union[Decision, _Mapping]] = ...) -> None: ...

class StepResponse(_message.Message):
    __slots__ = ("state", "needs_decision")
    STATE_FIELD_NUMBER: _ClassVar[int]
    NEEDS_DECISION_FIELD_NUMBER: _ClassVar[int]
    state: CommonExecutionState
    needs_decision: bool
    def __init__(self, state: _Optional[_Union[CommonExecutionState, _Mapping]] = ..., needs_decision: bool = ...) -> None: ...

class ControlRequest(_message.Message):
    __slots__ = ("run_id", "harness_id", "op")
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    HARNESS_ID_FIELD_NUMBER: _ClassVar[int]
    OP_FIELD_NUMBER: _ClassVar[int]
    run_id: str
    harness_id: str
    op: ControlOp
    def __init__(self, run_id: _Optional[str] = ..., harness_id: _Optional[str] = ..., op: _Optional[_Union[ControlOp, str]] = ...) -> None: ...

class ControlResponse(_message.Message):
    __slots__ = ("ok", "error")
    OK_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    ok: bool
    error: str
    def __init__(self, ok: bool = ..., error: _Optional[str] = ...) -> None: ...

class InspectRequest(_message.Message):
    __slots__ = ("run_id", "harness_id")
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    HARNESS_ID_FIELD_NUMBER: _ClassVar[int]
    run_id: str
    harness_id: str
    def __init__(self, run_id: _Optional[str] = ..., harness_id: _Optional[str] = ...) -> None: ...

class InspectResponse(_message.Message):
    __slots__ = ("state", "alive", "harness_meta_json")
    STATE_FIELD_NUMBER: _ClassVar[int]
    ALIVE_FIELD_NUMBER: _ClassVar[int]
    HARNESS_META_JSON_FIELD_NUMBER: _ClassVar[int]
    state: CommonExecutionState
    alive: bool
    harness_meta_json: str
    def __init__(self, state: _Optional[_Union[CommonExecutionState, _Mapping]] = ..., alive: bool = ..., harness_meta_json: _Optional[str] = ...) -> None: ...

class HarnessInfo(_message.Message):
    __slots__ = ("id", "kind", "capabilities", "est_cost_usd_per_step", "est_latency_ms", "supports_checkpoint", "required_permissions")
    ID_FIELD_NUMBER: _ClassVar[int]
    KIND_FIELD_NUMBER: _ClassVar[int]
    CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
    EST_COST_USD_PER_STEP_FIELD_NUMBER: _ClassVar[int]
    EST_LATENCY_MS_FIELD_NUMBER: _ClassVar[int]
    SUPPORTS_CHECKPOINT_FIELD_NUMBER: _ClassVar[int]
    REQUIRED_PERMISSIONS_FIELD_NUMBER: _ClassVar[int]
    id: str
    kind: str
    capabilities: _containers.RepeatedScalarFieldContainer[str]
    est_cost_usd_per_step: float
    est_latency_ms: int
    supports_checkpoint: bool
    required_permissions: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, id: _Optional[str] = ..., kind: _Optional[str] = ..., capabilities: _Optional[_Iterable[str]] = ..., est_cost_usd_per_step: _Optional[float] = ..., est_latency_ms: _Optional[int] = ..., supports_checkpoint: bool = ..., required_permissions: _Optional[_Iterable[str]] = ...) -> None: ...

class ListHarnessesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListHarnessesResponse(_message.Message):
    __slots__ = ("harnesses",)
    HARNESSES_FIELD_NUMBER: _ClassVar[int]
    harnesses: _containers.RepeatedCompositeFieldContainer[HarnessInfo]
    def __init__(self, harnesses: _Optional[_Iterable[_Union[HarnessInfo, _Mapping]]] = ...) -> None: ...

class SubmitRequest(_message.Message):
    __slots__ = ("task", "policy_backend", "start_harness", "options_json", "run_id")
    TASK_FIELD_NUMBER: _ClassVar[int]
    POLICY_BACKEND_FIELD_NUMBER: _ClassVar[int]
    START_HARNESS_FIELD_NUMBER: _ClassVar[int]
    OPTIONS_JSON_FIELD_NUMBER: _ClassVar[int]
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    task: TaskSpec
    policy_backend: str
    start_harness: str
    options_json: str
    run_id: str
    def __init__(self, task: _Optional[_Union[TaskSpec, _Mapping]] = ..., policy_backend: _Optional[str] = ..., start_harness: _Optional[str] = ..., options_json: _Optional[str] = ..., run_id: _Optional[str] = ...) -> None: ...

class SubmitResponse(_message.Message):
    __slots__ = ("run_id",)
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    run_id: str
    def __init__(self, run_id: _Optional[str] = ...) -> None: ...

class RunEvent(_message.Message):
    __slots__ = ("run_id", "seq", "ts_ms", "kind", "status", "json_payload", "state", "decision", "action", "usage")
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    SEQ_FIELD_NUMBER: _ClassVar[int]
    TS_MS_FIELD_NUMBER: _ClassVar[int]
    KIND_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    JSON_PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    DECISION_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    USAGE_FIELD_NUMBER: _ClassVar[int]
    run_id: str
    seq: int
    ts_ms: int
    kind: str
    status: RunStatus
    json_payload: str
    state: CommonExecutionState
    decision: Decision
    action: ActionCandidate
    usage: BudgetUsage
    def __init__(self, run_id: _Optional[str] = ..., seq: _Optional[int] = ..., ts_ms: _Optional[int] = ..., kind: _Optional[str] = ..., status: _Optional[_Union[RunStatus, str]] = ..., json_payload: _Optional[str] = ..., state: _Optional[_Union[CommonExecutionState, _Mapping]] = ..., decision: _Optional[_Union[Decision, _Mapping]] = ..., action: _Optional[_Union[ActionCandidate, _Mapping]] = ..., usage: _Optional[_Union[BudgetUsage, _Mapping]] = ...) -> None: ...

class WatchRequest(_message.Message):
    __slots__ = ("run_id",)
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    run_id: str
    def __init__(self, run_id: _Optional[str] = ...) -> None: ...

class GetRunRequest(_message.Message):
    __slots__ = ("run_id",)
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    run_id: str
    def __init__(self, run_id: _Optional[str] = ...) -> None: ...

class RunRecord(_message.Message):
    __slots__ = ("run_id", "status", "task", "state", "usage", "budget", "started_ms", "ended_ms", "error", "events", "checkpoints")
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    TASK_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    USAGE_FIELD_NUMBER: _ClassVar[int]
    BUDGET_FIELD_NUMBER: _ClassVar[int]
    STARTED_MS_FIELD_NUMBER: _ClassVar[int]
    ENDED_MS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    EVENTS_FIELD_NUMBER: _ClassVar[int]
    CHECKPOINTS_FIELD_NUMBER: _ClassVar[int]
    run_id: str
    status: RunStatus
    task: TaskSpec
    state: CommonExecutionState
    usage: BudgetUsage
    budget: Budget
    started_ms: int
    ended_ms: int
    error: str
    events: _containers.RepeatedCompositeFieldContainer[RunEvent]
    checkpoints: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, run_id: _Optional[str] = ..., status: _Optional[_Union[RunStatus, str]] = ..., task: _Optional[_Union[TaskSpec, _Mapping]] = ..., state: _Optional[_Union[CommonExecutionState, _Mapping]] = ..., usage: _Optional[_Union[BudgetUsage, _Mapping]] = ..., budget: _Optional[_Union[Budget, _Mapping]] = ..., started_ms: _Optional[int] = ..., ended_ms: _Optional[int] = ..., error: _Optional[str] = ..., events: _Optional[_Iterable[_Union[RunEvent, _Mapping]]] = ..., checkpoints: _Optional[_Iterable[str]] = ...) -> None: ...

class CancelRequest(_message.Message):
    __slots__ = ("run_id",)
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    run_id: str
    def __init__(self, run_id: _Optional[str] = ...) -> None: ...

class CancelResponse(_message.Message):
    __slots__ = ("ok",)
    OK_FIELD_NUMBER: _ClassVar[int]
    ok: bool
    def __init__(self, ok: bool = ...) -> None: ...
