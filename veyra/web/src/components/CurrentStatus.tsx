import { CheckCircle2, ShieldCheck, BarChart3, Terminal } from "lucide-react";

export default function CurrentStatus() {
  const verifiedItems = [
    { title: "132 Python Tests Passing", detail: "Passing offline unit & integration test suite in under 4 seconds" },
    { title: "Tier 0 Correctness Validation", detail: "200+ synthetic cases: 0 false interventions, 0 unsafe retries, 100% classification accuracy" },
    { title: "ToolMisuseBench Controlled Win", detail: "41.7% vs 16.7% raw baseline (+25pp), 50% boundary recovery, 15 re-plans eliminated" },
    { title: "Safe Argument Normalizer", detail: "Strict scalar & enum coercion ('42' -> 42, ISO dates, whitespace). Zero semantic guessing" },
    { title: "7-Tier Failure Taxonomy", detail: "Structured classification for schema, transient, rate limit, precondition, auth, and unknown state" },
    { title: "Bounded Safe Retry Engine", detail: "Retries allowed ONLY on idempotent transient/rate-limit errors. 0 unsafe write retries" },
    { title: "CandidateResolver & Equivalence", detail: "Declared developer equivalence with hard constraint filtering (health, permissions, risk)" },
    { title: "DeterministicRoutePolicy", detail: "v0.1 deterministic priority selection; zero LLM or embedding latency overhead in runtime path" },
    { title: "ExecutionEngine Pipeline", detail: "Full proposal -> candidate resolution -> route policy -> execution -> recovery loop" },
    { title: "MCP Tool Middleware", detail: "Transparent wrapper intercepting MCP tools/call JSON-RPC messages" },
    { title: "Trace Sink & Redaction", detail: "Section 11 execution traces with automatic recursive redaction of credentials and secrets" },
    { title: "Diagnostic Audit CLI", detail: "veyra-py audit and veyra-py toolmisuse subcommands for developer telemetry" },
  ];

  return (
    <section className="py-16 sm:py-20 bg-white border-t border-slate-200/80">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="max-w-2xl mb-10">
          <span className="text-xs font-mono font-semibold uppercase tracking-wider text-slate-500 bg-slate-100 px-2.5 py-1 rounded border border-slate-200">
            Implementation Status
          </span>
          <h2 className="text-2xl sm:text-3xl font-semibold text-slate-900 tracking-tight mt-3">
            What&apos;s verified and working today
          </h2>
          <p className="text-sm text-slate-600 mt-2">
            Engineering gate passed. Honest status indicators verified by continuous test execution.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {verifiedItems.map((item, i) => (
            <div key={i} className="technical-card p-4 bg-white flex items-start gap-3 hover:border-slate-300 transition-colors">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
              <div>
                <div className="text-xs font-semibold text-slate-900">{item.title}</div>
                <div className="text-[11px] text-slate-500 mt-0.5 leading-snug">{item.detail}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
