import { CheckCircle2, Clock, ArrowRight, ShieldCheck, Cpu } from "lucide-react";

export default function RoadmapSection() {
  const roadmapSteps = [
    {
      week: "Week 1",
      title: "Core Tool Boundary",
      status: "COMPLETED",
      items: [
        "Veyra tool interceptor & @veyra.tool decorator",
        "7-tier structured failure taxonomy",
        "Safe argument normalizer (0 semantic guessing)",
        "Bounded safe retry engine (strict idempotency)",
        "Tier 0 synthetic validation (200+ cases passed)",
      ],
    },
    {
      week: "Week 2",
      title: "Controlled Benchmark Evidence",
      status: "COMPLETED",
      items: [
        "ToolMisuseBench 4-way comparative harness",
        "Raw vs Naive vs Structured vs Veyra comparison",
        "+25 percentage-point win over raw agent (41.7% vs 16.7%)",
        "50.0% boundary recovery rate with 0 unsafe retries",
        "15 agent re-planning cycles eliminated",
      ],
    },
    {
      week: "Week 3",
      title: "Real MCP Catalogs & Stress Testing",
      status: "IN PROGRESS",
      items: [
        "Test against 3 real MCP catalogs (Filesystem, GitHub, Postgres)",
        "Measure real-world latency, schema drift, and timeouts",
        "Evaluate on MCP-Universe & MCPMark suites",
        "Benchmark report on production-like fault scenarios",
      ],
    },
    {
      week: "Week 4",
      title: "Release & Routing Laboratory",
      status: "UPCOMING",
      items: [
        "PyPI package & open-source GitHub release",
        "Developer documentation & live MCP tutorials",
        "Initial routing laboratory: exact cache & value-shape feasibility",
        "Sequential routing experiments: TAGE-history & process graphs",
      ],
    },
  ];

  return (
    <section className="py-16 sm:py-20 bg-slate-50/50 border-t border-slate-200/80">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="max-w-2xl mb-12">
          <span className="text-xs font-mono font-semibold uppercase tracking-wider text-slate-500 bg-slate-100 px-2.5 py-1 rounded border border-slate-200">
            Roadmap & Milestones
          </span>
          <h2 className="text-2xl sm:text-3xl font-semibold text-slate-900 tracking-tight mt-3">
            Frozen 4-week execution roadmap.
          </h2>
          <p className="text-sm text-slate-600 mt-2">
            Build the boundary first. Measure what actually breaks. Automate only what is safely automatable. Learn only from evidence.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {roadmapSteps.map((step, idx) => (
            <div
              key={idx}
              className={`technical-card p-6 bg-white flex flex-col justify-between ${
                step.status === "COMPLETED"
                  ? "border-emerald-500/30 ring-1 ring-emerald-500/10"
                  : step.status === "IN PROGRESS"
                  ? "border-amber-500/40 ring-1 ring-amber-500/20"
                  : "border-slate-200/80"
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-mono font-bold text-slate-900">{step.week}</span>
                  <span
                    className={`text-[10px] font-mono px-2 py-0.5 rounded font-semibold ${
                      step.status === "COMPLETED"
                        ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                        : step.status === "IN PROGRESS"
                        ? "bg-amber-50 text-amber-700 border border-amber-200"
                        : "bg-slate-100 text-slate-600 border border-slate-200"
                    }`}
                  >
                    {step.status}
                  </span>
                </div>
                <h3 className="text-sm font-semibold text-slate-900 mb-3">{step.title}</h3>
                <ul className="space-y-2 text-xs text-slate-600">
                  {step.items.map((item, itemIdx) => (
                    <li key={itemIdx} className="flex items-start gap-2">
                      <span className="text-slate-400 mt-0.5">•</span>
                      <span className="leading-snug">{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
