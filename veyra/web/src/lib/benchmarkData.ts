import { Gate1Result, TraceEvent, CandidateAction, ExecutionNode } from "./types";

export interface ToolMisuseBenchmarkResult {
  arm: string;
  name: string;
  task_success_rate: number;
  boundary_recovery_rate: number;
  unsafe_retries: number;
  agent_replans: number;
  total_tool_calls: number;
  latency_ms: number;
  status: "BASELINE" | "UNSAFE" | "INEFFICIENT" | "WINNER";
  description: string;
}

export const TOOLMISUSE_BENCHMARK_DATA: ToolMisuseBenchmarkResult[] = [
  {
    arm: "raw_agent",
    name: "Raw Agent (Standard Baseline)",
    task_success_rate: 16.7,
    boundary_recovery_rate: 0.0,
    unsafe_retries: 0,
    agent_replans: 50,
    total_tool_calls: 60,
    latency_ms: 12.4,
    status: "BASELINE",
    description: "Uncaught tool failure throws raw exception to agent prompt, forcing an expensive LLM re-planning cycle.",
  },
  {
    arm: "naive_retry",
    name: "Raw Agent + Naive Retry",
    task_success_rate: 16.7,
    boundary_recovery_rate: 0.0,
    unsafe_retries: 40,
    agent_replans: 50,
    total_tool_calls: 140,
    latency_ms: 38.6,
    status: "UNSAFE",
    description: "Blindly retries all errors up to 3 times, causing 40 critical unsafe retries on non-idempotent write operations.",
  },
  {
    arm: "structured_feedback",
    name: "Raw Agent + Structured Feedback",
    task_success_rate: 16.7,
    boundary_recovery_rate: 0.0,
    unsafe_retries: 0,
    agent_replans: 50,
    total_tool_calls: 60,
    latency_ms: 14.2,
    status: "INEFFICIENT",
    description: "Injects structured JSON errors into prompt; agent avoids crashes but still burns tokens on unnecessary re-plans.",
  },
  {
    arm: "veyra",
    name: "Agent + Veyra (Boundary Layer)",
    task_success_rate: 41.7,
    boundary_recovery_rate: 50.0,
    unsafe_retries: 0,
    agent_replans: 35,
    total_tool_calls: 75,
    latency_ms: 16.8,
    status: "WINNER",
    description: "Safely normalizes arguments and retries idempotent transient errors at the boundary. +25pp success, 15 re-plans eliminated.",
  },
];

