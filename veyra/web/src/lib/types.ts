// Types for Veyra Web Application

export interface ExecutionNode {
  id: string;
  label: string;
  subtitle: string;
  inputs: Record<string, any>;
  decision: {
    model: string;
    action_type: string;
    target: string;
    confidence: number;
    latency_ms: number;
  };
  probabilities: { name: string; prob: number; allowed: boolean }[];
  policy_constraints: { rule: string; status: "passed" | "blocked"; detail: string }[];
  selected_action: string;
  cost: number;
  result: {
    status: "success" | "failure" | "pending";
    observation: string;
    verification: string;
  };
}

export interface Gate1Result {
  model_cohort: string;
  agents: string[];
  m_count: number;
  best_agent: string;
  best_pass_rate: number;
  oracle_rate: number;
  null_rate: number;
  net_headroom: number;
  ci_lower: number;
  ci_upper: number;
  mde_80: number;
  margin: number;
  verdict: "STOP" | "INCONCLUSIVE" | "CLEAR";
  oracle_cost?: number;
  null_cost?: number;
  cost_delta?: number;
}

export interface TraceEvent {
  id: string;
  timestamp: string;
  type: 
    | "TASK_CREATED"
    | "STATE_UPDATED"
    | "DECISION"
    | "POLICY_EVAL"
    | "TOOL_CALL"
    | "OBSERVATION"
    | "FAILURE"
    | "POLICY_UPDATE"
    | "SWITCH_HARNESS"
    | "VERIFICATION"
    | "SUCCESS";
  summary: string;
  harness: string;
  details: Record<string, any>;
  cost_delta: number;
}

export interface CandidateAction {
  name: string;
  type: string;
  probability: number;
  estimated_cost: number;
  risk_level: "low" | "medium" | "high" | "critical";
  allowed: boolean;
  block_reason?: string;
}

export interface ActiveRunState {
  task_id: string;
  task_prompt: string;
  current_harness: string;
  current_step: number;
  max_steps: number;
  budget_limit: number;
  budget_used: number;
  model_calls: number;
  tool_calls: number;
  confidence: number;
  status: "running" | "paused" | "completed" | "failed";
}
