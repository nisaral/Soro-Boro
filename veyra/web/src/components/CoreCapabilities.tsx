import { CheckCircle2, Shield, AlertOctagon, RefreshCw, GitFork, FileCode2, Terminal, Database, Lock } from "lucide-react";

export default function CoreCapabilities() {
  const capabilities = [
    {
      icon: Lock,
      title: "Durable Operation Identity",
      description: "Binds every mutating tool call to a durable logical operation ID and stable idempotency key. Keys are deterministically reused across retries—never regenerated per attempt.",
      badge: "IDENTITY",
    },
    {
      icon: RefreshCw,
      title: "Idempotency-First Recovery",
      description: "When network drops occur, Soro-Boro's primary defense is stable key deduplication at the provider. Blind replays with new keys are strictly prohibited for mutations.",
      badge: "RECOVERY",
    },
    {
      icon: Shield,
      title: "Rich Lifecycle Reconciliation",
      description: "Providers do not return binary booleans. Soro-Boro reconciles through rich multi-stage states (SUCCEEDED, PENDING, FAILED, REQUIRES_ACTION, NOT_FOUND).",
      badge: "RECONCILER",
    },
    {
      icon: AlertOctagon,
      title: "Eventual Consistency Guards",
      description: "Immediate lookups on eventual read replicas can return false 404s. Soro-Boro flags eventual consistency and enforces safe deferral (AMBIGUOUS_DEFERRED) rather than retrying.",
      badge: "CONSISTENCY",
    },
    {
      icon: Database,
      title: "Write-Ahead Intent (WAL)",
      description: "Synchronously writes INTENT to disk before the external tool is invoked. If the host crashes mid-mutation, startup scanners detect orphaned writes before resuming the agent.",
      badge: "DURABILITY",
    },
    {
      icon: FileCode2,
      title: "Tamper-Evident Audit Ledger",
      description: "Every dispatch, reconciliation, and terminal state is chained into an append-only SHA-256 ledger, providing reproducible evidence for post-incident triage and compliance.",
      badge: "AUDIT TRAIL",
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
            Engineered for consequential agent writes.
          </h2>
          <p className="text-sm text-slate-600 mt-2">
            Soro-Boro prevents unsafe retries and data drift when AI agents touch money, cloud resources, or production databases.
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