export const DEMO_EXECUTION_NODES: ExecutionNode[] = [
  {
    id: "proposal",
    label: "Proposal",
    subtitle: "Agent Tool Proposal",
    inputs: { tool: "get_invoice", arguments: { invoice_id: "2042", status: "PAID" } },
    decision: { model: "Agent Proposal", action_type: "PROPOSE_ACTION", target: "get_invoice", confidence: 1.0, latency_ms: 1.2 },
    probabilities: [
      { name: "get_invoice", prob: 1.0, allowed: true },
    ],
    policy_constraints: [{ rule: "Boundary Intercept", status: "passed", detail: "Proposed tool call captured by Veyra middleware" }],
    selected_action: "PROPOSAL(tool='get_invoice', args={'invoice_id': '2042'})",
    cost: 0.0,
    result: { status: "pending", observation: "Received raw tool call proposal from agent", verification: "Boundary active" },
  },
  {
    id: "candidates",
    label: "Candidates",
    subtitle: "Candidate Resolver",
    inputs: { proposed_tool: "get_invoice", declared_equivalents: ["crm.get_invoice", "billing.get_invoice"] },
    decision: { model: "DeterministicCandidateResolver", action_type: "RESOLVE_CANDIDATES", target: "ToolRegistry", confidence: 1.0, latency_ms: 0.4 },
    probabilities: [
      { name: "get_invoice (primary)", prob: 0.7, allowed: true },
      { name: "crm.get_invoice (declared equivalent)", prob: 0.2, allowed: true },
      { name: "billing.get_invoice (declared equivalent)", prob: 0.1, allowed: true },
    ],
    policy_constraints: [{ rule: "Declared Equivalence", status: "passed", detail: "Explicit developer mappings resolved. No semantic guessing." }],
    selected_action: "CANDIDATE_SET(['get_invoice', 'crm.get_invoice'])",
    cost: 0.0,
    result: { status: "pending", observation: "Resolved candidate pool with declared metadata", verification: "Registry matched" },
  },
  {
    id: "constraints",
    label: "Constraints",
    subtitle: "Hard Guardrails",
    inputs: { tool_permissions: ["invoices:read"], caller_permissions: ["invoices:read", "user:basic"], risk_tier: "low" },
    decision: { model: "HardConstraintFilter", action_type: "FILTER_CANDIDATES", target: "Permissions & Risk", confidence: 1.0, latency_ms: 0.3 },
    probabilities: [
      { name: "get_invoice", prob: 1.0, allowed: true },
      { name: "delete_invoice", prob: 0.0, allowed: false },
    ],
    policy_constraints: [
      { rule: "Action Space Invariant", status: "passed", detail: "Router never widens policy-allowed action space" },
      { rule: "Permission Check", status: "passed", detail: "caller permissions satisfy invoices:read" },
    ],
    selected_action: "ALLOWED_CANDIDATE(get_invoice, risk='low')",
    cost: 0.0,
    result: { status: "pending", observation: "Hard constraints verified. Health check OK.", verification: "Invariants safe" },
  },
  {
    id: "route",
    label: "RoutePolicy",
    subtitle: "Deterministic Selection",
    inputs: { candidates: ["get_invoice"], policy: "DeterministicRoutePolicy" },
    decision: { model: "DeterministicRoutePolicy", action_type: "SELECT_ACTION", target: "get_invoice", confidence: 1.0, latency_ms: 0.2 },
    probabilities: [
      { name: "get_invoice", prob: 1.0, allowed: true },
    ],
    policy_constraints: [{ rule: "Deterministic Ordering", status: "passed", detail: "Primary declared tool selected without LLM latency" }],
    selected_action: "RESOLVED_ACTION(tool='get_invoice')",
    cost: 0.0,
    result: { status: "pending", observation: "Primary candidate selected by policy", verification: "Deterministic" },
  },
  {
    id: "normalizer",
    label: "Normalizer",
    subtitle: "Safe Coercion",
    inputs: { raw_args: { invoice_id: "2042", status: "PAID" }, schema: { invoice_id: "integer", status: ["paid", "pending"] } },
    decision: { model: "VeyraSafeNormalizer", action_type: "NORMALIZE_ARGS", target: "Arguments", confidence: 1.0, latency_ms: 0.5 },
    probabilities: [
      { name: "coerce '2042' -> 2042 (int)", prob: 1.0, allowed: true },
      { name: "normalize 'PAID' -> 'paid' (enum)", prob: 1.0, allowed: true },
    ],
    policy_constraints: [{ rule: "Zero Semantic Guessing", status: "passed", detail: "Only documented, semantics-preserving type normalizations" }],
    selected_action: "NORMALIZE(invoice_id=2042, status='paid')",
    cost: 0.0,
    result: { status: "pending", observation: "Corrected malformed string integer and enum casing before execution", verification: "Semantics intact" },
  },
  {
    id: "execution",
    label: "Execution",
    subtitle: "Tool Boundary Call",
    inputs: { tool: "get_invoice", args: { invoice_id: 2042, status: "paid" }, protocol: "mcp" },
    decision: { model: "MCP / Python Runtime", action_type: "EXECUTE_TOOL", target: "Invoice Service", confidence: 1.0, latency_ms: 14.2 },
    probabilities: [
      { name: "execute call_tool", prob: 1.0, allowed: true },
    ],
    policy_constraints: [{ rule: "Transport Protocol", status: "passed", detail: "Dispatched over JSON-RPC MCP channel" }],
    selected_action: "EXECUTE(get_invoice, attempt=1)",
    cost: 0.0,
    result: { status: "pending", observation: "Upstream returned HTTP 503 Service Unavailable (transient timeout)", verification: "Classifying error" },
  },
  {
    id: "recovery",
    label: "Safe Recovery",
    subtitle: "7-Tier Taxonomy",
    inputs: { error: "TimeoutError (503)", is_idempotent: true, is_retryable: true, kind: "TRANSIENT_ERROR" },
    decision: { model: "SafeRecoveryPolicy", action_type: "SAFE_RETRY", target: "get_invoice", confidence: 1.0, latency_ms: 18.5 },
    probabilities: [
      { name: "safe_retry (attempt 2)", prob: 1.0, allowed: true },
      { name: "unsafe_retry (non-idempotent)", prob: 0.0, allowed: false },
    ],
    policy_constraints: [
      { rule: "Idempotency Invariant", status: "passed", detail: "Read-only GET operation is idempotent and declared retryable" },
      { rule: "Zero Unsafe Retries", status: "passed", detail: "0 unsafe writes permitted" },
    ],
    selected_action: "RETRY(get_invoice, attempt=2) -> SUCCESS",
    cost: 0.0,
    result: { status: "success", observation: "Attempt 2 succeeded! Invoice $150.00 returned. 0 agent replans needed.", verification: "Recovered at boundary" },
  },
  {
    id: "trace",
    label: "Audit Trace",
    subtitle: "Telemetry & Redaction",
    inputs: { trace_id: "trc_9a8f21cd", decision: "retried_and_succeeded", safe: true, latency_ms: 34.8 },
    decision: { model: "TraceSink", action_type: "LOG_TRACE", target: "Audit Log", confidence: 1.0, latency_ms: 0.2 },
    probabilities: [
      { name: "record trace", prob: 1.0, allowed: true },
    ],
    policy_constraints: [{ rule: "Sensitive Key Redaction", status: "passed", detail: "Redacted auth tokens and credentials automatically" }],
    selected_action: "RECORD_TRACE(decision='retried_and_succeeded', safe=True)",
    cost: 0.0,
    result: { status: "success", observation: "Trace recorded to memory and runs/traces.jsonl for 'veyra audit'", verification: "Complete" },
  },
];

