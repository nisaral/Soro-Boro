"use client";

import { useState } from "react";
import { Check, Copy, Terminal, Play, Code2, Server, GitFork } from "lucide-react";

export default function DeveloperExperience() {
  const [activeTab, setActiveTab] = useState<"harness" | "python" | "reconciler" | "wal" | "cli">("harness");
  const [copied, setCopied] = useState(false);

  const snippets = {
    harness: `# Soro Unified Harness: Route -> Repair -> Guard
from soro.harness.pipeline import SoroHarness

# Load 4B or 0.8B pretrained model from Hugging Face
harness = SoroHarness.from_pretrained("nisaralll/soro-kev-4b")

@harness.tool(description="Look up customer order details", side_effect="read_only")
def get_order_status(order_id: str) -> dict:
    return {"order_id": order_id, "customer_email": "alice@acme.com", "shipment_id": "SHP-901"}

@harness.tool(description="Cancel pending warehouse shipment", side_effect="mutation")
def cancel_shipment(shipment_id: str) -> dict:
    return {"shipment_id": shipment_id, "cancelled": True}

# 1. Conformal Route: single prefill pointer pass (413ms NF4)
decision = harness.route("Check order ORD-774")
print(decision.action, decision.selected_tool)  # "EXECUTE", "get_order_status"

# 2. Multi-Step Workflow with Automatic Context Chaining:
trace = harness.run_workflow(
    "Look up order ORD-774, then cancel its shipment."
)
`,

    python: `# Soro-Boro: Wrap consequential mutations with durable boundary
from soro_boro import soro_wrap, SideEffectClass, OperationIdentity

@soro_wrap(
    side_effect_class=SideEffectClass.NON_IDEMPOTENT_MUTATION,
    key_generator=lambda order_id, amount: f"refund_{order_id}_{amount}",
    reconciler=stripe_refund_reconciler,
    max_retries=1
)
def refund_customer(order_id: str, amount: float, op: OperationIdentity):
    # op.idempotency_key is stable and deterministically bound to this logical write
    return stripe.Refund.create(
        charge=order_id,
        amount=int(amount * 100),
        idempotency_key=op.idempotency_key
    )

# Returns typed TerminalOutcome:
# outcome.status: "COMMITTED" | "PREVENTED_DUPLICATE" | "AMBIGUOUS_DEFERRED"
`,

    reconciler: `# Authoritative Provider Reconciler
from soro_boro import ReconciliationResult, ProviderLifecycleState, OperationIdentity

def stripe_refund_reconciler(op: OperationIdentity) -> ReconciliationResult:
    refunds = stripe.Refund.list(limit=1, idempotency_key=op.idempotency_key)
    if not refunds.data:
        # If read replica is eventual, NOT_FOUND cannot prove non-commit!
        return ReconciliationResult(
            state=ProviderLifecycleState.NOT_FOUND,
            authoritative=True,
            consistency_observed="strong"  # or "eventual"
        )

    rf = refunds.data[0]
    return ReconciliationResult(
        state=ProviderLifecycleState.SUCCEEDED if rf.status == "succeeded" else ProviderLifecycleState.PENDING,
        authoritative=True,
        raw_response=rf
    )`,

    wal: `# Tamper-Evident Write-Ahead Log (WAL)
from soro_boro import WriteAheadLog

wal = WriteAheadLog("runs/soro_boro_wal.jsonl")

# 1. Sync INTENT flushed before external call
wal.record_intent(op.operation_id, op.idempotency_key, "refund", {"amount": 149.99})

# 2. Crash recovery: On restart, detect any in-flight unacknowledged writes
orphans = wal.find_orphaned_intents()
for o in orphans:
    print(f"Reconciling orphaned write from crash: {o.operation_id}")`,

    cli: `# Soro-Boro Adversarial Benchmark & Audit CLI
# 1. Run the 5-fault distributed failure test suite (0 duplicate effects)
$ pytest python/tests/test_soro_boro_adversarial.py -v

# Output:
# test_dropped_ack_prevents_duplicate_charge ... PASSED
# test_stale_replica_causes_safe_deferral ...... PASSED
# test_probe_failure_fails_closed .............. PASSED
# test_wal_durability_and_crash_recovery ....... PASSED
# ================= 6 passed in 11.46s ==================`,
  };

  const copyCurrent = () => {
    navigator.clipboard.writeText(snippets[activeTab]);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <section className="py-16 sm:py-20 bg-slate-50/70 border-t border-slate-200/80">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
          <div className="lg:col-span-5 space-y-4">
            <span className="text-xs font-mono font-semibold uppercase tracking-wider text-slate-500 bg-slate-100 px-2.5 py-1 rounded border border-slate-200">
              Developer Experience
            </span>
            <h2 className="text-2xl sm:text-3xl font-semibold text-slate-900 tracking-tight">
              Explicit integration. Safe defaults. Zero blind retries.
            </h2>
            <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
              Wrap your consequential write operations with Soro-Boro. Retain your existing agent framework while enforcing stable idempotency keys, write-ahead durability, and fail-closed reconciliation.
            </p>

            <div className="pt-2 space-y-2 text-xs font-mono text-slate-700">
              <div className="flex items-center gap-2 p-2 bg-white rounded border border-slate-200">
                <Terminal className="w-3.5 h-3.5 text-slate-400" />
                <span>pip install soro-boro</span>
              </div>
              <div className="flex items-center gap-2 p-2 bg-white rounded border border-slate-200">
                <Play className="w-3.5 h-3.5 text-emerald-600" />
                <span>pytest python/tests/test_soro_boro_adversarial.py</span>
              </div>
            </div>
          </div>

          <div className="lg:col-span-7">
            <div className="technical-card bg-slate-950 text-slate-100 overflow-hidden shadow-md border-slate-800">
              {/* Tabs */}
              <div className="flex items-center justify-between border-b border-slate-800 bg-slate-900/60 px-4 py-2">
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setActiveTab("harness")}
                    className={`px-3 py-1 text-xs font-mono rounded transition-colors ${
                      activeTab === "harness"
                        ? "bg-slate-800 text-emerald-400 font-semibold"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    SoroHarness
                  </button>
                  <button
                    onClick={() => setActiveTab("python")}
                    className={`px-3 py-1 text-xs font-mono rounded transition-colors ${
                      activeTab === "python"
                        ? "bg-slate-800 text-emerald-400 font-semibold"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    @soro_wrap
                  </button>
                  <button
                    onClick={() => setActiveTab("reconciler")}
                    className={`px-3 py-1 text-xs font-mono rounded transition-colors ${
                      activeTab === "reconciler"
                        ? "bg-slate-800 text-emerald-400 font-semibold"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    Reconciler
                  </button>
                  <button
                    onClick={() => setActiveTab("wal")}
                    className={`px-3 py-1 text-xs font-mono rounded transition-colors ${
                      activeTab === "wal"
                        ? "bg-slate-800 text-emerald-400 font-semibold"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    Write-Ahead Log
                  </button>
                  <button
                    onClick={() => setActiveTab("cli")}
                    className={`px-3 py-1 text-xs font-mono rounded transition-colors ${
                      activeTab === "cli"
                        ? "bg-slate-800 text-emerald-400 font-semibold"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    Adversarial Suite
                  </button>
                </div>

                <button
                  onClick={copyCurrent}
                  className="flex items-center gap-1 text-[11px] font-mono text-slate-400 hover:text-slate-200 transition-colors"
                >
                  {copied ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-emerald-400" />
                      <span className="text-emerald-400">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" />
                      <span>Copy</span>
                    </>
                  )}
                </button>
              </div>

              {/* Code Snippet Box */}
              <div className="p-4 overflow-x-auto text-xs font-mono leading-relaxed text-slate-200 bg-slate-950">
                <pre>{snippets[activeTab]}</pre>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
