import { CheckCircle2, Clock, ArrowRight, ShieldCheck, Cpu } from "lucide-react";

export default function RoadmapSection() {
  const roadmapSteps = [
    {
      week: "Milestone 1",
      title: "Python Core & Identity",
      status: "COMPLETED",
      items: [
        "soro_boro package core with @soro_wrap decorator",
        "OperationIdentity with stable idempotency keys",
        "Rich ProviderLifecycleState (SUCCEEDED, PENDING, NOT_FOUND)",
        "Write-Ahead Intent (WAL) with synchronous fsync",
        "Crash recovery scanner for orphaned in-flight writes",
      ],
    },
    {
      week: "Milestone 2",
      title: "Adversarial Test Suite",
      status: "COMPLETED",
      items: [
        "5-fault distributed failure test matrix",
        "Dropped ACK recovery (0 duplicate mutations observed)",
        "Eventual consistency guard (AMBIGUOUS_DEFERRED safe halt)",
        "Reconciliation probe failure fail-closed invariant",
        "6 of 6 adversarial test cases verified via pytest",
      ],
    },
    {
      week: "Milestone 3",
      title: "Real Provider Integrations",
      status: "IN PROGRESS",
      items: [
        "Stripe Refunds reference mutator with idempotency reuse",
        "GitHub Issues & incident ticket creation reference",
        "Postgres / transactional SQL boundary wrapper",
        "Interactive web simulator with real-time WAL inspection",
      ],
    },
    {
      week: "Milestone 4",
      title: "Validation & Clearance",
      status: "UPCOMING",
      items: [
        "Namespace & trademark clearance (PyPI, USPTO, India CGPDTM)",
        "10-15 interviews with platform teams operating write agents",
        "Open-source GitHub release with reproducible benchmarks",
        "Clearance for commercial enterprise deployment",
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
            Grounded execution roadmap.
          </h2>
          <p className="text-sm text-slate-600 mt-2">
            Build the execution boundary first. Reconcile provider state authoritatively. Protect against eventual consistency false-negatives. Validate with real platform teams.
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