export const GATE1_BENCHMARK_DATA: Gate1Result[] = [
  {
    model_cohort: "GPT-5.3-Codex — Vendor Triplet",
    agents: ["SageAgent", "Droid", "Mux"],
    m_count: 3,
    best_agent: "SageAgent",
    best_pass_rate: 78.4,
    oracle_rate: 88.1,
    null_rate: 85.0,
    net_headroom: 3.13,
    ci_lower: 0.73,
    ci_upper: 6.04,
    mde_80: 3.79,
    margin: 5.0,
    verdict: "INCONCLUSIVE",
  },
  {
    model_cohort: "Claude Opus 4.7",
    agents: ["vix", "0error Ledger"],
    m_count: 2,
    best_agent: "vix",
    best_pass_rate: 89.9,
    oracle_rate: 91.2,
    null_rate: 94.0,
    net_headroom: -2.79,
    ci_lower: -4.58,
    ci_upper: -1.08,
    mde_80: 2.56,
    margin: 5.0,
    verdict: "STOP",
  },
];

export const DEMO_TRACE_EVENTS: TraceEvent[] = [
  {
    id: "evt-101",
    timestamp: "09:41:02.102",
    type: "TOOL_CALL",
    summary: "Agent proposed get_invoice(invoice_id='2042')",
    harness: "agent-caller",
    details: { tool: "get_invoice", arguments: { invoice_id: "2042" } },
    cost_delta: 0.0,
  },
  {
    id: "evt-102",
    timestamp: "09:41:02.105",
    type: "POLICY_EVAL",
    summary: "Veyra normalized argument: '2042' -> 2042 (int)",
    harness: "veyra-boundary",
    details: { corrections: ["Coerced invoice_id to int"] },
    cost_delta: 0.0,
  },
  {
    id: "evt-103",
    timestamp: "09:41:02.124",
    type: "FAILURE",
    summary: "Attempt 1 failed: HTTP 503 upstream timeout",
    harness: "veyra-boundary",
    details: { kind: "transient_error", retryable: true, idempotent: true },
    cost_delta: 0.0,
  },
  {
    id: "evt-104",
    timestamp: "09:41:02.145",
    type: "SUCCESS",
    summary: "Attempt 2 succeeded via safe bounded retry. Returned invoice $150.00.",
    harness: "veyra-boundary",
    details: { decision: "retried_and_succeeded", safe: true },
    cost_delta: 0.0,
  },
];

export const DEMO_CANDIDATE_ACTIONS: CandidateAction[] = [
  {
    name: "get_invoice (primary)",
    type: "TOOL_CALL",
    probability: 0.85,
    estimated_cost: 0.001,
    risk_level: "low",
    allowed: true,
  },
  {
    name: "crm.get_invoice (declared equivalent)",
    type: "TOOL_CALL",
    probability: 0.12,
    estimated_cost: 0.002,
    risk_level: "low",
    allowed: true,
  },
  {
    name: "delete_invoice",
    type: "TOOL_CALL",
    probability: 0.03,
    estimated_cost: 0.005,
    risk_level: "critical",
    allowed: false,
    block_reason: "Denied by hard constraint: destructive write requires invoices:write permission",
  },
];
