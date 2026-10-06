import { CheckCircle2, Shield, AlertOctagon, RefreshCw, GitFork, FileCode2, Terminal } from "lucide-react";

export default function CoreCapabilities() {
  const capabilities = [
    {
      icon: CheckCircle2,
      title: "Safe Argument Normalizer",
      description: "Applies only provably safe, semantics-preserving coercions ('42' -> 42, 'true' -> True, unique enum matching, ISO dates). Zero semantic argument guessing.",
      badge: "CORRECTNESS",
    },
    {
      icon: AlertOctagon,
      title: "7-Tier Failure Taxonomy",
      description: "Classifies every failure into SCHEMA_ERROR, TRANSIENT_ERROR, RATE_LIMIT, PRECONDITION_ERROR, AUTHORIZATION_ERROR, UNKNOWN_STATE, or UNKNOWN with precise metadata.",
      badge: "TAXONOMY",
    },
    {
      icon: RefreshCw,
      title: "Bounded Safe Retries",
      description: "Retries ONLY when failure is transient/rate-limit AND operation is explicitly declared retryable AND idempotent. Strict 0 unsafe retries invariant.",
      badge: "SAFETY",
    },
    {
      icon: GitFork,
      title: "Candidate Resolution & Equivalence",
      description: "Explicit developer tool equivalence ('veyra.equivalent'). Enforces hard constraints (permissions, risk, health). Router never widens allowed action space.",
      badge: "ROUTING",
    },
    {
      icon: Terminal,
      title: "MCP & Python Drop-in Middleware",
      description: "Wraps standard Python functions (@veyra.tool) and intercepts MCP tools/call JSON-RPC messages. Developer keeps their agent, prompts, and models unchanged.",
      badge: "INTEGRATION",
    },
    {
      icon: FileCode2,
      title: "Observability & Audit CLI",
      description: "Section 11 telemetry traces with automatic credential redaction. Diagnostic CLI ('veyra audit') reports failures, recoveries, and replans avoided.",
      badge: "TELEMETRY",
    },
  ];

  return (
    <section className="py-16 sm:py-20 bg-white">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="max-w-2xl mb-12">
          <span className="text-xs font-mono font-semibold uppercase tracking-wider text-slate-500 bg-slate-100 px-2.5 py-1 rounded border border-slate-200">
            Core Architecture
          </span>
          <h2 className="text-2xl sm:text-3xl font-semibold text-slate-900 tracking-tight mt-3">
            Built for reliable, provably safe tool execution.
          </h2>
          <p className="text-sm text-slate-600 mt-2">
            Veyra sits outside the agent reasoning loop at the tool boundary, enforcing strict correctness and safety invariants.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {capabilities.map((cap, i) => {
            const Icon = cap.icon;
            return (
              <div key={i} className="technical-card p-6 bg-white flex flex-col justify-between group hover:border-slate-300 transition-colors">
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-100 text-slate-900 border border-slate-200 group-hover:bg-slate-900 group-hover:text-white transition-colors">
                      <Icon className="w-5 h-5" />
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-50 border border-slate-200 text-slate-600">
                      {cap.badge}
                    </span>
                  </div>
                  <h3 className="text-base font-semibold text-slate-900 mb-2">
                    {cap.title}
                  </h3>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    {cap.description}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
