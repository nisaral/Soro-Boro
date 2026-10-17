import { CheckCircle2, ShieldCheck, BarChart3, Terminal } from "lucide-react";

export default function CurrentStatus() {
  const verifiedItems = [
    { title: "Wrap + UNKNOWN_ACK", detail: "Five-minute charge/verify fixture: one ledger row, VERIFIED_COMMITTED, replayed=False" },
    { title: "DeterministicRouter", detail: "Contract filter then dense shortlist. EXECUTE / ASK / ABSTAIN / DENY. No LLM." },
    { title: "Thin agent loop", detail: "soro.run(task, llm=...) may only call tools that survived routing" },
    { title: "Catalog decorator", detail: "@soro.tool registers schema, side-effect class, permissions" },
    { title: "LangGraph / OpenAI Agents adapters", detail: "Wrap their tool nodes; Soro does not replace the graph" },
    { title: "ContinuityBench (local)", detail: "+20pp IPR vs fair static_resolution on the in-repo 120-task set — not a public leaderboard" },
    { title: "ToolMisuse +25pp", detail: "Quarantined. Do not treat the website table as a published score." },
    { title: "Harbor / MCPMark", detail: "Not claimed. No official public run." },
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
